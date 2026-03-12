from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional


class NdaaDetailsBase(BaseModel):
    # Section I - General Information
    company_organization: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = "TX"
    zip_code: Optional[str] = None
    poc_name: Optional[str] = None
    poc_is_lobbyist: Optional[bool] = False
    lobbyist_organization: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    met_with_congressman: Optional[str] = None
    meeting_date: Optional[str] = None
    multiple_requests: Optional[bool] = False
    request_priority: Optional[str] = None

    # Section II - Budgetary Legislative Proposal
    official_project_name: Optional[str] = None
    funding_agency: Optional[str] = None
    budget_account: Optional[str] = None
    sub_account_1: Optional[str] = None
    sub_account_2: Optional[str] = None
    line_title: Optional[str] = None
    line_number: Optional[str] = None
    hasc_subcommittee: Optional[str] = None
    funded_in_pb: Optional[bool] = False
    program_element: Optional[str] = None
    additional_funding_amount: Optional[int] = None
    is_scalable: Optional[bool] = False
    scalable_amount: Optional[int] = None
    fy26_bill_amount: Optional[int] = None
    unfunded_priority_list: Optional[bool] = False
    unfunded_ranking: Optional[str] = None
    unfunded_amount: Optional[int] = None

    # Section III - Policy Legislative Proposal
    proposed_bill_language: Optional[str] = None
    proposed_report_language: Optional[str] = None
    items_of_special_interest: Optional[str] = None

    # Section IV - Proposal Explanation
    justification: Optional[str] = None
    program_description: Optional[str] = None
    military_value: Optional[str] = None
    tx11_impact: Optional[str] = None
    partners: Optional[str] = None
    other_offices_engaged: Optional[str] = None
    committee_staff_engaged: Optional[str] = None
    additional_notes: Optional[str] = None


class NdaaDetailsCreate(NdaaDetailsBase):
    pass


class NdaaDetailsUpdate(NdaaDetailsBase):
    pass


class NdaaDetailsResponse(NdaaDetailsBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_id: int
    created_at: datetime
    updated_at: datetime
