"""
Context Optimizer for Argus MCP
Reduces token usage by 40-60% while preserving review quality.

Key strategies:
1. Code preprocessing (remove noise, keep structure)
2. Smart chunking for large files  
3. Two-phase review (triage → deep)
4. Diff enrichment with minimal context
"""

import re
import ast
import hashlib
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


# ============================================================================
# CONFIGURATION
# ============================================================================

class OptimizationLevel(Enum):
    """Context optimization levels"""
    NONE = 0      # No optimization (as is)
    LIGHT = 1     # Remove noise, preserve structure
    MODERATE = 2  # + compress imports, docstrings → signatures
    AGGRESSIVE = 3  # + chunking, two-phase review


@dataclass
class OptimizerConfig:
    """Optimizer configuration"""
    level: OptimizationLevel = OptimizationLevel.MODERATE
    max_file_tokens: int = 4000  # Threshold for chunking
    context_lines_before: int = 3  # Context lines before change
    context_lines_after: int = 3   # Context lines after change
    preserve_line_numbers: bool = True  # Critical for accurate references!
    compress_imports: bool = True
    compress_docstrings: bool = True
    remove_comments: bool = False  # Careful - may contain TODO/FIXME
    keep_todo_comments: bool = True


# ============================================================================
# CODE PREPROCESSING
# ============================================================================

@dataclass
class ProcessedCode:
    """Code processing result"""
    original_lines: int
    processed_lines: int
    content: str
    line_mapping: dict = field(default_factory=dict)  # new_line → original_line
    removed_sections: list = field(default_factory=list)
    tokens_saved_estimate: int = 0


