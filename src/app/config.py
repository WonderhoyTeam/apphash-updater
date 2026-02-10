from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "WONDERHOY_"}

    host: str = "0.0.0.0"
    port: int = 8000
    refresh_interval_minutes: int = 5
    admin_api_key: str = ""
    http_proxy: str | None = None
    enabled_regions: str = "JP,EN,TW,KR,CN"
    unity_version: str = "2022.3.21f1"
    cache_dir: str = "/data/cache"

    @property
    def region_list(self) -> list[str]:
        return [r.strip().upper() for r in self.enabled_regions.split(",") if r.strip()]


settings = Settings()
