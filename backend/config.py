"""
config.py — Centralized environment configuration for AI Data Analyst backend.
Never hardcode secrets. Everything is loaded from environment variables / .env.
"""
import os
from dotenv import load_dotenv

load_dotenv()


def _bool(val: str, default: bool = False) -> bool:
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


class Settings:
    # --- LLM provider config -------------------------------------------------
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "none")  # "anthropic" | "openai" | "groq" | "none"
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "claude-sonnet-4-6")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "")  # optional override, e.g. for Groq/other OpenAI-compatible APIs

    # --- Uploads ---------------------------------------------------------------
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./storage/uploads")

    # --- CORS --------------------------------------------------------------
    CORS_ORIGINS: list = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")

    # --- Storage -----------------------------------------------------------
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "./storage/app.db")
    CHROMA_PATH: str = os.getenv("CHROMA_PATH", "./storage/chroma")

    # --- Feature flags -------------------------------------------------------
    CACHE_ENABLED: bool = _bool(os.getenv("CACHE_ENABLED", "true"))
    SEMANTIC_SEARCH_ENABLED: bool = _bool(os.getenv("SEMANTIC_SEARCH_ENABLED", "true"))

    # --- Execution safety ----------------------------------------------------
    SQL_TIMEOUT_SECONDS: int = int(os.getenv("SQL_TIMEOUT_SECONDS", "10"))
    MAX_RESULT_ROWS: int = int(os.getenv("MAX_RESULT_ROWS", "500"))


settings = Settings()

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.dirname(settings.DATABASE_PATH) or ".", exist_ok=True)
os.makedirs(settings.CHROMA_PATH, exist_ok=True)