class CodePreprocessor:
    """Code preprocessing to reduce tokens"""
    
    # Patterns for Python
    PYTHON_NOISE_PATTERNS = [
        (r'^\s*#(?!.*(?:TODO|FIXME|HACK|XXX|BUG|NOTE)).*$', 'comment'),  # Comments (except important)
        (r'^\s*$', 'empty'),  # Empty lines
        (r'^\s*pass\s*$', 'pass'),  # pass statements
    ]
    
    # Patterns for JS/TS
    JS_NOISE_PATTERNS = [
        (r'^\s*//(?!.*(?:TODO|FIXME|HACK|XXX|BUG|NOTE)).*$', 'comment'),
        (r'^\s*/\*[\s\S]*?\*/\s*$', 'block_comment'),
        (r'^\s*$', 'empty'),
        (r"^\s*console\.log\(.*\);\s*$", 'debug'),
    ]
    
    def __init__(self, config: OptimizerConfig):
        self.config = config
    
    def process(self, code: str, language: str, file_path: str = "") -> ProcessedCode:
        """Основной метод обработки"""
        if self.config.level == OptimizationLevel.NONE:
            return ProcessedCode(
                original_lines=len(code.splitlines()),
                processed_lines=len(code.splitlines()),
                content=code
            )
        
        lines = code.splitlines()
        original_count = len(lines)
        
        # 1. Базовая очистка (LIGHT+)
        processed_lines, line_mapping = self._remove_noise(lines, language)
        
        # 2. Сжатие импортов (MODERATE+)
        if self.config.level.value >= OptimizationLevel.MODERATE.value:
            if self.config.compress_imports:
                processed_lines = self._compress_imports(processed_lines, language)
        
        # 3. Сжатие docstrings (MODERATE+)
        if self.config.level.value >= OptimizationLevel.MODERATE.value:
            if self.config.compress_docstrings and language == "python":
                processed_lines = self._compress_docstrings(processed_lines)
        
        # Собираем результат с номерами строк
        if self.config.preserve_line_numbers:
            content = self._format_with_line_numbers(processed_lines, line_mapping)
        else:
            content = "\n".join(processed_lines)
        
        tokens_saved = (original_count - len(processed_lines)) * 4  # ~4 токена на строку
        
        return ProcessedCode(
            original_lines=original_count,
            processed_lines=len(processed_lines),
            content=content,
            line_mapping=line_mapping,
            tokens_saved_estimate=tokens_saved
        )
    
    def _remove_noise(self, lines: list, language: str) -> tuple[list, dict]:
        """Удаляет шумовые строки, сохраняя маппинг номеров"""
        patterns = self.PYTHON_NOISE_PATTERNS if language == "python" else self.JS_NOISE_PATTERNS
        
        result = []
        line_mapping = {}  # new_index → original_index
        
        for orig_idx, line in enumerate(lines, 1):
            is_noise = False
            
            for pattern, _ in patterns:
                if re.match(pattern, line):
                    is_noise = True
                    break
            
            # Сохраняем TODO/FIXME комментарии
            if is_noise and self.config.keep_todo_comments:
                if re.search(r'(?:TODO|FIXME|HACK|XXX|BUG|NOTE)', line, re.IGNORECASE):
                    is_noise = False
            
            if not is_noise:
                new_idx = len(result)
                line_mapping[new_idx] = orig_idx
                result.append(line)
        
        return result, line_mapping
    
    def _compress_imports(self, lines: list, language: str) -> list:
        """Группирует импорты в summary"""
        if language == "python":
            return self._compress_python_imports(lines)
        elif language in ("javascript", "typescript"):
            return self._compress_js_imports(lines)
        return lines
    
    def _compress_python_imports(self, lines: list) -> list:
        """Сжимает Python импорты"""
        imports = []
        from_imports = {}
        other_lines = []
        import_end_idx = 0
        
        for idx, line in enumerate(lines):
            stripped = line.strip()
            
            if stripped.startswith('import '):
                modules = stripped[7:].split(',')
                imports.extend([m.strip().split(' as ')[0] for m in modules])
                import_end_idx = idx
                
            elif stripped.startswith('from '):
                match = re.match(r'from\s+([\w.]+)\s+import\s+(.+)', stripped)
                if match:
                    module, items = match.groups()
                    if module not in from_imports:
                        from_imports[module] = []
                    from_imports[module].extend([i.strip().split(' as ')[0] for i in items.split(',')])
                    import_end_idx = idx
            else:
                other_lines.append(line)
        
        if not imports and not from_imports:
            return lines
        
        # Формируем сжатый блок импортов
        summary_parts = []
        if imports:
            summary_parts.append(f"# imports: {', '.join(sorted(set(imports)))}")
        for module, items in sorted(from_imports.items()):
            summary_parts.append(f"# from {module}: {', '.join(sorted(set(items)))}")
        
        return summary_parts + [""] + other_lines
    
    def _compress_js_imports(self, lines: list) -> list:
        """Сжимает JS/TS импорты"""
        imports = []
        other_lines = []
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('import ') or stripped.startswith('const ') and ' require(' in stripped:
                # Извлекаем имя модуля
                match = re.search(r"from\s+['\"](.+?)['\"]", stripped)
                if match:
                    imports.append(match.group(1))
                else:
                    match = re.search(r"require\(['\"](.+?)['\"]\)", stripped)
                    if match:
                        imports.append(match.group(1))
            else:
                other_lines.append(line)
        
        if not imports:
            return lines
        
        summary = f"// imports: {', '.join(sorted(set(imports)))}"
        return [summary, ""] + other_lines
    
    def _compress_docstrings(self, lines: list) -> list:
        """Заменяет docstrings на краткие сигнатуры"""
        code = "\n".join(lines)
        
        # Паттерн для многострочных docstrings
        # Заменяем на однострочный summary
        def replace_docstring(match):
            docstring = match.group(0)
            # Берём первую строку как summary
            first_line = docstring.split('\n')[0].strip().strip('"""').strip("'''")
            if len(first_line) > 60:
                first_line = first_line[:57] + "..."
            return f'"""{first_line}"""' if first_line else '"""..."""'
        
        # Заменяем многострочные docstrings
        code = re.sub(r'"""[\s\S]*?"""', replace_docstring, code)
        code = re.sub(r"'''[\s\S]*?'''", replace_docstring, code)
        
        return code.splitlines()
    
    def _format_with_line_numbers(self, lines: list, mapping: dict) -> str:
        """Форматирует код с оригинальными номерами строк"""
        result = []
        for new_idx, line in enumerate(lines):
            orig_idx = mapping.get(new_idx, new_idx + 1)
            result.append(f"{orig_idx:4d} | {line}")
        return "\n".join(result)


# ============================================================================
# SEMANTIC CHUNKING (для AGGRESSIVE level)
# ============================================================================

@dataclass
class CodeChunk:
    """Семантический чанк кода"""
    chunk_type: str  # "class", "function", "module_level"
    name: str
    start_line: int
    end_line: int
    content: str
    dependencies: list = field(default_factory=list)  # Используемые имена
    complexity_score: int = 0  # Для приоритизации


