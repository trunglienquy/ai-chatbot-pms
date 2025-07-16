from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
from sentence_transformers import SentenceTransformer, util
import json
import re

from config import load_config
from gemini_ai import configure_gemini, generate_sql_query, generate_natural_language_response
from db import get_db_connection
from schema_utils import load_schema, extract_table_names, validate_tables_in_sql, extract_possible_table_names, filter_schema_by_table_names
from sql_utils import is_safe_sql
from token_utils import token_manager

conversation_memory = {}
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

with open("table_keywords.json", "r", encoding="utf-8") as f:
    keyword_table_mapping = json.load(f)

def find_similar_cached_response(user_id, new_question, threshold=0.85):
    if user_id not in conversation_memory:
        return None
    
    new_embedding = embedding_model.encode(new_question, convert_to_tensor=True)
    for item in reversed(conversation_memory[user_id][-5:]):  # chỉ check 5 câu gần nhất
        sim = util.cos_sim(new_embedding, item['embedding'])[0][0].item()
        if sim > threshold:
            return item  # Trả lại kết quả cũ đã truy vấn
    
    return None

def parse_tasks_from_system(tasks_text):
    """
    Parse danh sách task từ hệ thống
    Format: "ID - ProjectName - TaskName"
    """
    tasks = []
    lines = tasks_text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Pattern: "221 - HousingStaff - Mockup register"
        match = re.match(r'(\d+)\s*-\s*([^-]+)\s*-\s*(.+)', line)
        if match:
            task_id, project_name, task_name = match.groups()
            tasks.append({
                'id': task_id.strip(),
                'project_name': project_name.strip(),
                'task_name': task_name.strip()
            })
    
    return tasks

def parse_daily_report(report_text):
    """
    Parse báo cáo hằng ngày để extract thông tin effort
    Chỉ phân tích phần "Today(Actual - Thực tế)"
    """
    # Tìm phần Actual
    actual_pattern = r'■■\s*Today\(Actual\s*-\s*Thực tế\)\s*■■(.*?)(?=■■|$)'
    actual_match = re.search(actual_pattern, report_text, re.DOTALL | re.IGNORECASE)
    
    if not actual_match:
        return []
    
    actual_section = actual_match.group(1)
    projects_effort = []
    
    # Pattern để tìm project và effort: "■ ProjectName - Xh"
    project_pattern = r'■\s*([^-]+)\s*-\s*(\d+)h'
    project_matches = re.findall(project_pattern, actual_section, re.IGNORECASE)
    
    for project_name, effort in project_matches:
        project_name = project_name.strip()
        effort = int(effort)
        
        # Tìm các task trong project này
        tasks = []
        # Pattern để tìm task: "+ Task description"
        task_pattern = r'\+\s*(.+)'
        task_matches = re.findall(task_pattern, actual_section)
        
        # Tìm phần task thuộc về project này
        project_start = actual_section.find(f"■ {project_name}")
        if project_start != -1:
            # Tìm phần kết thúc của project (dòng tiếp theo bắt đầu bằng ■)
            next_project = re.search(r'\n\s*■\s*[^-]', actual_section[project_start:])
            if next_project:
                project_section = actual_section[project_start:project_start + next_project.start()]
            else:
                project_section = actual_section[project_start:]
            
            # Extract tasks từ phần project
            task_matches = re.findall(r'\+\s*(.+)', project_section)
            tasks = [task.strip() for task in task_matches]
        
        projects_effort.append({
            'project_name': project_name,
            'effort': effort,
            'tasks': tasks
        })
    
    return projects_effort

