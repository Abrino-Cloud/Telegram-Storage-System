import os
from typing import List, Union, Optional, Dict, Any
from pydantic_settings import BaseSettings
from pydantic import validator, PostgresDsn, AnyHttpUrl, field_validator

class Settings(BaseSettings):
    # API settings
    API_V1_STR: str = "/api"
    PROJECT_NAME: str = "Telegram Storage"
    
    # CORS settings
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []
    
    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    # Database settings
    POSTGRES_HOST: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    DATABASE_URI: Optional[PostgresDsn] = None
    
    @field_validator("DATABASE_URI", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=values.data.get("POSTGRES_USER"),
            password=values.data.get("POSTGRES_PASSWORD"),
            host=values.data.get("POSTGRES_HOST"),
            path=f"{values.data.get('POSTGRES_DB') or ''}",
        )
    
    # Redis settings
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_PASSWORD: str
    
    # Security settings
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    MAGIC_LINK_EXPIRE_MINUTES: int = 15  # 15 minutes
    
    # Telegram settings
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_ADMIN_USER_ID: int
    
    # Application settings
    ENABLE_REGISTRATION: bool = True
    ADMIN_EMAIL: Optional[str] = None
    ADMIN_PASSWORD: Optional[str] = None
    FRONTEND_URL: str = "http://frontend"
    
    # Rate limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60  # seconds
    
    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()