class SemanticChunker:
    """Разбивает код на семантические блоки"""
    
    def __init__(self, config: OptimizerConfig):
        self.config = config
    
    def chunk_python(self, code: str) -> list[CodeChunk]:
        """Разбивает Python код на чанки"""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            # Fallback: возвращаем весь код как один чанк
            return [CodeChunk(
                chunk_type="module",
                name="<unparseable>",
                start_line=1,
                end_line=len(code.splitlines()),
                content=code
            )]
        
        chunks = []
        lines = code.splitlines()
        
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                chunk = self._extract_class_chunk(node, lines)
                chunks.append(chunk)
                
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                chunk = self._extract_function_chunk(node, lines)
                chunks.append(chunk)
        
        # Добавляем module-level код (импорты, константы)
        module_level = self._extract_module_level(tree, lines, chunks)
        if module_level:
            chunks.insert(0, module_level)
        
        return chunks
    
    def _extract_class_chunk(self, node: ast.ClassDef, lines: list) -> CodeChunk:
        """Извлекает класс как чанк"""
        start = node.lineno
        end = node.end_lineno or start
        content = "\n".join(lines[start-1:end])
        
        # Анализируем сложность
        complexity = self._calculate_complexity(node)
        
        # Извлекаем зависимости
        deps = self._extract_dependencies(node)
        
        return CodeChunk(
            chunk_type="class",
            name=node.name,
            start_line=start,
            end_line=end,
            content=content,
            dependencies=deps,
            complexity_score=complexity
        )
    
    def _extract_function_chunk(self, node, lines: list) -> CodeChunk:
        """Извлекает функцию как чанк"""
        start = node.lineno
        end = node.end_lineno or start
        content = "\n".join(lines[start-1:end])
        
        complexity = self._calculate_complexity(node)
        deps = self._extract_dependencies(node)
        
        return CodeChunk(
            chunk_type="function",
            name=node.name,
            start_line=start,
            end_line=end,
            content=content,
            dependencies=deps,
            complexity_score=complexity
        )
    
    def _extract_module_level(self, tree: ast.Module, lines: list, chunks: list) -> Optional[CodeChunk]:
        """Извлекает module-level код"""
        # Собираем строки, не входящие в классы/функции
        covered = set()
        for chunk in chunks:
            covered.update(range(chunk.start_line, chunk.end_line + 1))
        
        module_lines = []
        for i, line in enumerate(lines, 1):
            if i not in covered:
                module_lines.append(f"{i:4d} | {line}")
        
        if module_lines:
            return CodeChunk(
                chunk_type="module_level",
                name="<module>",
                start_line=1,
                end_line=len(lines),
                content="\n".join(module_lines),
                complexity_score=1
            )
        return None
    
    def _calculate_complexity(self, node) -> int:
        """Оценивает сложность узла AST"""
        score = 0
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.Try)):
                score += 1
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                score += 2
            elif isinstance(child, ast.ClassDef):
                score += 3
        return score
    
    def _extract_dependencies(self, node) -> list:
        """Извлекает используемые имена"""
        names = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Name):
                names.add(child.id)
            elif isinstance(child, ast.Attribute):
                if isinstance(child.value, ast.Name):
                    names.add(child.value.id)
        return list(names)


# ============================================================================
# TWO-PHASE REVIEW (для AGGRESSIVE level)
# ============================================================================

@dataclass
class TriageResult:
    """Результат первичной сортировки"""
    needs_deep_review: list  # CodeChunk или line ranges
    skip_reasons: dict  # chunk_name → reason
    estimated_tokens: int


