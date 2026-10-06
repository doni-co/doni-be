from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    app_env: str = "local"
    database_url: str = "postgresql+asyncpg://doni:doni@localhost:5432/doni"
    redis_url: str = "redis://localhost:6379/0"
    storage_root: str = "/data"
    ai_server_url: str = "http://localhost:9000"
    jwt_secret: str = "change-me"


settings = Settings()
