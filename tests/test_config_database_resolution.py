from app.config import Settings


def test_resolved_database_url_prefers_supabase_when_database_url_unset(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://u:p@host:5432/db")
    settings = Settings()
    assert settings.resolved_database_url == "postgresql://u:p@host:5432/db"


def test_resolved_database_url_normalizes_postgres_scheme(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@host:5432/db")
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    settings = Settings()
    assert settings.resolved_database_url == "postgresql://u:p@host:5432/db"
