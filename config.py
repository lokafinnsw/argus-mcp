"""
Configuration module for MCP verify_code server
"""

import os
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# ============================================================================
# API KEYS - Load from environment variables
# ============================================================================

def get_api_key(key_name: str, required: bool = False) -> Optional[str]:
    """Safely load API key from environment"""
    value = os.getenv(key_name)
    if required and not value:
        raise ValueError(f"{key_name} environment variable is required")
    return value

# GLM 4.7 API (z.ai)
GLM_API_KEY = get_api_key("GLM_API_KEY")
GLM_BASE_URL = "https://api.z.ai/api/coding/paas/v4"

# OpenRouter API (для Gemini и MiniMax)
OPENROUTER_API_KEY = get_api_key("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Проверяем что хотя бы один ключ доступен
if not GLM_API_KEY and not OPENROUTER_API_KEY:
    raise ValueError(
        "At least one API key must be provided: GLM_API_KEY or OPENROUTER_API_KEY"
    )

# ============================================================================
# MODEL CONFIGURATION
# ============================================================================

MODELS = {
    "glm-4.7": {
        "name": "GLM 4.7",
        "provider": "z.ai",
        "api_key": GLM_API_KEY,
        "base_url": GLM_BASE_URL,
        "model_id": "glm-4.7",
        "enabled": bool(GLM_API_KEY),
        "cost_per_1k_tokens": 0.002,  # $0.002/1K tokens
        "max_tokens": 8000,
        "timeout": 60
    },
    "gemini-flash": {
        "name": "Google Gemini 3 Flash Preview",
        "provider": "openrouter",
        "api_key": OPENROUTER_API_KEY,
        "base_url": OPENROUTER_BASE_URL,
        "model_id": "google/gemini-3-flash-preview",
        "enabled": bool(OPENROUTER_API_KEY),
        "cost_per_1k_tokens": 0.001,  # $0.001/1K tokens
        "max_tokens": 8000,
        "timeout": 45
    },
    "minimax": {
        "name": "MiniMax M2.1",
        "provider": "openrouter",
        "api_key": OPENROUTER_API_KEY,
        "base_url": OPENROUTER_BASE_URL,
        "model_id": "minimax/minimax-01",
        "enabled": bool(OPENROUTER_API_KEY),
        "cost_per_1k_tokens": 0.001,  # $0.001/1K tokens
        "max_tokens": 8000,
        "timeout": 60
    }
}

# Базовая модель по умолчанию
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "glm-4.7")

# Fallback порядок при ошибках
FALLBACK_ORDER = ["glm-4.7", "gemini-flash", "minimax"]

# ============================================================================
# VALIDATION LIMITS
# ============================================================================

MAX_CODE_SIZE = 200_000  # 200KB - максимальный размер кода
MAX_TOKENS_ESTIMATE = 50_000  # Примерная оценка токенов
MAX_FILES_COUNT = 20  # Максимум файлов в multiple режиме

# ============================================================================
# RETRY CONFIGURATION
# ============================================================================

RETRY_ATTEMPTS = 3
RETRY_MIN_WAIT = 1  # секунды
RETRY_MAX_WAIT = 10  # секунды

# HTTP статусы для retry
RETRY_STATUS_CODES = [429, 500, 502, 503, 504]

# ============================================================================
# CACHE CONFIGURATION
# ============================================================================

CACHE_ENABLED = True
CACHE_TTL = 3600  # 1 час
CACHE_MAX_SIZE = 100  # Максимум записей в кэше

# ============================================================================
# SERVER CONFIGURATION
# ============================================================================

SERVER_NAME = "Argus MCP"
SERVER_VERSION = "2.0.0"
MCP_PROTOCOL_VERSION = "2024-11-05"

# ============================================================================
# TEMPERATURE AND GENERATION SETTINGS
# ============================================================================

DEFAULT_TEMPERATURE = 0.3  # Низкая температура для консистентности
DEFAULT_MAX_TOKENS = 2000  # Максимум токенов в ответе

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_enabled_models() -> list[str]:
    """Возвращает список доступных моделей"""
    return [key for key, config in MODELS.items() if config["enabled"]]

def get_model_config(model_key: str) -> dict:
    """Получает конфигурацию модели"""
    if model_key not in MODELS:
        raise ValueError(f"Unknown model: {model_key}")
    
    config = MODELS[model_key]
    if not config["enabled"]:
        raise ValueError(f"Model {model_key} is not enabled (missing API key)")
    
    return config

def get_fallback_models(exclude: str = None) -> list[str]:
    """Возвращает список fallback моделей"""
    models = [m for m in FALLBACK_ORDER if MODELS[m]["enabled"]]
    if exclude:
        models = [m for m in models if m != exclude]
    return models
