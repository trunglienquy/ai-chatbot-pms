import google.generativeai as genai
import re
import logging
from token_utils import token_manager

def configure_gemini(api_key):
    """
    Configure the Gemini API with the provided API key.
    
    Cấu hình API Gemini với khóa API được cung cấp.
    """
    genai.configure(api_key=api_key)

def generate_sql_query(question, schema, model_name="gemini-1.5-flash", max_input_tokens=8000):
    """
    Generate SQL query from natural language question using the provided schema.
    
    Args:
        question: User's natural language question
        schema: Database schema text
        model_name: Gemini model name
        max_input_tokens: Maximum input tokens allowed
    
    Returns:
        Generated SQL query string
    
    Raises:
        ValueError: If prompt exceeds token limit
    """
    
    # 🔍 Token validation và optimization
    logging.info(f"Original schema tokens: {token_manager.count_tokens(schema)}")
    
    # Truncate schema if needed
    optimized_schema = token_manager.truncate_schema(schema, question, max_input_tokens - 1000)
    
    prompt = f"""
You are an expert in SQL and assistant for Property Management System (PMS). Based on the following schema:

SECURITY RULES (CRITICAL):
- Generate ONLY SELECT queries for data retrieval
- NO data modification operations allowed
- NO system functions or administrative queries
- Single query only, no chaining with semicolons

SCHEMA:
{optimized_schema}

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
    
    # 🔍 Validate prompt trước khi gọi API
    is_valid, error_msg = token_manager.validate_prompt(prompt)
    if not is_valid:
        logging.error(f"Prompt validation failed: {error_msg}")
        raise ValueError(f"Token limit exceeded: {error_msg}")
    
    prompt_tokens = token_manager.count_tokens(prompt)
    logging.info(f"Final prompt tokens: {prompt_tokens}")
    
    logging.info(f"Generated SQL prompt: {prompt}")
    model = genai.GenerativeModel(model_name)
    
    try:
        response = model.generate_content(prompt)
        raw = response.text.strip()
        logging.info(f"Raw model output: {raw}")
        
        # Clean the output to remove any markdown formatting
        cleaned = re.sub(r"^```sql\s*|```$", "", raw, flags=re.IGNORECASE).strip()
        logging.info(f"Cleaned SQL: {cleaned}")
        return cleaned
        
    except Exception as e:
        logging.error(f"Error calling Gemini API: {str(e)}")
        raise e

def generate_natural_language_response(question, results, model_name="gemini-1.5-flash", max_token=150, max_input_tokens=4000):
    """
    Generate natural language response from SQL results.
    
    Args:
        question: User's original question
        results: SQL query results
        model_name: Gemini model name
        max_token: Maximum output tokens
        max_input_tokens: Maximum input tokens
    
    Returns:
        Natural language response string
    """
    if not results:
        return "Xin lỗi, tôi không tìm thấy thông tin phù hợp với câu hỏi của bạn. Bạn có thể thử hỏi lại theo cách khác không?"
    
    # 🔍 Optimize results để fit token limit
    optimized_results = token_manager.optimize_results_for_response(results, question, max_input_tokens - 1000)
    
    if len(optimized_results) < len(results):
        logging.info(f"Results optimized: {len(results)} -> {len(optimized_results)} items")
    
    # Giới hạn số lượng kết quả để tránh quá dài
    sample = optimized_results[:10]
    
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
    
    # 🔍 Validate prompt trước khi gọi API
    is_valid, error_msg = token_manager.validate_prompt(prompt)
    if not is_valid:
        logging.error(f"Response prompt validation failed: {error_msg}")
        return "Xin lỗi, dữ liệu quá lớn để xử lý. Vui lòng thử câu hỏi cụ thể hơn."
    
    prompt_tokens = token_manager.count_tokens(prompt)
    logging.info(f"Response prompt tokens: {prompt_tokens}")
    
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
