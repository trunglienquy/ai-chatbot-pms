import google.generativeai as genai
import re
import logging

def configure_gemini(api_key):
    """
    Configure the Gemini API with the provided API key.
    
    Cấu hình API Gemini với khóa API được cung cấp.
    """
    genai.configure(api_key=api_key)

def query_model(question, schema, model_name="gemini-1.5-flash"):
    """
    Send a prompt to the Gemini model to generate a SQL query based on the provided schema and question.

    Gửi một prompt đến mô hình Gemini để tạo câu truy vấn SQL dựa trên schema và câu hỏi đã cung cấp.
    """
    prompt = f"""
You are an expert in SQL. Based on the following schema:

{schema}

Write a single optimized MySQL SELECT query that answers the following user question:
The question may include pattern matching (e.g., using LIKE with wildcards), filtering, sorting, or joining multiple tables.

Always use proper SQL syntax. When using LIKE, include appropriate wildcards (e.g., % or _) if needed for pattern matching.

"{question}"

Only return the SQL query. No explanation, no markdown, no extra text.
"""
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(prompt)
    raw = response.text.strip()
    logging.info(f"Raw model output: {raw}")
    # Clean the output to remove any markdown formatting
    cleaned = re.sub(r"^```sql\s*|```$", "", raw, flags=re.IGNORECASE).strip()
    logging.info(f"Cleaned SQL: {cleaned}")
    return cleaned
