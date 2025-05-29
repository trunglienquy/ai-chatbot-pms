from flask import Flask, request, jsonify
from flask_cors import CORS
import logging

from config import load_config
from gemini_ai import configure_gemini, query_model
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

@app.route("/ask", methods=["POST"])
def handle_question():
    data = request.get_json()
    question = data.get("question", "")
    if not question:
        return jsonify({"error": "Missing question"}), 400

    try:
        generated_sql = query_model(question, schema_text)

        if not is_safe_sql(generated_sql):
            return jsonify({
                "error": "Only SELECT queries are allowed",
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

        return jsonify({
            "question": question,
            "sql_generated": generated_sql,
            "results": results
        })

    except Exception as e:
        logging.error(f"Error in /ask endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)