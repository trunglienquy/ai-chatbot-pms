#!/usr/bin/env python3
"""
Test script cho Token Management System
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from token_utils import token_manager

def test_token_counting():
    """Test basic token counting"""
    print("🧪 Testing Token Counting...")
    
    test_cases = [
        "Hello world",
        "Tôi muốn tìm dự án của khách hàng ABC",
        "SELECT * FROM projects WHERE name LIKE '%test%'",
        "",
        "A" * 1000  # Long text
    ]
    
    for text in test_cases:
        tokens = token_manager.count_tokens(text)
        print(f"  Text: '{text[:50]}{'...' if len(text) > 50 else ''}'")
        print(f"  Tokens: {tokens}")
        print(f"  Characters: {len(text)}")
        print()

def test_schema_truncation():
    """Test schema truncation"""
    print("🧪 Testing Schema Truncation...")
    
    # Create a mock large schema
    large_schema = """
Table projects
Columns:
- id: int(10)
- name: varchar(191)
- description: text
- start_date: datetime
- end_date: datetime

Table members
Columns:
- id: int(10)
- firstname: varchar(100)
- lastname: varchar(100)
- email: varchar(191)
- role: varchar(50)

Table tasks
Columns:
- id: int(10)
- project_id: int(11)
- member_id: int(11)
- title: varchar(255)
- description: text
- status: varchar(50)
- priority: int(5)
- created_at: timestamp
- updated_at: timestamp
""" * 10  # Multiply to make it large
    
    question = "Tìm tất cả dự án của khách hàng ABC"
    
    original_tokens = token_manager.count_tokens(large_schema)
    print(f"Original schema tokens: {original_tokens}")
    
    truncated = token_manager.truncate_schema(large_schema, question, max_tokens=2000)
    truncated_tokens = token_manager.count_tokens(truncated)
    
    print(f"Truncated schema tokens: {truncated_tokens}")
    print(f"Reduction: {original_tokens - truncated_tokens} tokens")
    print()

def test_prompt_validation():
    """Test prompt validation"""
    print("🧪 Testing Prompt Validation...")
    
    short_prompt = "Hello, how are you?"
    long_prompt = "A" * 50000  # Very long prompt
    
    # Test short prompt
    is_valid, error = token_manager.validate_prompt(short_prompt)
    print(f"Short prompt valid: {is_valid}")
    if not is_valid:
        print(f"Error: {error}")
    
    # Test long prompt
    is_valid, error = token_manager.validate_prompt(long_prompt)
    print(f"Long prompt valid: {is_valid}")
    if not is_valid:
        print(f"Error: {error}")
    print()

def test_token_stats():
    """Test token statistics"""
    print("🧪 Testing Token Stats...")
    
    stats = token_manager.get_token_stats()
    print(f"Token stats: {stats}")
    print()

def main():
    print("🚀 Starting Token Management Tests\n")
    
    try:
        test_token_counting()
        test_schema_truncation()
        test_prompt_validation()
        test_token_stats()
        
        print("✅ All tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
