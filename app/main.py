from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.db import Base, engine
import app.models  # noqa: F401 — ensure all models are registered before create_all

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