def match_tasks_with_system_tasks(daily_efforts, system_tasks):
    """
    Match effort từ báo cáo với task trong hệ thống
    Cải thiện logic để chấp nhận task có ý nghĩa tương tự
    """
    results = []
    undefined_tasks = []
    
    for daily_effort in daily_efforts:
        project_name = daily_effort['project_name']
        total_effort = daily_effort['effort']
        daily_tasks = daily_effort['tasks']
        
        # Tìm các task trong hệ thống thuộc về project này
        matching_system_tasks = [
            task for task in system_tasks 
            if task['project_name'].lower() == project_name.lower()
        ]
        
        # Nếu không tìm thấy task trong hệ thống theo project name
        if not matching_system_tasks:
            # Thử tìm task theo nội dung tương tự trong toàn bộ hệ thống
            matched_tasks = []
            unmatched_daily_tasks = []
            
            for task_desc in daily_tasks:
                best_match = None
                best_score = 0
                
                for sys_task in system_tasks:
                    # Tính điểm tương đồng dựa trên nhiều tiêu chí
                    score = calculate_similarity_score(task_desc, sys_task['task_name'])
                    if score > best_score and score >= 0.3:  # Ngưỡng tối thiểu 30%
                        best_score = score
                        best_match = sys_task
                
                if best_match:
                    matched_tasks.append({
                        'daily_task': task_desc,
                        'system_task': best_match,
                        'score': best_score
                    })
                else:
                    unmatched_daily_tasks.append(task_desc)
            
            # Nếu tìm thấy ít nhất 1 task tương tự, phân bổ effort
            if matched_tasks:
                effort_per_matched_task = total_effort / len(matched_tasks)
                for match in matched_tasks:
                    results.append(f"{match['system_task']['id']} - {effort_per_matched_task}")
                
                # Thêm các task không match vào undefined
                for task_desc in unmatched_daily_tasks:
                    undefined_tasks.append({
                        'project_name': project_name,
                        'task_name': task_desc,
                        'effort': total_effort / len(daily_tasks) if daily_tasks else total_effort
                    })
            else:
                # Không tìm thấy task nào tương tự, thêm tất cả vào undefined
                for task_desc in daily_tasks:
                    undefined_tasks.append({
                        'project_name': project_name,
                        'task_name': task_desc,
                        'effort': total_effort / len(daily_tasks) if daily_tasks else total_effort
                    })
            continue
        
        # Nếu có task trong hệ thống theo project name
        matched_daily_tasks = []
        unmatched_daily_tasks = []
        
        for task_desc in daily_tasks:
            best_match = None
            best_score = 0
            
            # Ưu tiên tìm trong cùng project trước
            for sys_task in matching_system_tasks:
                score = calculate_similarity_score(task_desc, sys_task['task_name'])
                if score > best_score and score >= 0.3:
                    best_score = score
                    best_match = sys_task
            
            # Nếu không tìm thấy trong cùng project, tìm trong toàn bộ hệ thống
            if not best_match:
                for sys_task in system_tasks:
                    score = calculate_similarity_score(task_desc, sys_task['task_name'])
                    if score > best_score and score >= 0.3:
                        best_score = score
                        best_match = sys_task
            
            if best_match:
                matched_daily_tasks.append({
                    'daily_task': task_desc,
                    'system_task': best_match,
                    'score': best_score
                })
            else:
                unmatched_daily_tasks.append(task_desc)
        
        # Phân bổ effort cho các task đã match
        if matched_daily_tasks:
            effort_per_matched_task = total_effort / len(matched_daily_tasks)
            for match in matched_daily_tasks:
                results.append(f"{match['system_task']['id']} - {effort_per_matched_task}")
        
        # Thêm các task không match vào undefined
        for task_desc in unmatched_daily_tasks:
            undefined_tasks.append({
                'project_name': project_name,
                'task_name': task_desc,
                'effort': total_effort / len(daily_tasks) if daily_tasks else total_effort
            })
    
    return results, undefined_tasks

