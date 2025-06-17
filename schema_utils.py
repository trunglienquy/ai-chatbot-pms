import re

def load_schema(file_path="table_sys.txt"):
    """
    Read all content from the file 

    Đọc toàn bộ nội dung từ file
    """
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def extract_table_names(schema_text):
    """
    Extract table name from schema of type format:
    Table table_name

    Trích xuất tên bảng từ schema có định dạng:
    Table table_name
    """
    return set(re.findall(r"^Table\s+([a-zA-Z0-9_]+)", schema_text, flags=re.MULTILINE))

def extract_tables_from_sql(sql):
    """
    Extract table names used in SQL from the FROM/JOIN clauses.

    Trích xuất tên bảng được sử dụng trong SQL từ các mệnh đề FROM/JOIN.
    """
    return set(re.findall(r"(?i)(?:FROM|JOIN)\s+([a-zA-Z0-9_]+)", sql))

def validate_tables_in_sql(sql, allowed_tables):
    """
    Compare tables appearing in SQL with the allowed table list.

    So sánh các bảng xuất hiện trong SQL với danh sách bảng được cho phép.
    """
    tables_in_sql = extract_tables_from_sql(sql)
    forbidden = tables_in_sql - allowed_tables
    if forbidden:
        return False, forbidden
    return True, None

def filter_schema_by_table_names(schema_text, table_names):
    """
    Chỉ lấy phần schema của các bảng liên quan.
    
    :param schema_text: toàn bộ schema dưới dạng text
    :param table_names: danh sách tên bảng cần lọc
    :return: đoạn schema đã lọc
    """
    table_blocks = schema_text.split("Table ")
    filtered = []

    for block in table_blocks:
        if not block.strip():
            continue
        header_line = block.splitlines()[0]
        table_name = header_line.strip().split()[0]
        if table_name in table_names:
            filtered.append("Table " + block.strip())

    return "\n\n".join(filtered)

def extract_possible_table_names(question, all_tables):
    """
    Tìm các bảng có thể liên quan đến câu hỏi dựa vào tên bảng xuất hiện trong câu hỏi.
    So khớp đơn giản theo từ khóa.
    """
    lower_question = question.lower()
    return [table for table in all_tables if table.lower() in lower_question]
