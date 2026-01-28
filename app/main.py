from fastapi import FastAPI

from app.api import api_router

app = FastAPI(
    title="FY27 Appropriations Tracker",
    description="Tier Two appropriations tracking system for CPF, programmatic, and language requests",
    version="1.0.0",
)

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
