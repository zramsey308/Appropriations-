from fastapi import APIRouter

from app.api.requests import router as requests_router
from app.api.dashboard import router as dashboard_router
from app.api.eligible_accounts import router as accounts_router
from app.api.upload import router as upload_router
from app.api.intake import router as intake_router
from app.api.cpf_upload import router as cpf_upload_router
from app.api.prog_lang_upload import router as prog_lang_upload_router
from app.api.ndaa_upload import router as ndaa_upload_router

api_router = APIRouter()
api_router.include_router(requests_router, prefix="/requests", tags=["requests"])
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(accounts_router, prefix="/eligible-accounts", tags=["eligible-accounts"])
api_router.include_router(upload_router, prefix="/upload", tags=["upload"])
api_router.include_router(intake_router, prefix="/intake", tags=["intake"])
api_router.include_router(cpf_upload_router, prefix="/upload", tags=["cpf-upload"])
api_router.include_router(prog_lang_upload_router, prefix="/upload", tags=["prog-lang-upload"])
api_router.include_router(ndaa_upload_router, prefix="/upload", tags=["ndaa-upload"])
