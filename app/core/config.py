from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Kidzventure ERP"
    debug: bool = False

    # Set DEV_SQLITE=true for local run without PostgreSQL/Docker
    dev_sqlite: bool = False
    sqlite_path: str = "./kidzventure_dev.db"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/kidzventure"
    database_url_sync: str = "postgresql://postgres:postgres@localhost:5432/kidzventure"

    @property
    def use_sqlite(self) -> bool:
        return self.dev_sqlite

    @property
    def effective_database_url(self) -> str:
        if self.dev_sqlite:
            return f"sqlite+aiosqlite:///{self.sqlite_path}"
        return self.database_url

    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
