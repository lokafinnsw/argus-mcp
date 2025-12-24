"""
Caching module for code review results
"""

import hashlib
import json
import time
from typing import Optional, Dict, Any
from config import CACHE_ENABLED, CACHE_TTL, CACHE_MAX_SIZE


class ReviewCache:
    """Simple in-memory cache for review results"""
    
    def __init__(self, enabled: bool = CACHE_ENABLED, ttl: int = CACHE_TTL, max_size: int = CACHE_MAX_SIZE):
        self.enabled = enabled
        self.ttl = ttl
        self.max_size = max_size
        self._cache: Dict[str, Dict[str, Any]] = {}
    
    def _generate_key(self, arguments: dict, model: str) -> str:
        """Генерирует ключ кэша на основе аргументов и модели"""
        # Создаём стабильный ключ из аргументов
        cache_data = {
            "model": model,
            "code": arguments.get("code", ""),
            "diff": arguments.get("diff", ""),
            "files": arguments.get("files", []),
            "task_context": arguments.get("task_context", "")
        }
        
        # Сортируем для стабильности
        content = json.dumps(cache_data, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def get(self, arguments: dict, model: str) -> Optional[dict]:
        """Получает результат из кэша"""
        if not self.enabled:
            return None
        
        key = self._generate_key(arguments, model)
        
        if key not in self._cache:
            return None
        
        entry = self._cache[key]
        
        # Проверяем TTL
        if time.time() - entry["timestamp"] > self.ttl:
            del self._cache[key]
            return None
        
        return entry["result"]
    
    def set(self, arguments: dict, model: str, result: dict) -> None:
        """Сохраняет результат в кэш"""
        if not self.enabled:
            return
        
        key = self._generate_key(arguments, model)
        
        # Если кэш переполнен, удаляем самую старую запись
        if len(self._cache) >= self.max_size:
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k]["timestamp"])
            del self._cache[oldest_key]
        
        self._cache[key] = {
            "result": result,
            "timestamp": time.time()
        }
    
    def clear(self) -> None:
        """Очищает весь кэш"""
        self._cache.clear()
    
    def stats(self) -> dict:
        """Возвращает статистику кэша"""
        return {
            "enabled": self.enabled,
            "size": len(self._cache),
            "max_size": self.max_size,
            "ttl": self.ttl
        }


# Глобальный экземпляр кэша
_cache = ReviewCache()


def get_cache() -> ReviewCache:
    """Возвращает глобальный экземпляр кэша"""
    return _cache
