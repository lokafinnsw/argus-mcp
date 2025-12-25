"""
Prompt templates and language-specific hints
"""

import os
from typing import Optional

# ============================================================================
# LANGUAGE-SPECIFIC HINTS
# ============================================================================

LANGUAGE_HINTS = {
    ".py": """
**Python-специфичные проверки:**
- PEP 8 style guide compliance
- Type hints (PEP 484) для всех функций
- Async/await patterns корректность
- Context managers (with statement)
- Exception handling best practices
- List comprehensions vs loops
- f-strings vs format()
""",
    ".js": """
**JavaScript-специфичные проверки:**
- ESLint rules compliance
- Async/await vs Promises
- Null/undefined safety
- Arrow functions vs function declarations
- Destructuring patterns
- Module imports (ES6)
- Event loop understanding
""",
    ".ts": """
**TypeScript-специфичные проверки:**
- Strict type checking
- Interface vs Type definitions
- Generic types usage
- Enum vs const enum
- Non-null assertions (!)
- Type guards and narrowing
- Utility types (Partial, Pick, Omit)
""",
    ".vue": """
**Vue.js-специфичные проверки:**
- Composition API vs Options API
- Reactivity patterns (ref, reactive, computed)
- Props validation and types
- Emits declaration
- Lifecycle hooks usage
- Template syntax correctness
- Script setup best practices
""",
    ".jsx": """
**React JSX-специфичные проверки:**
- Component naming (PascalCase)
- Hooks rules (useEffect, useState)
- Props destructuring
- Key prop in lists
- Event handlers naming
- Conditional rendering patterns
- Fragment usage
""",
    ".tsx": """
**React TypeScript-специфичные проверки:**
- Component props typing
- Generic components
- Event types (React.MouseEvent)
- Ref types (React.RefObject)
- Children type (React.ReactNode)
- Hook types (useState<T>)
""",
    ".go": """
**Go-специфичные проверки:**
- Error handling patterns
- Goroutines and channels
- Defer statements usage
- Interface implementation
- Pointer vs value receivers
- Package naming conventions
- Context usage
""",
    ".rs": """
**Rust-специфичные проверки:**
- Ownership and borrowing
- Lifetime annotations
- Error handling (Result, Option)
- Pattern matching exhaustiveness
- Trait implementations
- Unsafe code justification
- Clippy warnings
""",
    ".java": """
**Java-специфичные проверки:**
- SOLID principles
- Exception handling hierarchy
- Stream API usage
- Optional usage
- Access modifiers correctness
- Generics type safety
- Resource management (try-with-resources)
""",
    ".php": """
**PHP-специфичные проверки:**
- PSR standards compliance
- Type declarations (PHP 7+)
- Null coalescing operator
- Array functions vs loops
- PDO prepared statements
- Namespace usage
- Error handling (try-catch)
"""
}

def get_language_hint(file_path: str) -> str:
    """Получает language hint по расширению файла"""
    if not file_path:
        return ""
    
    ext = os.path.splitext(file_path)[1].lower()
    return LANGUAGE_HINTS.get(ext, "")

# ============================================================================
# BASE PROMPTS
# ============================================================================

SYSTEM_PROMPT_SINGLE = """ROLE: Senior QA Engineer & Security Auditor.
GOAL: Perform a rigorous code review with a "Zero-Trust" mindset.
LANGUAGE: Respond in the same language as the user's request (English, Russian, Chinese, etc.).

INSTRUCTIONS:
1. ANALYZE the code for Logic Errors, Security (OWASP), Performance, and Maintainability.
2. CATEGORIZE findings strictly into three levels:
   - "Must Fix" (Critical bugs, security flaws, crashes).
   - "Should Fix" (Logic gaps, risky patterns, poor UX).
   - "Suggestions" (Code style, optimizations, best practices).
3. BE SPECIFIC: Quote the exact file path and line number or the specific logic error.

{language_hint}

{stack_info}

OUTPUT FORMAT (Strict Markdown):

### ❌ Must Fix
- **`path/to/file:line`** (or **Error Type**): Concise explanation of why this is critical and how it breaks the system.

### 🟡 Should Fix
- **`path/to/file:line`**: Explanation of the issue (e.g., TODOs, missing edge case handling).

### 🟢 Suggestions
- **`path/to/file:line`**: Improvement tip (e.g., "Use .capitalize() instead of string slicing").

RULES:
- If a category is empty, omit it.
- Keep explanations professional and concise.
- Use the exact emojis provided.
- Each issue MUST contain exact file path and line number in format `file_path:line`."""

