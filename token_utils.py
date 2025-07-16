import tiktoken
import logging
import re
from typing import Tuple, Optional

class TokenManager:
    """
    Quản lý token cho Gemini API calls
    """
    
    def __init__(self, model_name: str = "gpt-4"):
        """
        Initialize token manager
        
        Args:
            model_name: Tên model để đếm token (dùng gpt-4 để estimate cho Gemini)
        """
        try:
            self.encoder = tiktoken.encoding_for_model(model_name)
        except KeyError:
            # Fallback to cl100k_base if model not found
            self.encoder = tiktoken.get_encoding("cl100k_base")
        
        # Gemini 1.5 Flash limits
        self.MAX_INPUT_TOKENS = 8000  # Conservative limit
        self.MAX_OUTPUT_TOKENS = 2048
        
        logging.info(f"TokenManager initialized with max_input: {self.MAX_INPUT_TOKENS}, max_output: {self.MAX_OUTPUT_TOKENS}")
    
    def count_tokens(self, text: str) -> int:
        """
        Đếm số token trong text
        
        Args:
            text: Text cần đếm token
            
        Returns:
            Số lượng token
        """
        if not text:
            return 0
        
        try:
            tokens = self.encoder.encode(text)
            return len(tokens)
        except Exception as e:
            logging.error(f"Error counting tokens: {str(e)}")
            # Fallback: estimate 1 token = 4 characters
            return len(text) // 4
    
    def truncate_schema(self, schema: str, question: str, max_tokens: int = None) -> str:
        """
        Cắt ngắn schema nếu tổng token vượt quá giới hạn
        
        Args:
            schema: Schema text
            question: User question
            max_tokens: Max tokens cho schema (default: MAX_INPUT_TOKENS - question_tokens - prompt_overhead)
            
        Returns:
            Schema đã được cắt ngắn
        """
        if max_tokens is None:
            question_tokens = self.count_tokens(question)
            prompt_overhead = 1000  # Estimate for prompt template
            max_tokens = self.MAX_INPUT_TOKENS - question_tokens - prompt_overhead
        
        schema_tokens = self.count_tokens(schema)
        
        if schema_tokens <= max_tokens:
            logging.info(f"Schema tokens ({schema_tokens}) within limit ({max_tokens})")
            return schema
        
        logging.warning(f"Schema too long ({schema_tokens} tokens). Truncating to {max_tokens} tokens.")
        
        # Cắt theo từng table block
        table_blocks = schema.split("Table ")
        truncated_blocks = ["Table " + table_blocks[0]]  # Keep first block
        current_tokens = self.count_tokens(truncated_blocks[0])
        
        for block in table_blocks[1:]:
            if not block.strip():
                continue
                
            table_block = "Table " + block
            block_tokens = self.count_tokens(table_block)
            
            if current_tokens + block_tokens > max_tokens:
                logging.info(f"Truncated schema at {len(truncated_blocks)} tables")
                break
            
            truncated_blocks.append(table_block)
            current_tokens += block_tokens
        
        truncated_schema = "\n\n".join(truncated_blocks)
        final_tokens = self.count_tokens(truncated_schema)
        logging.info(f"Final schema tokens: {final_tokens}")
        
        return truncated_schema
    
    def validate_prompt(self, prompt: str) -> Tuple[bool, str]:
        """
        Validate prompt trước khi gọi API
        
        Args:
            prompt: Prompt cần validate
            
        Returns:
            (is_valid, error_message)
        """
        if not prompt:
            return False, "Empty prompt"
        
        token_count = self.count_tokens(prompt)
        
        if token_count > self.MAX_INPUT_TOKENS:
            return False, f"Prompt too long: {token_count} tokens (max: {self.MAX_INPUT_TOKENS})"
        
        if token_count > self.MAX_INPUT_TOKENS * 0.9:  # Warning at 90%
            logging.warning(f"Prompt near token limit: {token_count}/{self.MAX_INPUT_TOKENS}")
        
        return True, ""
    
    def optimize_results_for_response(self, results: list, question: str, max_tokens: int = None) -> list:
        """
        Tối ưu kết quả để fit trong token limit cho natural language response
        
        Args:
            results: Kết quả từ database
            question: User question
            max_tokens: Max tokens cho results data
            
        Returns:
            Optimized results list
        """
        if not results:
            return results
        
        if max_tokens is None:
            question_tokens = self.count_tokens(question)
            prompt_overhead = 500  # Estimate for response prompt template
            max_tokens = self.MAX_INPUT_TOKENS - question_tokens - prompt_overhead
        
        # Convert results to string để đếm token
        results_str = str(results)
        current_tokens = self.count_tokens(results_str)
        
        if current_tokens <= max_tokens:
            return results
        
        logging.warning(f"Results too long ({current_tokens} tokens). Truncating to fit {max_tokens} tokens.")
        
        # Cắt từ từ cho đến khi fit
        truncated_results = results.copy()
        while len(truncated_results) > 1:
            # Cắt bớt một nửa
            truncated_results = truncated_results[:len(truncated_results)//2]
            current_tokens = self.count_tokens(str(truncated_results))
            
            if current_tokens <= max_tokens:
                break
        
        logging.info(f"Truncated results from {len(results)} to {len(truncated_results)} items")
        return truncated_results
    
    def get_token_stats(self) -> dict:
        """
        Lấy thống kê token limits
        
        Returns:
            Dict chứa token limits info
        """
        return {
            "max_input_tokens": self.MAX_INPUT_TOKENS,
            "max_output_tokens": self.MAX_OUTPUT_TOKENS,
            "encoder_name": self.encoder.name if hasattr(self.encoder, 'name') else 'unknown'
        }

# Global instance
token_manager = TokenManager()
