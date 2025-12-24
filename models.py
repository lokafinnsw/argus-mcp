"""
Model providers with retry logic and fallback support
"""

import asyncio
import httpx
from typing import Dict, Any, Optional
from config import (
    MODELS, DEFAULT_TEMPERATURE, DEFAULT_MAX_TOKENS,
    RETRY_ATTEMPTS, RETRY_MIN_WAIT, RETRY_MAX_WAIT, RETRY_STATUS_CODES,
    get_fallback_models
)


class ModelProvider:
    """Base class for model providers"""
    
    def __init__(self, model_key: str):
        if model_key not in MODELS:
            raise ValueError(f"Unknown model: {model_key}")
        
        self.config = MODELS[model_key]
        if not self.config["enabled"]:
            raise ValueError(f"Model {model_key} is not enabled (missing API key)")
        
        self.model_key = model_key
    
    async def _call_api_with_retry(
        self,
        messages: list[dict],
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS
    ) -> Dict[str, Any]:
        """Вызывает API с retry-логикой"""
        
        last_error = None
        
        for attempt in range(RETRY_ATTEMPTS):
            try:
                result = await self._call_api(messages, temperature, max_tokens)
                return result
            
            except httpx.HTTPStatusError as e:
                last_error = e
                
                # Retry только для определённых статусов
                if e.response.status_code not in RETRY_STATUS_CODES:
                    raise
                
                # Экспоненциальная задержка
                if attempt < RETRY_ATTEMPTS - 1:
                    wait_time = min(RETRY_MIN_WAIT * (2 ** attempt), RETRY_MAX_WAIT)
                    await asyncio.sleep(wait_time)
            
            except Exception as e:
                last_error = e
                # Для других ошибок не делаем retry
                raise
        
        # Если все попытки исчерпаны
        raise last_error
    
    async def _call_api(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int
    ) -> Dict[str, Any]:
        """Вызывает API (должен быть переопределён в подклассах)"""
        
        timeout = self.config.get("timeout", 60)
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            headers = {
                "Authorization": f"Bearer {self.config['api_key']}",
                "Content-Type": "application/json"
            }
            
            # Для OpenRouter добавляем дополнительные заголовки
            if self.config['provider'] == 'openrouter':
                headers["HTTP-Referer"] = "https://windsurf-mcp-verify-code"
                headers["X-Title"] = "Windsurf Code Verifier"
            
            response = await client.post(
                f"{self.config['base_url']}/chat/completions",
                headers=headers,
                json={
                    "model": self.config['model_id'],
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens
                }
            )
            
            response.raise_for_status()
            return response.json()
    
    async def verify_code(
        self,
        system_prompt: str,
        user_message: str
    ) -> Dict[str, Any]:
        """Проверяет код через модель"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        try:
            data = await self._call_api_with_retry(messages)
            
            verdict = data["choices"][0]["message"]["content"]
            
            return {
                "success": True,
                "verdict": verdict,
                "model": self.config['name'],
                "model_key": self.model_key,
                "tokens_used": data.get("usage", {}),
                "cost": self._calculate_cost(data.get("usage", {}))
            }
        
        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "error": f"API Error: {e.response.status_code} - {e.response.text}",
                "model": self.config['name'],
                "model_key": self.model_key
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "model": self.config['name'],
                "model_key": self.model_key
            }
    
    def _calculate_cost(self, usage: dict) -> float:
        """Рассчитывает стоимость запроса"""
        if not usage:
            return 0.0
        
        total_tokens = usage.get("total_tokens", 0)
        cost_per_1k = self.config.get("cost_per_1k_tokens", 0.0)
        
        return (total_tokens / 1000) * cost_per_1k


class ModelManager:
    """Управляет моделями и fallback логикой"""
    
    def __init__(self):
        self._providers: Dict[str, ModelProvider] = {}
    
    def get_provider(self, model_key: str) -> ModelProvider:
        """Получает провайдер для модели"""
        if model_key not in self._providers:
            self._providers[model_key] = ModelProvider(model_key)
        return self._providers[model_key]
    
    async def verify_with_fallback(
        self,
        system_prompt: str,
        user_message: str,
        primary_model: str
    ) -> Dict[str, Any]:
        """Проверяет код с fallback на другие модели при ошибке"""
        
        # Пробуем основную модель
        try:
            provider = self.get_provider(primary_model)
            result = await provider.verify_code(system_prompt, user_message)
            
            if result["success"]:
                return result
        
        except Exception as e:
            # Логируем ошибку, но продолжаем с fallback
            pass
        
        # Если основная модель не сработала, пробуем fallback
        fallback_models = get_fallback_models(exclude=primary_model)
        
        for model_key in fallback_models:
            try:
                provider = self.get_provider(model_key)
                result = await provider.verify_code(system_prompt, user_message)
                
                if result["success"]:
                    # Добавляем информацию о fallback
                    result["fallback_used"] = True
                    result["primary_model_failed"] = primary_model
                    return result
            
            except Exception:
                continue
        
        # Если все модели не сработали
        return {
            "success": False,
            "error": f"All models failed. Primary: {primary_model}, Fallbacks: {fallback_models}",
            "model": "None",
            "model_key": None
        }


# Глобальный экземпляр менеджера
_manager = ModelManager()


def get_model_manager() -> ModelManager:
    """Возвращает глобальный экземпляр менеджера моделей"""
    return _manager
