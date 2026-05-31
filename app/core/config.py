from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "SoundCare API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/soundcare"

    # CORS
    CORS_ORIGINS: list = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Music Generation
    SUNO_API_KEY: Optional[str] = None
    MINIMAX_API_KEY: Optional[str] = None

    # LLM
    LLM_PROVIDER: str = "openai"
    GEMINI_API_KEY: Optional[str] = None

    # Default Music Provider: "minimax" or "suno"
    DEFAULT_MUSIC_PROVIDER: str = "minimax"

    class Config:
        env_file = ".env"


settings = Settings()