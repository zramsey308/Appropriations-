from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import DashboardSummary
from app.services import RequestService

router = APIRouter()


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    fy: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Get dashboard summary statistics."""
    service = RequestService(db)
    return service.get_dashboard_summary(fy)
