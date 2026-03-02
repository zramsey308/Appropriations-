import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.api import api_router
from app.db import Base, engine
import app.models  # noqa: F401 — ensure all models are registered before create_all

logger = logging.getLogger(__name__)

app = FastAPI(
    title="FY27 Appropriations Tracker",
    description="Tier Two appropriations tracking system for CPF, programmatic, and language requests",
    version="1.0.0",
)

# CORS configuration for GitHub Pages frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        # GitHub Pages - will be updated with actual URL
        "https://*.github.io",
    ],
    allow_origin_regex=r"https://.*\.github\.io",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create database tables on startup (safe no-op if they already exist)
Base.metadata.create_all(bind=engine)

# Apply incremental schema changes for columns added after initial deployment
def _apply_column_migrations():
    """Add missing columns that were introduced after initial deployment."""
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("requests")}
    with engine.begin() as conn:
        if "priority_order" not in columns:
            conn.execute(text("ALTER TABLE requests ADD COLUMN priority_order INTEGER"))
            logger.info("Added priority_order column to requests table")

try:
    _apply_column_migrations()
except Exception as e:
    logger.warning(f"Column migration skipped: {e}")

app.include_router(api_router, prefix="/api")


@app.get("/")
def root():
    return {
        "name": "FY27 Appropriations Tracker",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}
