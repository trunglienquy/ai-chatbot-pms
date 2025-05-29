import re

"""
Check if the SQL query is a safe SELECT statement
"""

"""
Kiểm tra câu SQL có phải là câu lệnh SELECT an toàn
"""
def is_safe_sql(sql):
    return re.match(r"(?i)^\s*SELECT\s+", sql.strip()) is not None
