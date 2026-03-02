from pydantic import BaseModel, ConfigDict
from typing import Optional

from app.models.enums import Subcommittee


class EligibleAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subcommittee: Subcommittee
    subcategory: Optional[str] = None
    agency: str
    account_name: str
    is_new: bool
    notes: Optional[str] = None
    active: bool
