import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database - Supabase PostgreSQL in production, SQLite for local dev
    database_url: str = "sqlite:///./data/appropriations.db"
    supabase_db_url: Optional[str] = None  # Optional fallback when DATABASE_URL is not set
    attachments_dir: str = "./data/attachments"

    # Supabase Storage for persistent file uploads (production)
    supabase_url: Optional[str] = None
    supabase_service_key: Optional[str] = None
    supabase_storage_bucket: str = "attachments"

    # Google Sheets backup (optional)
    google_sheets_enabled: bool = False
    google_sheets_id: Optional[str] = None
    google_service_account_json: Optional[str] = None  # JSON string of service account credentials

    @property
    def use_supabase_storage(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_key)

    @property
    def resolved_database_url(self) -> str:
        """Preferred runtime DB URL.

        Priority:
        1) DATABASE_URL
        2) SUPABASE_DB_URL
        3) default local SQLite
        """
        # Respect explicit env var first (even when class default is SQLite).
        env_database_url = os.getenv("DATABASE_URL", "").strip()
        env_supabase_db_url = os.getenv("SUPABASE_DB_URL", "").strip()

        url = env_database_url or env_supabase_db_url or self.database_url or self.supabase_db_url or "sqlite:///./data/appropriations.db"

        # Render/Supabase guides sometimes provide postgres:// URLs; SQLAlchemy expects postgresql://
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]

        return url

    class Config:
        env_file = ".env"


settings = Settings()
