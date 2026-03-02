from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool

from app.config import settings

# Configure connection based on database type
connect_args = {}
engine_kwargs = {}

db_url = settings.resolved_database_url

if db_url.startswith("sqlite"):
    # SQLite requires check_same_thread=False for FastAPI
    connect_args["check_same_thread"] = False
elif db_url.startswith("postgresql"):
    # PostgreSQL (Supabase) - use NullPool for serverless compatibility
    engine_kwargs["poolclass"] = NullPool

engine = create_engine(
    db_url,
    connect_args=connect_args,
    **engine_kwargs
)

# Enable foreign keys for SQLite
if db_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
