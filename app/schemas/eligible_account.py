from pydantic import BaseModel
from typing import Optional

from app.models.enums import Subcommittee


class EligibleAccountResponse(BaseModel):
    id: int
    subcommittee: Subcommittee
    subcategory: Optional[str] = None
    agency: str
    account_name: str
    is_new: bool
    notes: Optional[str] = None
    active: bool

    class Config:
        from_attributes = True
