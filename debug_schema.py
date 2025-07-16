#!/usr/bin/env python3
"""
Debug schema validation issues
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from schema_utils import load_schema, extract_table_names, extract_tables_from_sql, validate_tables_in_sql

def debug_schema_validation():
    """Debug schema validation"""
    print("🔍 Debugging Schema Validation Issues\n")
    
    # Load schema và extract tables
    schema_text = load_schema()
    allowed_tables = set(t.lower() for t in extract_table_names(schema_text))
    
    print(f"📊 Total tables in schema: {len(allowed_tables)}")
    print(f"🔤 Sample allowed tables: {list(allowed_tables)[:10]}")
    print()
    
    # Test với câu SQL từ log
    test_sqls = [
        "SELECT t1.name FROM teams AS t1 JOIN members AS t2 ON t1.id = t2.team_id WHERE t2.firstname = 'Sáť­'",
        "SELECT SUM(T1.plan_effort) AS total_effort FROM plan_efforts AS T1 INNER JOIN projects AS T2 ON T1.project_id = T2.id",
        "SELECT m.firstname, m.lastname FROM projects p JOIN members m ON p.member_id = m.id WHERE p.name = 'MyPage'"
    ]
    
    for i, sql in enumerate(test_sqls, 1):
        print(f"🧪 Test SQL {i}:")
        print(f"SQL: {sql}")
        
        # Extract tables từ SQL
        tables_in_sql = extract_tables_from_sql(sql)
        print(f"Tables found in SQL: {tables_in_sql}")
        
        # Validate
        is_valid, forbidden = validate_tables_in_sql(sql, allowed_tables)
        print(f"Valid: {is_valid}")
        if not is_valid:
            print(f"❌ Forbidden tables: {forbidden}")
            # Check if table exists with different case
            for table in forbidden:
                if table.lower() in allowed_tables:
                    print(f"   ℹ️  '{table}' exists as '{table.lower()}' in schema")
                else:
                    print(f"   ❌ '{table}' not found in schema at all")
        print()
    
    # Kiểm tra vài bảng cụ thể
    check_tables = ['teams', 'members', 'projects', 'plan_efforts']
    print("🔍 Checking specific tables:")
    for table in check_tables:
        exists = table.lower() in allowed_tables
        print(f"  {table}: {'✅ EXISTS' if exists else '❌ NOT FOUND'}")
    
    print()
    print("📝 All allowed tables:")
    for table in sorted(allowed_tables):
        print(f"  - {table}")

if __name__ == "__main__":
    debug_schema_validation()
