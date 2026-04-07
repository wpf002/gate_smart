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

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
