from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional, List

from app.models.enums import RequestType, Subcommittee, RequestStatus
from app.schemas.cpf_details import CPFDetailsResponse
from app.schemas.attachment import AttachmentResponse


class RequestBase(BaseModel):
    fiscal_year: Optional[int] = 2027
    request_type: RequestType
    subcommittee: Subcommittee
    title: str
    description: Optional[str] = None
    requester_name: Optional[str] = None
    requester_email: Optional[str] = None
    requester_phone: Optional[str] = None
    requester_organization: Optional[str] = None
    requested_amount: Optional[int] = None
    program_name: Optional[str] = None
    agency: Optional[str] = None
    bureau: Optional[str] = None
    account: Optional[str] = None
    program_funding: Optional[str] = None
    programmatic_justification: Optional[str] = None
    bill_section: Optional[str] = None
    proposed_language: Optional[str] = None
    language_justification: Optional[str] = None
    language_location: Optional[str] = None
    priority_rank: Optional[str] = None
    problem_statement: Optional[str] = None
    goals_outcomes: Optional[str] = None
    other_members: Optional[str] = None
    prior_year_submission: Optional[bool] = None
    prior_year_details: Optional[str] = None
    priority_order: Optional[int] = None
    assigned_to: Optional[str] = None
    notes: Optional[str] = None


class RequestCreate(RequestBase):
    status: Optional[RequestStatus] = RequestStatus.submitted


class RequestUpdate(BaseModel):
    fiscal_year: Optional[int] = None
    request_type: Optional[RequestType] = None
    subcommittee: Optional[Subcommittee] = None
    status: Optional[RequestStatus] = None
    title: Optional[str] = None
    description: Optional[str] = None
    requester_name: Optional[str] = None
    requester_email: Optional[str] = None
    requester_phone: Optional[str] = None
    requester_organization: Optional[str] = None
    requested_amount: Optional[int] = None
    program_name: Optional[str] = None
    agency: Optional[str] = None
    bureau: Optional[str] = None
    account: Optional[str] = None
    program_funding: Optional[str] = None
    programmatic_justification: Optional[str] = None
    bill_section: Optional[str] = None
    proposed_language: Optional[str] = None
    language_justification: Optional[str] = None
    language_location: Optional[str] = None
    priority_rank: Optional[str] = None
    priority_order: Optional[int] = None
    problem_statement: Optional[str] = None
    goals_outcomes: Optional[str] = None
    other_members: Optional[str] = None
    prior_year_submission: Optional[bool] = None
    prior_year_details: Optional[str] = None
    assigned_to: Optional[str] = None
    notes: Optional[str] = None


class RequestResponse(RequestBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: RequestStatus
    priority_order: Optional[int] = None
    cpf_details: Optional[CPFDetailsResponse] = None
    attachments: List[AttachmentResponse] = []
    created_at: datetime
    updated_at: datetime


class RequestListResponse(BaseModel):
    items: List[RequestResponse]
    total: int
