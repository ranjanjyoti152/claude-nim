from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # NVIDIA NIM
    nvidia_api_key: str = ""
    nim_base_url: str = "https://integrate.api.nvidia.com/v1"
    # Optional extra backends for load balancing. Comma-separated "url|key" pairs;
    # key is optional (blank for local NIM). The primary above is always included.
    # e.g. "http://gpu1:8000/v1|,http://gpu2:8000/v1|"
    nim_backends: str = ""

    # Auth
    jwt_secret: str = "change-me"
    jwt_expire_minutes: int = 1440
    jwt_algorithm: str = "HS256"

    # MongoDB
    mongo_url: str = "mongodb://mongo:27017"
    mongo_db: str = "anthropic_gateway"

    # Gateway
    gateway_port: int = 8787

    # Response caching (non-streaming identical requests)
    cache_enabled: bool = True
    cache_ttl_seconds: int = 300

    def backends(self) -> list[dict]:
        """All NIM backends: the primary plus any configured extras."""
        out = [{"base_url": self.nim_base_url, "api_key": self.nvidia_api_key}]
        for entry in self.nim_backends.split(","):
            entry = entry.strip()
            if not entry:
                continue
            url, _, key = entry.partition("|")
            out.append({"base_url": url.strip(), "api_key": key.strip()})
        return out


settings = Settings()
