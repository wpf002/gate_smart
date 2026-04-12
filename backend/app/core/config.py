import os


class Settings:
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    RACING_API_USERNAME: str = os.getenv("RACING_API_USERNAME", "")
    RACING_API_PASSWORD: str = os.getenv("RACING_API_PASSWORD", "")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
    TRACKSENSE_WEBHOOK_SECRET: str = os.getenv("TRACKSENSE_WEBHOOK_SECRET", "")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
    ONESIGNAL_APP_ID: str = os.getenv("ONESIGNAL_APP_ID", "")
    ONESIGNAL_API_KEY: str = os.getenv("ONESIGNAL_API_KEY", "")
    GMAIL_USER: str = os.getenv("GMAIL_USER", "")
    GMAIL_APP_PASSWORD: str = os.getenv("GMAIL_APP_PASSWORD", "")
    DAILY_REPORT_EMAIL: str = os.getenv("DAILY_REPORT_EMAIL", "wfoti71992@gmail.com")
    # Railway provides DATABASE_URL as postgresql:// — derive both variants from it
    _db_url_raw: str = os.getenv("DATABASE_URL", "postgresql://localhost/gatesmart")

    @property
    def DATABASE_URL(self) -> str:
        """Async URL for SQLAlchemy asyncpg driver."""
        url = self._db_url_raw
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        if url.startswith("postgresql://") and "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def DATABASE_URL_SYNC(self) -> str:
        """Sync URL for psycopg2 (ingest scripts)."""
        url = self._db_url_raw
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        url = url.replace("postgresql+asyncpg://", "postgresql://")
        return url

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