def calculate_similarity_score(daily_task, system_task):
    """
    Tính điểm tương đồng giữa task trong báo cáo và task trong hệ thống
    Trả về điểm từ 0-1, càng cao càng tương tự
    """
    daily_lower = daily_task.lower()
    system_lower = system_task.lower()
    
    # 1. Exact match hoặc substring match
    if daily_lower == system_lower:
        return 1.0
    if daily_lower in system_lower or system_lower in daily_lower:
        return 0.8
    
    # 2. Keyword matching
    daily_words = set(daily_lower.split())
    system_words = set(system_lower.split())
    
    # Loại bỏ các từ không quan trọng
    stop_words = {'làm', 'viết', 'tạo', 'thực', 'hiện', 'công', 'việc', 'task', 'work', 'do', 'make', 'create'}
    daily_words = daily_words - stop_words
    system_words = system_words - stop_words
    
    if not daily_words or not system_words:
        return 0.0
    
    # Tính điểm dựa trên số từ chung
    common_words = daily_words & system_words
    if common_words:
        similarity = len(common_words) / max(len(daily_words), len(system_words))
        return min(similarity * 1.5, 1.0)  # Tăng điểm cho keyword matching
    
    # 3. Fuzzy matching cho các từ tương tự
    # Ví dụ: "mockup" ~ "mock up", "register" ~ "registration"
    similar_keywords = {
        'mockup': ['mock', 'up', 'design'],
        'register': ['registration', 'signup', 'sign'],
        'meeting': ['meet', 'discussion', 'báo cáo'],
        'estimate': ['estimation', 'tính toán'],
        'price': ['pricing', 'giá', 'cost'],
        'schedule': ['lịch', 'trình', 'plan'],
        'transfer': ['chuyển', 'move', 'copy']
    }
    
    daily_keywords = set()
    system_keywords = set()
    
    for word in daily_words:
        for key, similar_list in similar_keywords.items():
            if word in similar_list or key in word:
                daily_keywords.add(key)
                break
    
    for word in system_words:
        for key, similar_list in similar_keywords.items():
            if word in similar_list or key in word:
                system_keywords.add(key)
                break
    
    if daily_keywords and system_keywords:
        common_keywords = daily_keywords & system_keywords
        if common_keywords:
            return 0.6  # Điểm cho fuzzy matching
    
    return 0.0


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

app = Flask(__name__)
CORS(app, resources={r"/ask": {"origins": "http://pms.test"}})
config_data = load_config()
configure_gemini(config_data["GEMINI_API_KEY"])
DB_CONFIG = config_data["DB"]

schema_text = load_schema()
allowed_tables = set(t.lower() for t in extract_table_names(schema_text))

def is_modifying_question(question: str) -> bool:
    # hiện tại modify keywords đang hard code chỉ là một danh sách đơn giản, có thể mở rộng sau này
    # phương pháp mở rộng có thể là sử dụng mô hình AI để phân tích câu hỏi nhưng hiện tại sẽ tốn phí nên chưa triển khai
    modifying_keywords = [
        "thêm", "tạo", "chèn", "insert", "cập nhật", "update", "xóa", "chỉnh sửa", "delete", "drop", "remove", "alter", "edit", "drop"
    ]
    question_lower = question.lower()
    return any(keyword in question_lower for keyword in modifying_keywords)

@app.route("/ask", methods=["POST"])
def handle_question():
    data = request.get_json()
    question = data.get("question", "")
    # user_id = data.get("user_id", "default")  # thêm user_id vào request PMS để tách session
    
    if not question:
        return jsonify({"error": "Missing question"}), 400

    if is_modifying_question(question):
        return {"error": "Câu hỏi mang tính chỉnh sửa dữ liệu. Không thực hiện."}
    
    try:
        # # 🔍 Kiểm tra câu hỏi tương tự
        # cached = find_similar_cached_response(user_id, question)
        # if cached:
        #     logging.info("✅ Dùng lại kết quả từ cache")
        #     response = generate_natural_language_response(question, cached["result"])
        #     return jsonify({
        #         "question": question,
        #         "sql_generated": cached["sql"],
        #         "results": cached["result"],
        #         "response": response,
        #         "cached": True
        #     })

        # 💡 Không có cache, tiếp tục như hiện tại
        ####### generated_sql = generate_sql_query(question, schema_text)
        # keyword -> related tables

        def guess_tables_from_question(question, keyword_mapping):
            """
            Trả về danh sách bảng có thể liên quan đến câu hỏi dựa trên keyword mapping
            """
            question_lower = question.lower()
            matched_tables = set()
            for keyword, tables in keyword_mapping.items():
                if keyword in question_lower:
                    matched_tables.update(tables)
            return list(matched_tables)
        # Tìm các bảng có thể liên quan đến câu hỏi
        relevant_tables = guess_tables_from_question(question, keyword_table_mapping)

