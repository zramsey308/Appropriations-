from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional, List

from app.models.enums import EntityType
from app.schemas.eligible_account import EligibleAccountResponse


class CPFDetailsBase(BaseModel):
    cpf_account_id: Optional[int] = None
    tx11_nexus: Optional[bool] = False
    tx11_nexus_explanation: Optional[str] = None
    entity_type: Optional[EntityType] = None
    entity_name: Optional[str] = None
    entity_address: Optional[str] = None
    project_name: Optional[str] = None
    project_address: Optional[str] = None
    project_description: Optional[str] = None
    requested_amount: Optional[int] = None
    total_project_cost: Optional[int] = None
    cost_share_amount: Optional[int] = None
    cost_share_required: Optional[bool] = False
    cost_share_explanation: Optional[str] = None
    public_benefit_justification: Optional[str] = None
    tx11_priority_justification: Optional[str] = None
    stakeholders_support: Optional[str] = None
    eligibility_citations: Optional[str] = None
    timeline: Optional[str] = None
    future_federal_funding: Optional[bool] = False
    future_federal_funding_explanation: Optional[str] = None
    partial_funding_acceptable: Optional[bool] = False
    partial_funding_explanation: Optional[str] = None
    authorized_in_law: Optional[bool] = False
    authorization_citation: Optional[str] = None
    in_presidential_budget: Optional[bool] = False
    presidential_budget_details: Optional[str] = None
    prior_federal_funding: Optional[bool] = False
    prior_funding_details: Optional[str] = None
    derogatory_info: Optional[bool] = False
    derogatory_info_explanation: Optional[str] = None
    members_receiving_request: Optional[str] = None


class CPFDetailsCreate(CPFDetailsBase):
    pass


class CPFDetailsUpdate(CPFDetailsBase):
    pass


class CPFDetailsResponse(CPFDetailsBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_id: int
    support_letters_received: int
    selected: bool
    selected_slot: Optional[int] = None
    selected_at: Optional[datetime] = None
    eligible_account: Optional[EligibleAccountResponse] = None
    created_at: datetime
    updated_at: datetime


class CPFValidationItem(BaseModel):
    field: str
    requirement: str
    passed: bool
    message: str


class CPFValidationResult(BaseModel):
    passed: bool
    items: List[CPFValidationItem]
    missing_requirements: List[str]