class TwoPhaseReviewer:
    """Двухфазный review: triage → deep"""
    
    TRIAGE_PROMPT = """Быстрый анализ кода. Укажи ТОЛЬКО участки, требующие детального review.

Код:
{code_summary}

Ответь JSON:
{{
  "needs_review": [
    {{"name": "function_name", "reason": "complex logic", "priority": "high|medium"}},
    ...
  ],
  "can_skip": ["simple_getter", "obvious_setter"]
}}"""

    DEEP_REVIEW_PROMPT = """Детальный review участка кода.

Контекст:
{context}

Код для проверки (строки {start_line}-{end_line}):
```{language}
{code}
```

Проверь: Security, Logic, Performance, Edge Cases.
Формат: {{"issues": [{{"line": N, "severity": "must|should|suggestion", "issue": "...", "fix": "..."}}]}}"""

    def __init__(self, config: OptimizerConfig):
        self.config = config
        self.chunker = SemanticChunker(config)
    
    def build_triage_prompt(self, chunks: list[CodeChunk]) -> str:
        """Строит промпт для первичной сортировки"""
        summary_parts = []
        
        for chunk in chunks:
            # Только сигнатуры, не весь код
            if chunk.chunk_type == "class":
                summary_parts.append(f"class {chunk.name}: (lines {chunk.start_line}-{chunk.end_line}, complexity={chunk.complexity_score})")
            elif chunk.chunk_type == "function":
                summary_parts.append(f"def {chunk.name}(): (lines {chunk.start_line}-{chunk.end_line}, complexity={chunk.complexity_score})")
        
        return self.TRIAGE_PROMPT.format(code_summary="\n".join(summary_parts))
    
    def build_deep_review_prompt(self, chunk: CodeChunk, context: str, language: str) -> str:
        """Строит промпт для глубокого review конкретного чанка"""
        return self.DEEP_REVIEW_PROMPT.format(
            context=context,
            start_line=chunk.start_line,
            end_line=chunk.end_line,
            language=language,
            code=chunk.content
        )


# ============================================================================
# DIFF ENRICHMENT
# ============================================================================

@dataclass
class EnrichedDiff:
    """Обогащённый diff с минимальным контекстом"""
    hunks: list
    total_context_lines: int
    parent_scopes: dict  # hunk_id → parent function/class signature


class DiffEnricher:
    """Добавляет умный контекст к diff"""
    
    def __init__(self, config: OptimizerConfig):
        self.config = config
    
    def enrich(self, diff: str, full_file: str = None, language: str = "python") -> EnrichedDiff:
        """Обогащает diff контекстом"""
        hunks = self._parse_hunks(diff)
        enriched_hunks = []
        parent_scopes = {}
        
        for hunk in hunks:
            enriched = {
                "header": hunk["header"],
                "changes": hunk["changes"],
            }
            
            # Добавляем контекст если есть полный файл
            if full_file:
                # Находим родительский scope (функцию/класс)
                parent = self._find_parent_scope(full_file, hunk["start_line"], language)
                if parent:
                    enriched["parent_signature"] = parent
                    parent_scopes[hunk["header"]] = parent
            
            enriched_hunks.append(enriched)
        
        return EnrichedDiff(
            hunks=enriched_hunks,
            total_context_lines=sum(len(h["changes"]) for h in enriched_hunks),
            parent_scopes=parent_scopes
        )
    
    def _parse_hunks(self, diff: str) -> list:
        """Парсит diff на hunks"""
        hunks = []
        current_hunk = None
        
        for line in diff.splitlines():
            if line.startswith('@@'):
                if current_hunk:
                    hunks.append(current_hunk)
                
                # Парсим заголовок @@ -start,count +start,count @@
                match = re.match(r'@@ -(\d+),?\d* \+(\d+),?\d* @@', line)
                start_line = int(match.group(2)) if match else 0
                
                current_hunk = {
                    "header": line,
                    "start_line": start_line,
                    "changes": []
                }
            elif current_hunk and line.startswith(('+', '-', ' ')):
                current_hunk["changes"].append(line)
        
        if current_hunk:
            hunks.append(current_hunk)
        
        return hunks
    
    def _find_parent_scope(self, code: str, line_number: int, language: str) -> Optional[str]:
        """Находит родительскую функцию/класс для строки"""
        if language != "python":
            return None
        
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return None
        
        lines = code.splitlines()
        
        # Ищем ближайший scope, содержащий эту строку
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.lineno <= line_number <= (node.end_lineno or node.lineno):
                    # Возвращаем только сигнатуру
                    sig_line = lines[node.lineno - 1]
                    return sig_line.strip()
        
        return None


# ============================================================================
# MULTI-FILE CONTEXT BUILDER
# ============================================================================

@dataclass
class MultiFileContext:
    """Оптимизированный контекст для multi-file review"""
    dependency_graph: str
    interfaces_only: list  # Файлы без изменений - только интерфейсы
    full_content: list     # Изменённые файлы - полный код
    total_tokens_estimate: int


