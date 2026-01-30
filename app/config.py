from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database - Supabase PostgreSQL in production, SQLite for local dev
    database_url: str = "sqlite:///./data/appropriations.db"
    attachments_dir: str = "./data/attachments"

    # Google Sheets backup (optional)
    google_sheets_enabled: bool = False
    google_sheets_id: Optional[str] = None
    google_service_account_json: Optional[str] = None  # JSON string of service account credentials

    class Config:
        env_file = ".env"


settings = Settings()
