from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

from .constants import Environment


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database (optional - using Convex instead of PostgreSQL)
    DATABASE_URL: PostgresDsn | None = None
    ENVIRONMENT: Environment = Environment.PRODUCTION

    # Convex Database
    CONVEX_URL: str | None = None

    # Azure Speech Services
    AZURE_SPEECH_KEY: str | None = None
    AZURE_SPEECH_REGION: str | None = None
    AZURE_SPEECH_ENDPOINT: str | None = None

    # Azure OpenAI (for Whisper transcription fallback)
    AZURE_OPENAI_API_KEY: str | None = None
    AZURE_OPENAI_TRANSCRIBE_URL: str | None = None

    # Anthropic Claude
    ANTHROPIC_API_KEY: str
    ANTHROPIC_MODEL: str = "claude-sonnet-4-5"


settings = Config()  # type: ignore