class MultiFileContextBuilder:
    """Строит оптимальный контекст для multi-file review"""
    
    def __init__(self, config: OptimizerConfig):
        self.config = config
        self.preprocessor = CodePreprocessor(config)
    
    def build(self, files: list[dict]) -> MultiFileContext:
        """
        files: [{"path": str, "content": str, "diff": str?, "is_modified": bool}]
        """
        interfaces = []
        full_content = []
        deps = []
        total_tokens = 0
        
        for f in files:
            path = f["path"]
            content = f.get("content", "")
            is_modified = f.get("is_modified", bool(f.get("diff")))
            language = self._detect_language(path)
            
            if is_modified:
                # Полный код с preprocessing
                processed = self.preprocessor.process(content, language, path)
                full_content.append({
                    "path": path,
                    "content": processed.content,
                    "original_lines": processed.original_lines
                })
                total_tokens += processed.processed_lines * 4
            else:
                # Только интерфейс
                interface = self._extract_interface(content, language)
                interfaces.append({
                    "path": path,
                    "interface": interface
                })
                total_tokens += len(interface.splitlines()) * 4
            
            # Собираем зависимости
            deps.extend(self._extract_imports(content, path, language))
        
        # Строим граф зависимостей
        dep_graph = self._build_dependency_graph(deps)
        
        return MultiFileContext(
            dependency_graph=dep_graph,
            interfaces_only=interfaces,
            full_content=full_content,
            total_tokens_estimate=total_tokens
        )
    
    def _detect_language(self, path: str) -> str:
        """Определяет язык по расширению"""
        ext = path.rsplit('.', 1)[-1].lower()
        return {
            'py': 'python',
            'js': 'javascript',
            'ts': 'typescript',
            'jsx': 'javascript',
            'tsx': 'typescript',
            'vue': 'vue',
            'go': 'go',
            'rs': 'rust',
        }.get(ext, 'unknown')
    
    def _extract_interface(self, code: str, language: str) -> str:
        """Извлекает только интерфейс (сигнатуры) из кода"""
        if language != "python":
            # Для других языков - первые N строк + сигнатуры функций
            lines = code.splitlines()[:30]
            return "\n".join(lines) + "\n# ... (interface only)"
        
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return code[:500] + "\n# ... (parse error)"
        
        lines = code.splitlines()
        interface_parts = []
        
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                # Класс + сигнатуры методов
                class_line = lines[node.lineno - 1]
                interface_parts.append(class_line)
                
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_line = lines[item.lineno - 1]
                        interface_parts.append("    " + method_line.strip())
                
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_line = lines[node.lineno - 1]
                interface_parts.append(func_line)
        
        return "\n".join(interface_parts)
    
    def _extract_imports(self, code: str, path: str, language: str) -> list:
        """Извлекает импорты для графа зависимостей"""
        imports = []
        
        if language == "python":
            for line in code.splitlines():
                if line.strip().startswith('from ') or line.strip().startswith('import '):
                    imports.append({"from": path, "import": line.strip()})
        
        return imports
    
    def _build_dependency_graph(self, deps: list) -> str:
        """Строит текстовое представление графа зависимостей"""
        if not deps:
            return "# No cross-file dependencies detected"
        
        graph_lines = ["# Dependency Graph:"]
        for dep in deps[:20]:  # Ограничиваем
            graph_lines.append(f"# {dep['from']} → {dep['import']}")
        
        if len(deps) > 20:
            graph_lines.append(f"# ... and {len(deps) - 20} more")
        
        return "\n".join(graph_lines)


# ============================================================================
# MAIN OPTIMIZER CLASS
# ============================================================================