SYSTEM_PROMPT_MULTIPLE = """ROLE: Senior QA Engineer & Security Auditor.
GOAL: Perform a rigorous code review with a "Zero-Trust" mindset for MULTIPLE FILES.
LANGUAGE: Respond in the same language as the user's request (English, Russian, Chinese, etc.).

CRITICAL FOCUS (Multi-File Review):
1. **Cross-file dependencies** - Check consistency between files
2. **Forgotten updates** - If API changed in one file, verify all calls are updated
3. **Imports** - Verify new functions/classes are imported where used
4. **Data types** - Check type compatibility between frontend and backend
5. **Architectural patterns** - Verify compliance with overall architecture

INSTRUCTIONS:
1. ANALYZE the code for Logic Errors, Security (OWASP), Performance, and Maintainability.
2. CATEGORIZE findings strictly into three levels:
   - "Must Fix" (Critical bugs, security flaws, crashes, cross-file inconsistencies).
   - "Should Fix" (Logic gaps, risky patterns, poor UX, missing imports).
   - "Suggestions" (Code style, optimizations, best practices).
3. BE SPECIFIC: Quote the exact file path and line number or the specific logic error.

{language_hints}

{stack_info}

OUTPUT FORMAT (Strict Markdown):

### ❌ Must Fix
- **`path/to/file:line`** (or **Error Type**): Concise explanation of why this is critical and how it breaks the system.

### 🟡 Should Fix
- **`path/to/file:line`**: Explanation of the issue (e.g., TODOs, missing edge case handling).

### 🟢 Suggestions
- **`path/to/file:line`**: Improvement tip (e.g., "Use .capitalize() instead of string slicing").

RULES:
- If a category is empty, omit it.
- Keep explanations professional and concise.
- Use the exact emojis provided.
- Each issue MUST contain exact file path and line number in format `file_path:line`."""

# ============================================================================
# PROMPT BUILDERS
# ============================================================================

def format_stack_info(project_stack: Optional[dict]) -> str:
    """Форматирует информацию о стеке технологий"""
    if not project_stack:
        return ""
    
    parts = ["**PROJECT STACK:**"]
    
    if project_stack.get("framework"):
        parts.append(f"- Framework: {project_stack['framework']}")
    
    if project_stack.get("frontend"):
        parts.append(f"- Frontend: {project_stack['frontend']}")
    
    if project_stack.get("backend"):
        parts.append(f"- Backend: {project_stack['backend']}")
    
    if project_stack.get("database"):
        parts.append(f"- Database: {project_stack['database']}")
    
    if project_stack.get("conventions"):
        parts.append(f"- Code Conventions: {project_stack['conventions']}")
    
    if project_stack.get("architecture"):
        parts.append(f"- Architecture: {project_stack['architecture']}")
    
    if len(parts) > 1:  # Если есть хоть одно поле
        return "\n".join(parts)
    
    return ""


def build_system_prompt(mode: str, file_paths: list[str] = None, project_stack: Optional[dict] = None) -> str:
    """Строит system prompt в зависимости от режима"""
    
    # Форматируем stack информацию
    stack_info = format_stack_info(project_stack)
    
    if mode in ["diff", "multiple"]:
        # Собираем language hints для всех файлов
        hints = []
        if file_paths:
            seen_exts = set()
            for path in file_paths:
                ext = os.path.splitext(path)[1].lower()
                if ext not in seen_exts and ext in LANGUAGE_HINTS:
                    hints.append(LANGUAGE_HINTS[ext])
                    seen_exts.add(ext)
        
        language_hints = "\n".join(hints) if hints else ""
        return SYSTEM_PROMPT_MULTIPLE.format(
            language_hints=language_hints,
            stack_info=stack_info
        )
    
    else:  # single file
        language_hint = ""
        if file_paths and len(file_paths) > 0:
            language_hint = get_language_hint(file_paths[0])
        
        return SYSTEM_PROMPT_SINGLE.format(
            language_hint=language_hint,
            stack_info=stack_info
        )


def detect_language(text: str) -> str:
    """Detects language of text (simple heuristic based on character ranges)"""
    if not text:
        return "en"
    
    # Count Cyrillic characters
    cyrillic_count = sum(1 for c in text if '\u0400' <= c <= '\u04FF')
    # Count Chinese characters
    chinese_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    # Total alphabetic characters
    alpha_count = sum(1 for c in text if c.isalpha())
    
    if alpha_count == 0:
        return "en"
    
    cyrillic_ratio = cyrillic_count / alpha_count
    chinese_ratio = chinese_count / alpha_count
    
    if cyrillic_ratio > 0.3:
        return "ru"
    elif chinese_ratio > 0.3:
        return "zh"
    else:
        return "en"


def build_user_message(task_context: str, session_changes: str, code_content: str) -> str:
    """Builds user message in detected language"""
    
    # Detect language from task_context
    lang = detect_language(task_context)
    
    if lang == "ru":
        return f"""## Задача
{task_context}

## Изменения в сессии
{session_changes or "Не указаны"}

{code_content}

Проверь код и дай вердикт."""
    
    elif lang == "zh":
        return f"""## 任务
{task_context}

## 会话更改
{session_changes or "未指定"}

{code_content}

请检查代码并给出评审意见。"""
    
    else:  # English (default)
        return f"""## Task
{task_context}

## Session Changes
{session_changes or "Not specified"}

{code_content}

Review the code and provide your verdict."""
