from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    app_env: str = "local"
    database_url: str = "postgresql+asyncpg://doni:doni@localhost:5432/doni"
    redis_url: str = "redis://localhost:6379/0"
    storage_root: str = "/data"
    ai_server_url: str = "http://localhost:9000"
    jwt_secret: str = "change-me"

    garage_endpoint_url: str = "http://localhost:3900"
    garage_public_url: str = ""  # 외부(AI 서버 등)에서 접근하는 주소. 비어 있으면 endpoint_url 사용
    garage_region: str = "garage"
    garage_access_key: str = ""
    garage_secret_key: str = ""
    garage_bucket: str = "doni"


settings = Settings()
