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

def generate_natural_language_response(question, results, model_name="gemini-1.5-flash"):
    """
    Generate natural language response from SQL results.

    Sinh câu trả lời tự nhiên từ kết quả SQL.
    """
    if not results:
        return "Xin lỗi, tôi không tìm thấy thông tin phù hợp với câu hỏi của bạn. Bạn có thể thử hỏi lại theo cách khác không?"
    
    # Lấy tối đa 5 kết quả để có context tốt hơn
    sample = results[:5]
    
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
    )
    
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        result = response.text.strip()
        if not result:
            return "Xin lỗi, tôi gặp một chút vấn đề khi xử lý câu trả lời. Bạn có thể thử lại không?"
        return result
    except Exception as e:
        logging.error(f"Error generating natural response: {str(e)}")
        return "Xin lỗi, có lỗi xảy ra khi tạo câu trả lời. Vui lòng thử lại sau."
