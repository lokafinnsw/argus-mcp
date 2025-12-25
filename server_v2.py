#!/usr/bin/env python3
"""
MCP Server: verify_code v2.0
Verifies code through multiple AI models with retry, fallback and caching.
"""

import sys
import json
import asyncio
from typing import Dict, Any, Optional

from config import (
    SERVER_NAME, SERVER_VERSION, MCP_PROTOCOL_VERSION,
    DEFAULT_MODEL, get_enabled_models, MODELS, get_fallback_models_for_model
)
from validators import validate_arguments, sanitize_file_path
from prompts import build_system_prompt, build_user_message
from cache import get_cache
from models import get_model_manager
from context_optimizer import ContextOptimizer, OptimizerConfig, OptimizationLevel


class MCPServer:
    def __init__(self):
        self.cache = get_cache()
        self.model_manager = get_model_manager()
        self.optimizer = ContextOptimizer(OptimizerConfig(level=OptimizationLevel.MODERATE))
        
        self.tools = {
            "verify_code": {
                "name": "verify_code",
                "description": """Verifies code through external AI model with Zero-Trust approach.

MODES:
1. Single File - review one file (params: code + file_path)
2. Git Diff - review changes via git diff (param: diff)
3. Multiple Files - review multiple files with cross-file dependencies (param: files[])

FEATURES:
- Retry with exponential backoff (3 attempts)
- Automatic fallback to other models on error
- Result caching (TTL: 1 hour)
- Language-aware checks for 10 languages (Python, JS, TS, Vue, React, Go, Rust, Java, PHP)
- Security (OWASP), performance, and architecture checks

MODELS:
- glm-4.7 (z.ai) - $0.40/M input, fast
- gemini-flash (OpenRouter) - $0.50/M input, very fast
- minimax (OpenRouter) - $0.30/M input

USAGE:
- \"Review my code\" - basic check
- \"Check code with Gemini\" - model selection
- \"Verify changes in multiple files\" - cross-file review""",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "[Mode 1: Single File] Full code of one file"
                        },
                        "diff": {
                            "type": "string",
                            "description": "[Mode 2: Git Diff] Git diff output (unified format). Saves tokens, shows only changes."
                        },
                        "files": {
                            "type": "array",
                            "description": "[Mode 3: Multiple Files] Array of files with changes",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "path": {"type": "string", "description": "File path"},
                                    "content": {"type": "string", "description": "File content"},
                                    "diff": {"type": "string", "description": "Diff for this file (optional)"},
                                    "stats": {"type": "string", "description": "Change statistics, e.g. '+79 -11'"}
                                },
                                "required": ["path"]
                            }
                        },
                        "task_context": {
                            "type": "string",
                            "description": "Task description and what the code should do"
                        },
                        "session_changes": {
                            "type": "string",
                            "description": "Brief description of changes made in this session"
                        },
                        "file_path": {
                            "type": "string",
                            "description": "[Mode 1] File path (for single file mode)"
                        },
                        "model": {
                            "type": "string",
                            "description": f"Model for verification. Available: {', '.join(get_enabled_models())}",
                            "enum": get_enabled_models()
                        },
                        "use_cache": {
                            "type": "boolean",
                            "description": "Use cache (default true)"
                        },
                        "use_fallback": {
                            "type": "boolean",
                            "description": "Use fallback to other models on error (default true)"
                        },
                        "project_stack": {
                            "type": "object",
                            "description": "Project technology stack information for more accurate verification",
                            "properties": {
                                "framework": {"type": "string", "description": "Main framework (e.g., Django 5.0, FastAPI)"},
                                "frontend": {"type": "string", "description": "Frontend stack (e.g., Vue 3 + Inertia.js)"},
                                "backend": {"type": "string", "description": "Backend stack (e.g., Python 3.11)"},
                                "database": {"type": "string", "description": "Database (e.g., PostgreSQL 15)"},
                                "conventions": {"type": "string", "description": "Code conventions (e.g., Google Python Style Guide)"},
                                "architecture": {"type": "string", "description": "Architectural pattern (e.g., Clean Architecture, MVC)"}
                            }
                        }
                    },
                    "required": ["task_context"]
                }
            },
            "list_models": {
                "name": "list_models",
                "description": """Shows list of all available AI models for code verification.

INFORMATION:
- Model name and key
- Provider (z.ai, OpenRouter)
- Status (✅ available / ❌ unavailable)
- Cost per 1K tokens
- Max tokens
- Current default model

USAGE:
- \"Show available models\"
- \"What models can I use?\"
- \"List models for code review\"

RESULT: Table with full information about each model""",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            "set_default_model": {
                "name": "set_default_model",
                "description": """Sets default model for current session.

PURPOSE:
Changes the base model that will be used for all subsequent code checks if model is not specified explicitly.

AVAILABLE MODELS:
- glm-4.7 - fast, $0.40/M input (default)
- gemini-flash - very fast, $0.50/M input
- minimax - medium speed, $0.30/M input

USAGE:
- \"Set Gemini as default model\"
- \"Use MiniMax for all checks\"
- \"Switch to GLM 4.7\"

NOTE: Change applies only to current session""",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "model": {
                            "type": "string",
                            "description": "Model key to set as default",
                            "enum": get_enabled_models()
                        }
                    },
                    "required": ["model"]
                }
            },
            "cache_stats": {
                "name": "cache_stats",
                "description": """Shows cache statistics for code verification results.

INFORMATION:
- Cache status (enabled/disabled)
- Current size / max size
- TTL (entry lifetime in seconds)
- Fill percentage

PURPOSE:
Cache stores verification results to speed up repeated requests with the same code. If code hasn't changed, result is taken from cache (~50ms instead of 2-5 sec).

USAGE:
- \"Show cache stats\"
- \"How many results in cache?\"
- \"Check cache status\"

RESULT: Detailed information about cache state""",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            "retry_with_fallback": {
                "name": "retry_with_fallback",
                "description": """Retries the last failed code verification with fallback models.

PURPOSE:
If the primary model failed during code verification, this tool allows you to retry the verification using fallback models.

USAGE:
- \"Retry with fallback models\"
- \"Try other models\"
- \"Use fallback for last check\"

NOTE: This will use the exact same code and parameters from the last failed verification.""",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            "diagnose": {
                "name": "diagnose",
                "description": """Diagnose API connectivity and show recent errors.

PURPOSE:
Helps troubleshoot when code verification fails. Tests connection to each AI provider and shows recent error log.

CHECKS:
- API key presence for each model
- Connection test to z.ai and OpenRouter
- Recent error history with timestamps
- Recommendations for fixing issues

USAGE:
- \"Diagnose Argus\"
- \"Why is verification failing?\"
- \"Check API status\"
- \"Show recent errors\"

RESULT: Diagnostic report with connection status and error analysis""",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            }
        }

    def _detect_mode(self, arguments: dict) -> str:
        """Detects operation mode based on provided parameters"""
        if arguments.get("diff"):
            return "diff"
        elif arguments.get("files"):
            return "multiple"
        elif arguments.get("code"):
            return "single"
        else:
            return "unknown"

    def _extract_file_paths(self, arguments: dict, mode: str) -> list[str]:
        """Извлекает пути к файлам для language hints"""
        if mode == "single":
            file_path = arguments.get("file_path", "")
            return [sanitize_file_path(file_path)] if file_path else []
        
        elif mode == "diff":
            diff = arguments.get("diff", "")
            files = []
            for line in diff.split('\n'):
                if line.startswith('diff --git'):
                    parts = line.split()
                    if len(parts) >= 4:
                        file_path = parts[3].replace('b/', '')
                        files.append(sanitize_file_path(file_path))
            return files
        
        elif mode == "multiple":
            files = arguments.get("files", [])
            return [sanitize_file_path(f.get("path", "")) for f in files if f.get("path")]
        
        return []

    def _format_code_for_review(self, arguments: dict, mode: str) -> tuple:
        """Formats code for review based on mode (with optimization)"""
        
        if mode == "single":
            file_path = arguments.get("file_path", "unknown")
            code = arguments.get("code", "")
            
            result = self.optimizer.optimize_single_file(code, file_path)
            
            header = f"📄 **{file_path}** (optimized: {result['original_lines']}→{result['processed_lines']} lines)"
            content = f"## Code to Review\n```{result['language']}\n{result['processed_code']}\n```"
            
            return (header, content)
        
        elif mode == "diff":
            diff = arguments.get("diff", "")
            
            result = self.optimizer.optimize_diff(diff)
            
            enriched = result["enriched_diff"]
            
            content_parts = ["## Git Diff (Enriched)"]
            for hunk in enriched.hunks:
                if hunk.get("parent_signature"):
                    content_parts.append(f"# In: {hunk['parent_signature']}")
                content_parts.append(hunk["header"])
                content_parts.extend(hunk["changes"])
            
            files = []
            for line in diff.split('\n'):
                if line.startswith('diff --git'):
                    parts = line.split()
                    if len(parts) >= 4:
                        file_path = parts[3].replace('b/', '')
                        files.append(file_path)
            
            header = "\n".join([f"📄 **{f}**" for f in files]) if files else "📄 **Changes**"
            content = "\n".join(content_parts)
            
            return (header, f"```diff\n{content}\n```")
        
        elif mode == "multiple":
            files = arguments.get("files", [])
            
            files_for_optimizer = []
            for f in files:
                files_for_optimizer.append({
                    "path": f.get("path", "unknown"),
                    "content": f.get("content", ""),
                    "diff": f.get("diff"),
                    "is_modified": bool(f.get("diff") or f.get("content"))
                })
            
            result = self.optimizer.optimize_multiple_files(files_for_optimizer)
            context = result["context"]
            
            content_parts = []
            
            if context.dependency_graph:
                content_parts.append(context.dependency_graph)
                content_parts.append("")
            
            for f in context.interfaces_only:
                content_parts.append(f"### {f['path']} (interface only)")
                content_parts.append(f"```\n{f['interface']}\n```")
                content_parts.append("")
            
            for f in context.full_content:
                content_parts.append(f"### {f['path']} (MODIFIED, {f['original_lines']} lines)")
                content_parts.append(f"```\n{f['content']}\n```")
                content_parts.append("")
            
            headers = []
            for f in files:
                path = f.get("path", "unknown")
                stats = f.get("stats", "")
                headers.append(f"📄 **{path}** {stats}")
            
            header = "\n".join(headers)
            content = "\n".join(content_parts)
            
            return (header, content)
        
        return ("", "")

    async def _verify_code(self, arguments: dict) -> Dict[str, Any]:
        """Main code verification logic"""
        
        # Validate input
        valid, error = validate_arguments(arguments)
        if not valid:
            return {"success": False, "error": f"Validation error: {error}"}
        
        # Determine mode and model
        mode = self._detect_mode(arguments)
        model_key = arguments.get("model", DEFAULT_MODEL)
        use_cache = arguments.get("use_cache", True)
        use_fallback = arguments.get("use_fallback", False)  # Disabled by default
        
        # Check cache
        if use_cache:
            cached_result = self.cache.get(arguments, model_key)
            if cached_result:
                cached_result["from_cache"] = True
                return cached_result
        
        # Format code and build prompts
        files_header, code_content = self._format_code_for_review(arguments, mode)
        file_paths = self._extract_file_paths(arguments, mode)
        project_stack = arguments.get("project_stack")
        
        system_prompt = build_system_prompt(mode, file_paths, project_stack)
        user_message = build_user_message(
            arguments.get("task_context", ""),
            arguments.get("session_changes", ""),
            code_content
        )
        
        # Call model (without automatic fallback by default)
        if use_fallback:
            result = await self.model_manager.verify_with_fallback(
                system_prompt, user_message, model_key
            )
        else:
            result = await self.model_manager.verify_without_fallback(
                system_prompt, user_message, model_key
            )
        
        # If primary model failed and fallback is disabled, ask user
        if not result["success"] and not use_fallback:
            result["needs_fallback"] = True
            result["message"] = f"Primary model '{model_key}' failed. Would you like to try fallback models?"
            # Save arguments for possible retry
            self._last_failed_verification = arguments
        
        # Add files header to verdict
        if result["success"] and files_header:
            result["verdict"] = f"{files_header}\n\n{result['verdict']}"
        
        # Save to cache
        if use_cache and result["success"]:
            self.cache.set(arguments, model_key, result)
        
        return result

    async def _list_models(self) -> Dict[str, Any]:
        """Returns list of available models"""
        models_info = []
        for key, config in MODELS.items():
            # Get fallback models for this model
            fallback_models = get_fallback_models_for_model(key)
            
            models_info.append({
                "key": key,
                "name": config["name"],
                "provider": config["provider"],
                "enabled": config["enabled"],
                "cost_input_per_1k": config["cost_input_per_1k"],
                "cost_output_per_1k": config["cost_output_per_1k"],
                "max_tokens": config["max_tokens"],
                "fallback_models": fallback_models
            })
        
        return {
            "success": True,
            "models": models_info,
            "default_model": DEFAULT_MODEL
        }

    async def _set_default_model(self, model_key: str) -> Dict[str, Any]:
        """Sets default model for session"""
        from config import MODELS, get_enabled_models
        
        enabled_models = get_enabled_models()
        
        if model_key not in enabled_models:
            return {
                "success": False,
                "error": f"Model '{model_key}' not available. Enabled models: {', '.join(enabled_models)}"
            }
        
        # DEFAULT_MODEL is a constant from config.py
        # For session changes we store in self
        if not hasattr(self, '_session_default_model'):
            self._session_default_model = DEFAULT_MODEL
        
        old_model = self._session_default_model
        self._session_default_model = model_key
        
        model_config = MODELS[model_key]
        
        return {
            "success": True,
            "old_model": old_model,
            "new_model": model_key,
            "model_name": model_config["name"],
            "message": f"Default model changed from '{old_model}' to '{model_key}' ({model_config['name']})"
        }

    async def _cache_stats(self) -> Dict[str, Any]:
        """Returns cache statistics"""
        return {
            "success": True,
            "cache": self.cache.stats()
        }

    async def _retry_with_fallback(self, arguments: dict) -> Dict[str, Any]:
        """Retries last verification using fallback models"""
        # Check if there are saved arguments from last verification
        if not hasattr(self, '_last_failed_verification'):
            return {
                "success": False,
                "error": "No failed verification found to retry"
            }
        
        # Get arguments from last verification
        last_arguments = self._last_failed_verification
        
        # Copy arguments and enable fallback
        retry_arguments = last_arguments.copy()
        retry_arguments["use_fallback"] = True
        
        # Execute verification with fallback
        result = await self._verify_code(retry_arguments)
        
        # If verification successful, remove saved arguments
        if result["success"]:
            delattr(self, '_last_failed_verification')
        
        return result

    async def _test_model_connection(self, model_key: str, config: dict) -> tuple:
        """Tests connection to a single model (with timeout)"""
        import httpx
        
        if not config.get("enabled"):
            return (model_key, "⏭️ Skipped (no API key)", None)
        
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                headers = {
                    "Authorization": f"Bearer {config['api_key']}",
                    "Content-Type": "application/json"
                }
                if config['provider'] == 'openrouter':
                    headers["HTTP-Referer"] = "https://argus-mcp-diagnose"
                
                await client.post(
                    f"{config['base_url']}/chat/completions",
                    headers=headers,
                    json={
                        "model": config['model_id'],
                        "messages": [{"role": "user", "content": "Hi"}],
                        "max_tokens": 5
                    }
                )
                return (model_key, "✅ Connected", 200)
        
        except httpx.TimeoutException:
            return (model_key, "⏱️ Timeout", "TIMEOUT")
        except httpx.HTTPStatusError as e:
            error_text = e.response.text[:50]
            return (model_key, f"❌ HTTP {e.response.status_code}: {error_text}", e.response.status_code)
        except httpx.ConnectError as e:
            return (model_key, f"🌐 Connection failed", "CONNECT_ERROR")
        except Exception as e:
            return (model_key, f"❓ {str(e)[:30]}", "ERROR")
    
    async def _diagnose(self) -> str:
        """Diagnoses API connections and errors"""
        from models import get_error_log, format_error_for_user
        
        lines = ["# 🔍 Argus MCP Diagnostics\n"]
        
        # 1. Check API keys
        lines.append("## API Keys Status\n")
        for model_key, config in MODELS.items():
            has_key = bool(config.get("api_key"))
            status = "✅" if has_key else "❌ MISSING"
            key_preview = config.get("api_key", "")[:8] + "..." if has_key else "Not set"
            lines.append(f"- **{config['name']}** ({model_key}): {status}")
            if has_key:
                lines.append(f"  - Key: `{key_preview}`")
                lines.append(f"  - Provider: {config['provider']}")
        
        # 2. Test API connections (parallel, with timeout)
        lines.append("\n## Connection Tests\n")
        
        try:
            # Create tasks and wait for completion with global timeout
            test_tasks = [
                self._test_model_connection(key, config)
                for key, config in MODELS.items()
            ]
            
            # Wait for all tests with 15 second timeout for entire process
            test_results = await asyncio.wait_for(
                asyncio.gather(*test_tasks, return_exceptions=True),
                timeout=15.0
            )
            
            for model_key, status, code in test_results:
                lines.append(f"- **{model_key}**: {status}")
        
        except asyncio.TimeoutError:
            lines.append("⏱️ Connection tests timed out (15s). One or more APIs are slow or unresponsive.")
            lines.append("   Check your network connection or API provider status.")
        
        # 3. Recent errors
        lines.append("\n## Recent Errors\n")
        error_log = get_error_log()
        if error_log:
            for err in error_log[-5:]:
                status = f" (HTTP {err['status_code']})" if err.get('status_code') else ""
                lines.append(f"- `{err['timestamp'][:19]}` **{err['model']}**: {err['error_type']}{status}")
                lines.append(f"  - {err['details'][:100]}")
        else:
            lines.append("No recent errors recorded.")
        
        # 4. Recommendations
        lines.append("\n## Recommendations\n")
        
        # Analyze test results if available
        if 'test_results' in locals():
            failed_tests = [r for r in test_results if "❌" in r[1] or "⏱️" in r[1] or "🌐" in r[1]]
            
            if not failed_tests:
                lines.append("✅ All systems operational!")
            else:
                for model_key, status, code in failed_tests:
                    if code == 401:
                        lines.append(f"- **{model_key}**: Invalid API key. Check `.env` file.")
                    elif code == 429:
                        lines.append(f"- **{model_key}**: Rate limited. Wait a few minutes.")
                    elif code == "TIMEOUT":
                        lines.append(f"- **{model_key}**: API slow/overloaded. Try later.")
                    elif code == "CONNECT_ERROR":
                        lines.append(f"- **{model_key}**: Network issue. Check internet connection.")
                    else:
                        lines.append(f"- **{model_key}**: Check API provider status page.")
        else:
            lines.append("⚠️ Could not complete connection tests due to timeout.")
        
        return "\n".join(lines)

    async def handle_request(self, request: dict) -> dict:
        """Handles MCP request"""
        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "Argus MCP",
                        "version": SERVER_VERSION
                    }
                }
            }

        elif method == "notifications/initialized":
            return None

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": list(self.tools.values())}
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            if tool_name == "verify_code":
                result = await self._verify_code(arguments)
                
                if result["success"]:
                    # Format output
                    content_parts = [result['verdict']]
                    
                    # Add model info
                    model_info = f"*Verified by: {result['model']}*"
                    
                    # Add fallback info if used
                    if result.get("fallback_used"):
                        model_info += f"\n*⚠️ Fallback: primary model {result['primary_model_failed']} failed*"
                    
                    # Add cache info
                    if result.get("from_cache"):
                        model_info += "\n*💾 Result from cache*"
                    
                    # Add cost if available
                    if result.get("cost", 0) > 0:
                        model_info += f"\n*💰 Cost: ${result['cost']:.4f}*"
                    
                    content_parts.append(f"\n---\n{model_info}")
                    content = "\n".join(content_parts)
                else:
                    # Format detailed error message
                    error_parts = [f"❌ **Verification Failed**\n"]
                    error_parts.append(f"**Error:** {result['error']}\n")
                    
                    # Add error details if available
                    if result.get("error_details"):
                        error_parts.append(f"\n**Details:**\n{result['error_details']}\n")
                    
                    # Add recommendations
                    if result.get("recommendations"):
                        error_parts.append("\n**Recommendations:**")
                        for rec in result["recommendations"]:
                            error_parts.append(f"\n- {rec}")
                    
                    error_parts.append("\n\n*Use `Diagnose Argus` for detailed diagnostics*")
                    content = "".join(error_parts)

                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": content}]
                    }
                }
            
            elif tool_name == "list_models":
                result = await self._list_models()
                
                # Format output
                models_text = "# Available Models\n\n"
                for model in result["models"]:
                    status = "✅" if model["enabled"] else "❌"
                    cost_in = f"${model['cost_input_per_1k']:.4f}/1K in"
                    cost_out = f"${model['cost_output_per_1k']:.4f}/1K out"
                    
                    models_text += f"{status} **{model['name']}** (`{model['key']}`)\n"
                    models_text += f"   - Provider: {model['provider']}\n"
                    models_text += f"   - Cost: {cost_in}, {cost_out}\n"
                    models_text += f"   - Context: {model['max_tokens']:,} tokens\n\n"
                
                models_text += f"\n**Default model:** `{result['default_model']}`"
                
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": models_text}]
                    }
                }
            
            elif tool_name == "set_default_model":
                model_key = arguments.get("model")
                result = await self._set_default_model(model_key)
                
                if result["success"]:
                    content = f"""✅ **Default Model Changed**

**Previous model:** `{result['old_model']}`
**New model:** `{result['new_model']}` ({result['model_name']})

All subsequent code verifications will use {result['model_name']} unless explicitly specified.

**Note:** This change applies only to the current Windsurf session."""
                else:
                    content = f"❌ Error: {result['error']}"
                
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": content}]
                    }
                }
            
            elif tool_name == "cache_stats":
                result = await self._cache_stats()
                
                cache = result["cache"]
                stats_text = f"""# Cache Statistics

**Enabled:** {cache['enabled']}
**Size:** {cache['size']} / {cache['max_size']}
**TTL:** {cache['ttl']} seconds"""
                
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": stats_text}]
                    }
                }
            
            elif tool_name == "diagnose":
                try:
                    result = await asyncio.wait_for(self._diagnose(), timeout=20.0)
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [{"type": "text", "text": result}]
                        }
                    }
                except asyncio.TimeoutError:
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [{"type": "text", "text": "⏱️ Diagnostics timed out after 20 seconds. One or more APIs are slow or unresponsive. Check your network connection."}]
                        }
                    }
            
            elif tool_name == "retry_with_fallback":
                result = await self._retry_with_fallback(arguments)
                
                if result["success"]:
                    # Format output
                    content_parts = [result['verdict']]
                    
                    # Add model info
                    model_info = f"*Verified by: {result['model']}*"
                    
                    # Add fallback info if used
                    if result.get("fallback_used"):
                        model_info += f"\n*⚠️ Fallback: primary model {result['primary_model_failed']} failed*"
                    
                    # Add cache info
                    if result.get("from_cache"):
                        model_info += "\n*💾 Result from cache*"
                    
                    # Add cost if available
                    if result.get("cost", 0) > 0:
                        model_info += f"\n*💰 Cost: ${result['cost']:.4f}*"
                    
                    content_parts.append(f"\n---\n{model_info}")
                    content = "\n".join(content_parts)
                else:
                    # Format detailed error message
                    error_parts = [f"❌ **Verification Failed**\n"]
                    error_parts.append(f"**Error:** {result['error']}\n")
                    
                    # Add error details if available
                    if result.get("error_details"):
                        error_parts.append(f"\n**Details:**\n{result['error_details']}\n")
                    
                    # Add recommendations
                    if result.get("recommendations"):
                        error_parts.append("\n**Recommendations:**")
                        for rec in result["recommendations"]:
                            error_parts.append(f"\n- {rec}")
                    
                    error_parts.append("\n\n*Use `Diagnose Argus` for detailed diagnostics*")
                    content = "".join(error_parts)

                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": content}]
                    }
                }
            
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": f"Unknown tool: {tool_name}"
                    }
                }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}"
            }
        }

    async def run(self):
        """Запускает MCP сервер через stdio"""
        while True:
            try:
                line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
                if not line:
                    break
                
                request = json.loads(line.strip())
                response = await self.handle_request(request)
                
                if response:
                    sys.stdout.write(json.dumps(response) + "\n")
                    sys.stdout.flush()
                    
            except json.JSONDecodeError:
                continue
            except Exception as e:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32603,
                        "message": str(e)
                    }
                }
                sys.stdout.write(json.dumps(error_response) + "\n")
                sys.stdout.flush()


if __name__ == "__main__":
    server = MCPServer()
    asyncio.run(server.run())
