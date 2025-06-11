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
