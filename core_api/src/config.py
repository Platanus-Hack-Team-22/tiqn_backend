from pydantic import PostgresDsn
from pydantic_settings import BaseSettings

from .constants import Environment


class Config(BaseSettings):
    DATABASE_URL: PostgresDsn
    ENVIRONMENT: Environment = Environment.PRODUCTION


settings = Config()  # type: ignore
