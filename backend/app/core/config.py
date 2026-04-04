import os
from typing import List


class Settings:
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    RACING_API_USERNAME: str = os.getenv("RACING_API_USERNAME", "")
    RACING_API_PASSWORD: str = os.getenv("RACING_API_PASSWORD", "")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    TRACKSENSE_WEBHOOK_SECRET: str = os.getenv("TRACKSENSE_WEBHOOK_SECRET", "")


settings = Settings()
