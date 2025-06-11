import google.generativeai as genai
import re
import logging

def configure_gemini(api_key):
    """
    Configure the Gemini API with the provided API key.
    
    Cấu hình API Gemini với khóa API được cung cấp.
    """
    genai.configure(api_key=api_key)

def generate_sql_query(question, schema, model_name="gemini-1.5-flash"):
    """
    Generate SQL query from natural language question using the provided schema.

    Sinh câu truy vấn SQL từ câu hỏi tự nhiên sử dụng schema đã cung cấp.
    """
    prompt = f"""
You are an expert in SQL and assistant for Property Management System (PMS). Based on the following schema:

SECURITY RULES (CRITICAL):
- Generate ONLY SELECT queries for data retrieval
- NO data modification operations allowed
- NO system functions or administrative queries
- Single query only, no chaining with semicolons

SCHEMA:
{schema}

BUSINESS RULES:
1. Always use CONCAT(firstname, ' ', lastname) AS fullname for displaying and filtering ONLY person names. When filtering by a name, apply conditions on the full name using LOWER(CONCAT(firstname, ' ', lastname)) LIKE '%value%'
2. Exclude sensitive fields: password, ssn, bank_account, internal_notes
3. When filtering by text (e.g., project names), if the value is likely a partial match or pattern (e.g., from user questions), use LIKE '%value%' instead of = 'value'.
4. Use `LOWER(column)` with `LIKE` to ensure case-insensitive matching
5. If the question includes numeric conditions (e.g., greater than, top N, totals), translate it using appropriate aggregate/filtering operators
6. When the user mentions a project name or partial name, search using LOWER(name) with LIKE '%value%' instead of using project ID or subqueries.

QUERY STANDARDS:
Write a single optimized MySQL SELECT query that answers the following user question:
1. Limit to 10 results maximum unless aggregation (e.g., SUM, COUNT) is used
2. Do not select attribute id, created_at, updated_at, or any other attribute that is not useful for the user.
3. Use proper JOINs for related data
4. The question may include pattern matching (e.g., using LIKE with wildcards), filtering, sorting, or joining multiple tables.
5. Always use proper SQL syntax. When using LIKE, include appropriate wildcards (e.g., % or _) if needed for pattern matching.
6. When generating SQL query only use atttribute that is in the schema.

USER QUESTION: "{question}"

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

def generate_natural_language_response(question, results, model_name="gemini-1.5-flash", max_token=150):
    """
    Generate natural language response from SQL results.

    Sinh câu trả lời tự nhiên từ kết quả SQL.
    """
    if not results:
        return "Xin lỗi, tôi không tìm thấy thông tin phù hợp với câu hỏi của bạn. Bạn có thể thử hỏi lại theo cách khác không?"
    
    # Lấy tối đa 5 kết quả để có context tốt hơn
    sample = results[:10]
    
    prompt = (
        f"Bạn là một trợ lý AI thân thiện và chuyên nghiệp. Hãy trả lời câu hỏi của người dùng một cách tự nhiên và dễ hiểu bằng tiếng Việt.\n\n"
        f"Câu hỏi của người dùng: {question}\n\n"
        f"Dữ liệu tìm được: {sample}\n\n"
        "Hãy trả lời theo các nguyên tắc sau:\n"
        "1. Sử dụng ngôn ngữ tự nhiên, thân thiện\n"
        "2. Tổ chức thông tin một cách logic và dễ hiểu\n"
        "3. Nếu có nhiều kết quả, hãy tóm tắt và nhấn mạnh thông tin quan trọng\n"
        "4. Nếu cần thiết, hãy thêm các từ nối để câu trả lời mạch lạc hơn\n"
        "5. Tránh lặp lại câu hỏi trong câu trả lời\n"
        "6. Giới hạn câu trả lời trong khoảng 150 từ\n"
    )
    
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt, generation_config={"max_output_tokens": max_token})
        result = response.text.strip()
        if not result:
            return "Xin lỗi, tôi gặp một chút vấn đề khi xử lý câu trả lời. Bạn có thể thử lại không?"
        return result
    except Exception as e:
        logging.error(f"Error generating natural response: {str(e)}")
        return "Xin lỗi, có lỗi xảy ra khi tạo câu trả lời. Vui lòng thử lại sau."
