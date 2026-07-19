from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from the environment (and an optional .env file)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # The real configuration always comes from backend/.env or the environment.
    # This fallback exists only so that importing the app never explodes when no
    # DATABASE_URL is set (e.g. tooling that imports modules without a live DB).
    # It intentionally mirrors .env.example: the dedicated uk_invoice_user against
    # uk_invoice_db, with a placeholder password that must be overridden.
    database_url: str = (
        "postgresql+psycopg://uk_invoice_user:CHANGE_ME@localhost:5432/uk_invoice_db"
    )


settings = Settings()
