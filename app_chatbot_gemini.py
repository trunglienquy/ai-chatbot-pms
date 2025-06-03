from flask import Flask, request, jsonify
from flask_cors import CORS
import logging

from config import load_config
from gemini_ai import configure_gemini, generate_sql_query, generate_natural_language_response
from db import get_db_connection
from schema_utils import load_schema, extract_table_names, extract_tables_from_sql, validate_tables_in_sql
from sql_utils import is_safe_sql

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
        "thêm", "tạo", "chèn", "insert", "cập nhật", "update", "xóa", "chỉnh sửa", "delete", "drop", "remove", "alter", "edit"
    ]
    question_lower = question.lower()
    return any(keyword in question_lower for keyword in modifying_keywords)

@app.route("/ask", methods=["POST"])
def handle_question():
    data = request.get_json()
    question = data.get("question", "")
    if not question:
        return jsonify({"error": "Missing question"}), 400
    if is_modifying_question(question):
        return {"error": "Câu hỏi mang tính chỉnh sửa dữ liệu. Không thực hiện."}

    try:
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

        return jsonify({
            "question": question,
            "sql_generated": generated_sql,
            "results": results,
            "response": natural_response
        })

    except Exception as e:
        logging.error(f"Error in /ask endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)