from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/zentri"
    REDIS_URL: str = "redis://localhost:6379"
    JWT_SECRET: str = "dev-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    TZ: str = "UTC"
    PRICE_FETCH_INTERVAL: int = 15
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000
    OLLAMA_HOST: str = "http://host.docker.internal:11434"


settings = Settings()
