from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # NVIDIA NIM
    nvidia_api_key: str = ""
    nim_base_url: str = "https://integrate.api.nvidia.com/v1"

    # Auth
    jwt_secret: str = "change-me"
    jwt_expire_minutes: int = 1440
    jwt_algorithm: str = "HS256"

    # MongoDB
    mongo_url: str = "mongodb://mongo:27017"
    mongo_db: str = "anthropic_gateway"

    # Gateway
    gateway_port: int = 8787


settings = Settings()
