from typing import Optional, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import EligibleAccount
from app.models.enums import Subcommittee
from app.schemas import EligibleAccountResponse

router = APIRouter()


@router.get("", response_model=List[EligibleAccountResponse])
def list_eligible_accounts(
    subcommittee: Optional[Subcommittee] = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
):
    """List eligible CPF accounts."""
    query = db.query(EligibleAccount)

    if subcommittee:
        query = query.filter(EligibleAccount.subcommittee == subcommittee)
    if active_only:
        query = query.filter(EligibleAccount.active == True)

    return query.order_by(EligibleAccount.subcommittee, EligibleAccount.subcategory, EligibleAccount.account_name).all()


@router.get("/{account_id}", response_model=EligibleAccountResponse)
def get_eligible_account(account_id: int, db: Session = Depends(get_db)):
    """Get a single eligible account by ID."""
    account = db.query(EligibleAccount).filter(EligibleAccount.id == account_id).first()
    if not account:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Eligible account not found")
    return account