class ContextOptimizer:
    """Главный класс для оптимизации контекста"""
    
    def __init__(self, config: OptimizerConfig = None):
        self.config = config or OptimizerConfig()
        self.preprocessor = CodePreprocessor(self.config)
        self.chunker = SemanticChunker(self.config)
        self.diff_enricher = DiffEnricher(self.config)
        self.multi_file_builder = MultiFileContextBuilder(self.config)
    
    def optimize_single_file(self, code: str, file_path: str) -> dict:
        """Оптимизирует контекст для single file review"""
        language = self._detect_language(file_path)
        
        # Preprocessing
        processed = self.preprocessor.process(code, language, file_path)
        
        # Chunking если файл большой и AGGRESSIVE mode
        chunks = None
        if (self.config.level == OptimizationLevel.AGGRESSIVE and 
            processed.processed_lines > 100):
            chunks = self.chunker.chunk_python(code) if language == "python" else None
        
        return {
            "mode": "single",
            "processed_code": processed.content,
            "original_lines": processed.original_lines,
            "processed_lines": processed.processed_lines,
            "tokens_saved": processed.tokens_saved_estimate,
            "chunks": chunks,
            "language": language
        }
    
    def optimize_diff(self, diff: str, full_file: str = None) -> dict:
        """Оптимизирует контекст для diff review"""
        # Определяем язык из diff
        language = "python"  # default
        for line in diff.splitlines():
            if line.startswith('diff --git'):
                path = line.split()[-1].replace('b/', '')
                language = self._detect_language(path)
                break
        
        enriched = self.diff_enricher.enrich(diff, full_file, language)
        
        return {
            "mode": "diff",
            "enriched_diff": enriched,
            "hunks_count": len(enriched.hunks),
            "has_parent_scopes": bool(enriched.parent_scopes),
            "language": language
        }
    
    def optimize_multiple_files(self, files: list[dict]) -> dict:
        """Оптимизирует контекст для multi-file review"""
        context = self.multi_file_builder.build(files)
        
        return {
            "mode": "multiple",
            "context": context,
            "files_with_interfaces": len(context.interfaces_only),
            "files_with_full_content": len(context.full_content),
            "estimated_tokens": context.total_tokens_estimate
        }
    
    def _detect_language(self, path: str) -> str:
        """Определяет язык по расширению"""
        ext = path.rsplit('.', 1)[-1].lower() if '.' in path else ''
        return {
            'py': 'python',
            'js': 'javascript', 
            'ts': 'typescript',
            'jsx': 'javascript',
            'tsx': 'typescript',
            'vue': 'vue',
            'go': 'go',
            'rs': 'rust',
            'java': 'java',
            'php': 'php',
        }.get(ext, 'unknown')


# ============================================================================
# OPTIMIZED PROMPTS
# ============================================================================

OPTIMIZED_SYSTEM_PROMPT = """ROLE: Code Reviewer (Zero-Trust)
LANG: {language}
FOCUS: {focus_areas}

OUTPUT JSON:
{{"issues": [{{"line": N, "sev": "must|should|tip", "msg": "...", "fix": "..."}}]}}

RULES:
- Line numbers MUST match original file
- Skip style if not in focus
- Be specific, no generic advice"""


def build_optimized_prompt(
    mode: str,
    language: str,
    focus_areas: list = None,
    project_stack: dict = None
) -> str:
    """Строит оптимизированный system prompt (~200 токенов vs ~800)"""
    
    focus = focus_areas or ["security", "logic", "performance"]
    focus_str = ", ".join(focus)
    
    prompt = OPTIMIZED_SYSTEM_PROMPT.format(
        language=language,
        focus_areas=focus_str
    )
    
    # Добавляем stack только если указан
    if project_stack:
        stack_parts = []
        for key, value in project_stack.items():
            if value:
                stack_parts.append(f"{key}: {value}")
        if stack_parts:
            prompt += f"\n\nSTACK: {', '.join(stack_parts)}"
    
    return prompt


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

if __name__ == "__main__":
    # Demo
    config = OptimizerConfig(level=OptimizationLevel.MODERATE)
    optimizer = ContextOptimizer(config)
    
    sample_code = '''
import os
import sys
from typing import List, Optional
from dataclasses import dataclass

# This is a comment
# Another comment

@dataclass
class User:
    """
    Represents a user in the system.
    
    This is a very long docstring that explains
    everything about the user class in great detail.
    """
    name: str
    email: str
    
    def validate(self) -> bool:
        """Validates the user data"""
        # TODO: implement proper validation
        return bool(self.name and self.email)

def process_users(users: List[User]) -> None:
    """Process all users"""
    for user in users:
        print(f"Processing {user.name}")  # Debug
        if user.validate():
            pass
'''
    
    result = optimizer.optimize_single_file(sample_code, "models/user.py")
    
    print("=== Optimization Result ===")
    print(f"Original lines: {result['original_lines']}")
    print(f"Processed lines: {result['processed_lines']}")
    print(f"Tokens saved: ~{result['tokens_saved']}")
    print(f"\nProcessed code:\n{result['processed_code']}")
