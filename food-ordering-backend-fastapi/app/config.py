"""
Application configuration.

Mirrors the exact environment-variable names documented in the current
Node backend's .env.example and confirmed in CURRENT_STATE.md's environment
inventory — no variable is renamed or added beyond what the current system
already reads, per the "preserve configuration surface" requirement in
docs/module-3-development-plan.md.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # MongoDB — current Node code falls back to MONGODB_CONNECTION_STRING
    # when MONGODB_URI is unset; preserved below via `mongodb_uri`.
    MONGODB_URI: str | None = None
    MONGODB_CONNECTION_STRING: str | None = None

    # JWT
    JWT_SECRET_KEY: str = ""

    # Frontend / backend URLs
    FRONTEND_URL: str = "http://localhost:5173"
    BACKEND_URL: str | None = None

    # Google OAuth
    GOOGLE_ID: str | None = None
    GOOGLE_SECRET: str | None = None

    # Cloudinary
    CLOUDINARY_CLOUD_NAME: str | None = None
    CLOUDINARY_API_KEY: str | None = None
    CLOUDINARY_API_SECRET: str | None = None

    # Stripe
    STRIPE_API_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None

    # Server
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    @property
    def mongodb_uri(self) -> str | None:
        """Same fallback order as the current Node backend's src/index.ts."""
        return self.MONGODB_URI or self.MONGODB_CONNECTION_STRING

    @property
    def cors_allow_origins(self) -> list[str]:
        """
        Same fixed allow-list as the current Node backend's src/index.ts,
        with FRONTEND_URL substituted for the env-driven entry. Confirmed
        as a preserved requirement, not a new decision.
        """
        candidates = [
            self.FRONTEND_URL,
            "http://localhost:5173",
            "http://localhost:3000",
            "https://mern-food-ordering.netlify.app",
            "https://mern-food-ordering-hnql.onrender.com",
        ]
        return [origin for origin in candidates if origin]


@lru_cache
def get_settings() -> Settings:
    return Settings()
