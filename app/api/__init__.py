from fastapi import APIRouter

from app.api.requests import router as requests_router
from app.api.dashboard import router as dashboard_router
from app.api.eligible_accounts import router as accounts_router

api_router = APIRouter()
api_router.include_router(requests_router, prefix="/requests", tags=["requests"])
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(accounts_router, prefix="/eligible-accounts", tags=["eligible-accounts"])
