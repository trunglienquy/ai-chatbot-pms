from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
from sentence_transformers import SentenceTransformer, util

from config import load_config
from gemini_ai import configure_gemini, generate_sql_query, generate_natural_language_response
from db import get_db_connection
from schema_utils import load_schema, extract_table_names, extract_tables_from_sql, validate_tables_in_sql
from sql_utils import is_safe_sql

conversation_memory = {}
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

def find_similar_cached_response(user_id, new_question, threshold=0.85):
    if user_id not in conversation_memory:
        return None
    
    new_embedding = embedding_model.encode(new_question, convert_to_tensor=True)
    for item in reversed(conversation_memory[user_id][-5:]):  # chỉ check 5 câu gần nhất
        sim = util.cos_sim(new_embedding, item['embedding'])[0][0].item()
        if sim > threshold:
            return item  # Trả lại kết quả cũ đã truy vấn
    
    return None


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
        generated_sql = generate_sql_query(question, schema_text)

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

        natural_response = generate_natural_language_response(question, results)

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




if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)