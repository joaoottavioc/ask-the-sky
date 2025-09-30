# src/core/config.py (Completo e Corrigido)
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    # Credenciais do BlueSky
    BSKY_HANDLE: str
    BSKY_APP_PASSWORD: str

     # Campos para rate limit
    daily_question_limit: int = Field(default=50)     # lê env DAILY_QUESTION_LIMIT
    redis_url: str | None = Field(default=None)       # lê env REDIS_URL

    # Chaves de API para os LLMs
    OPENAI_API_KEY: str
    GOOGLE_API_KEY: str
    
    # Credenciais de Autenticação Google
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    REDIRECT_URI: str

    # Chaves Secretas para Sessão e JWT
    JWT_SECRET: str
    SESSION_COOKIE_SECRET: str  # <-- Variável Adicionada

    # URLs da Aplicação
    STREAMLIT_BASE_URL: str

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()