# Nếu không đoán được bảng nào → fallback toàn bộ schema
        if not relevant_tables:
            logging.info("Không tìm thấy bảng liên quan, dùng toàn bộ schema")
            relevant_schema = schema_text
        else:
            logging.info(f"Các bảng liên quan đến câu hỏi: {relevant_tables}")
            relevant_schema = filter_schema_by_table_names(schema_text, relevant_tables)

        # Gọi Gemini sinh SQL từ schema rút gọn
        try:
            generated_sql = generate_sql_query(question, relevant_schema)
        except ValueError as ve:
            # Token limit exceeded
            logging.error(f"Token limit error: {str(ve)}")
            return jsonify({
                "error": "Câu hỏi quá phức tạp hoặc schema quá lớn. Vui lòng thử câu hỏi cụ thể hơn.",
                "error_type": "token_limit_exceeded",
                "details": str(ve)
            }), 400
        except Exception as e:
            # Other API errors
            logging.error(f"Gemini API error: {str(e)}")
            return jsonify({
                "error": "Có lỗi xảy ra khi xử lý câu hỏi. Vui lòng thử lại sau.",
                "error_type": "api_error"
            }), 500

        if not is_safe_sql(generated_sql):
            return jsonify({
                "error": "Chỉ câu hỏi an toàn được phép và chấp nhận câu hỏi SQL an toàn.",
                "sql_generated": generated_sql
            }), 400

        is_valid, forbidden = validate_tables_in_sql(generated_sql, allowed_tables)
        if not is_valid:
            return jsonify({
                "error": f"Query references tables not in schema: {', '.join(forbidden)}",
                "sql_generated": generated_sql
            }), 400

        conn = get_db_connection(DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute(generated_sql)
        results = cursor.fetchall()
        cursor.close()
        conn.close()

        try:
            natural_response = generate_natural_language_response(question, results)
        except Exception as e:
            logging.error(f"Error generating natural response: {str(e)}")
            # Fallback response if token issues
            natural_response = f"Tìm thấy {len(results)} kết quả cho câu hỏi của bạn. Dữ liệu có thể xem trong phần 'results'."

        # # 🧠 Lưu lại kết quả vào bộ nhớ
        # emb = embedding_model.encode(question, convert_to_tensor=True)
        # conversation_memory.setdefault(user_id, []).append({
        #     "question": question,
        #     "embedding": emb,
        #     "sql": generated_sql,
        #     "result": results
        # })

        return jsonify({
            "question": question,
            "sql_generated": generated_sql,
            "results": results,
            "response": natural_response,
            "cached": False
        })

    except Exception as e:
        logging.error(f"Error in /ask endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

# API RIÊNG CHO SERVER CHATBOT ĐỂ TỐI ƯU HIỆU SUẤT MÔ HÌNH AI
@app.route("/cache", methods=["GET"])
def view_cache():
    user_id = request.args.get("user_id", "default")
    history = conversation_memory.get(user_id, [])

    simplified = [
        {
            "question": item["question"],
            "sql": item["sql"],
            "num_results": len(item["result"])  # chỉ trả số lượng để tránh log quá nhiều
        }
        for item in history
    ]

    return jsonify({
        "user_id": user_id,
        "cached_questions": simplified,
        "total_cached": len(simplified)
    })



@app.route("/cache/clear", methods=["POST"])
def clear_cache():
    user_id = request.json.get("user_id", "default")
    conversation_memory[user_id] = []
    return jsonify({"message": f"Cache cleared for user {user_id}."})

@app.route("/token/info", methods=["GET"])
def get_token_info():
    """
    API để xem thông tin token limits và stats
    """
    stats = token_manager.get_token_stats()
    
    # Thêm thông tin về schema
    schema_tokens = token_manager.count_tokens(schema_text)
    
    return jsonify({
        "token_limits": stats,
        "schema_info": {
            "total_tokens": schema_tokens,
            "total_tables": len(allowed_tables),
            "schema_size_kb": len(schema_text) / 1024
        },
        "recommendations": {
            "max_question_tokens": stats["max_input_tokens"] - schema_tokens - 1000,
            "status": "healthy" if schema_tokens < stats["max_input_tokens"] * 0.7 else "warning"
        }
    })

@app.route("/timesheet-daily", methods=["POST"])
def analyze_timesheet_daily():
    """
    API để phân tích báo cáo hằng ngày và mapping với task trong hệ thống
    """
    try:
        data = request.get_json()
        system_tasks_text = data.get("system_tasks", "")
        daily_report = data.get("daily_report", "")
        
        if not system_tasks_text or not daily_report:
            return jsonify({
                "error": "Thiếu thông tin system_tasks hoặc daily_report"
            }), 400
        
        # Parse system tasks
        system_tasks = parse_tasks_from_system(system_tasks_text)
        logging.info(f"Parsed {len(system_tasks)} system tasks")
        
        # Parse daily report
        daily_efforts = parse_daily_report(daily_report)
        logging.info(f"Parsed {len(daily_efforts)} daily efforts")
        
        # Match tasks
        results, undefined_tasks = match_tasks_with_system_tasks(daily_efforts, system_tasks)
        
        return jsonify({
            "results": results,
            "undefined": undefined_tasks,
            "summary": {
                "total_system_tasks": len(system_tasks),
                "total_daily_efforts": len(daily_efforts),
                "matched_results": len(results),
                "undefined_tasks": len(undefined_tasks)
            }
        })
        
    except Exception as e:
        logging.error(f"Error in /timesheet-daily endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/timesheet-daily-ai", methods=["POST"])
def analyze_timesheet_daily_ai():
    """
    API sử dụng AI (Gemini) để phân tích báo cáo timesheet và mapping với task hệ thống
    """
    try:
        data = request.get_json()
        system_tasks_text = data.get("system_tasks", "")
        daily_report = data.get("daily_report", "")
        
        if not system_tasks_text or not daily_report:
            return jsonify({
                "error": "Thiếu thông tin system_tasks hoặc daily_report"
            }), 400
        
        # Prompt do user thiết kế
        prompt = f"""
Hãy phân tích báo cáo hằng ngày so với những task đang hiển thị trên hệ thống và trả về kết quả theo định dạng [id] - effort. 
Các task đang có trong hệ thống (định dạng ID - ProjectName - effort):
{system_tasks_text}
Nội dung báo cáo:
{daily_report}

Khi trả về kết quả trả về dạng JSON, không cần giải thích. Khi trả về kết quả dựa vào báo cáo hằng ngày và những task đang có trên hệ thống để trả về dạng ID - EFFORT. Nếu trong báo cáo ngày không có ghi effort của từng task thì lấy số giờ tổng thuộc về dự án chia đều cho các task cũng thuộc về dự án đó. Lưu ý effort là số giờ làm việc (h). Khi phân tích chỉ phân tích phần Actual không phân tích các phần khác. Các phần Other trong Actual cũng không cần phân tích. Với những task nào không xác định trả về cho tôi về dạng ProjectName - TaskName. Trả về ngày tháng năm trong nội dung báo cáo, ngày tháng năm lấy ở những dòng đầu tiên của báo cáo
Ví dụ trả về sẽ có dạng 
results = "221 - 2\n                  223 - 3". 
undifine = [
{{
"ProjectName": ''
"TaskName:": ''
"effort: "
}},
...]
date - ngày tháng năm trong nội dung báo cáo [yyyy-mm-dd]
"""
        
        # Gọi Gemini để sinh kết quả
        try:
            from gemini_ai import configure_gemini, generate_natural_language_response
            # Sử dụng hàm generate_natural_language_response để lấy kết quả dạng text
            # (hoặc có thể tạo hàm riêng nếu muốn tách biệt)
            # Ở đây ta dùng model trực tiếp để sinh ra kết quả
            import google.generativeai as genai
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt)
            raw = response.text.strip()
            # Tìm đoạn JSON trong kết quả trả về
            import re, json
            json_match = re.search(r'\{.*\}|\[.*\]', raw, re.DOTALL)
            if json_match:
                try:
                    result_json = json.loads(json_match.group(0))
                    return jsonify(result_json)
                except Exception:
                    pass
            # Nếu không parse được JSON, trả về raw text
            return jsonify({"raw": raw})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)