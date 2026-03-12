"""
NDAA JSON Schema Upload endpoint.

Accepts structured JSON from ChatGPT doc parsing for NDAA
(National Defense Authorization Act) requests, supporting both single and bulk uploads.
"""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.requests import Request as StarletteRequest

from app.db import get_db

router = APIRouter()


class NdaaUploadResult(BaseModel):
    id: int
    title: str
    request_type: str
    subcommittee: str
    organization: str
    amount: Optional[int] = None
    status: str


class NdaaBulkUploadResponse(BaseModel):
    created: int
    requests: list[NdaaUploadResult]
    errors: list[str]


@router.post("/ndaa-json", response_model=NdaaBulkUploadResponse)
async def upload_ndaa_json(
    request: StarletteRequest,
    db: Session = Depends(get_db),
):
    """Upload one or more NDAA requests in JSON schema.

    Accepts either a single JSON object or an array of them.
    """
    # Lazy import to avoid circular dependencies
    from app.api.intake import _create_from_flat_ndaa

    payload = await request.json()
    items = payload if isinstance(payload, list) else [payload]
    results: list[dict] = []
    errors: list[str] = []

    for i, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            errors.append(f"Item {i}: expected a JSON object")
            continue
        try:
            result = _create_from_flat_ndaa(item, db)
            results.append(result)
        except Exception as e:
            db.rollback()
            errors.append(f"Item {i}: {str(e)}")

    return NdaaBulkUploadResponse(created=len(results), requests=results, errors=errors)
