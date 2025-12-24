"""
Input validation module
"""

from typing import Tuple, Optional
from config import MAX_CODE_SIZE, MAX_FILES_COUNT, MAX_TOKENS_ESTIMATE


class ValidationError(Exception):
    """Custom exception for validation errors"""
    pass


def estimate_tokens(text: str) -> int:
    """Примерная оценка количества токенов (1 токен ≈ 4 символа)"""
    return len(text) // 4


def validate_code_size(code: str, max_size: int = MAX_CODE_SIZE) -> Tuple[bool, str]:
    """Валидирует размер кода"""
    size = len(code)
    if size > max_size:
        return False, f"Code too large: {size} bytes (max {max_size} bytes)"
    
    tokens = estimate_tokens(code)
    if tokens > MAX_TOKENS_ESTIMATE:
        return False, f"Code too large: ~{tokens} tokens (max {MAX_TOKENS_ESTIMATE} tokens)"
    
    return True, ""


def validate_diff(diff: str) -> Tuple[bool, str]:
    """Валидирует git diff"""
    if not diff.strip():
        return False, "Diff is empty"
    
    # Проверяем что это похоже на git diff
    if not any(line.startswith('diff --git') for line in diff.split('\n')):
        return False, "Invalid diff format (expected git diff output)"
    
    return validate_code_size(diff)


def validate_files(files: list) -> Tuple[bool, str]:
    """Валидирует массив файлов"""
    if not files:
        return False, "Files array is empty"
    
    if len(files) > MAX_FILES_COUNT:
        return False, f"Too many files: {len(files)} (max {MAX_FILES_COUNT})"
    
    total_size = 0
    for i, file_info in enumerate(files):
        # Проверяем обязательные поля
        if not isinstance(file_info, dict):
            return False, f"File #{i} is not a dictionary"
        
        if "path" not in file_info:
            return False, f"File #{i} missing 'path' field"
        
        if "content" not in file_info and "diff" not in file_info:
            return False, f"File #{i} missing 'content' or 'diff' field"
        
        # Считаем общий размер
        content = file_info.get("content", "")
        diff = file_info.get("diff", "")
        total_size += len(content) + len(diff)
    
    if total_size > MAX_CODE_SIZE * 2:  # Для multiple files даём больше места
        return False, f"Total files size too large: {total_size} bytes"
    
    return True, ""


def validate_arguments(arguments: dict) -> Tuple[bool, str]:
    """Валидирует все аргументы запроса"""
    
    # Проверяем что передан хотя бы один из: code, diff, files
    has_code = "code" in arguments and arguments["code"]
    has_diff = "diff" in arguments and arguments["diff"]
    has_files = "files" in arguments and arguments["files"]
    
    if not (has_code or has_diff or has_files):
        return False, "No code provided. Use 'code', 'diff', or 'files' parameter"
    
    # Валидируем в зависимости от режима
    if has_code:
        valid, error = validate_code_size(arguments["code"])
        if not valid:
            return False, f"[Single File] {error}"
    
    if has_diff:
        valid, error = validate_diff(arguments["diff"])
        if not valid:
            return False, f"[Git Diff] {error}"
    
    if has_files:
        valid, error = validate_files(arguments["files"])
        if not valid:
            return False, f"[Multiple Files] {error}"
    
    # Проверяем task_context
    if "task_context" not in arguments or not arguments["task_context"]:
        return False, "task_context is required"
    
    return True, ""


def sanitize_file_path(path: str) -> str:
    """Очищает путь к файлу от опасных символов"""
    # Убираем потенциально опасные символы
    dangerous_chars = ['..', '~', '$', '`', '|', ';', '&']
    for char in dangerous_chars:
        path = path.replace(char, '')
    
    return path.strip()
