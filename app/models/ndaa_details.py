from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship

from app.db import Base


class NdaaDetails(Base):
    __tablename__ = "ndaa_details"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("requests.id", ondelete="CASCADE"), unique=True, nullable=False)

    # Section I - General Information
    company_organization = Column(String(500), nullable=True)
    address = Column(Text, nullable=True)
    city = Column(String(255), nullable=True)
    state = Column(String(50), nullable=True, default="TX")
    zip_code = Column(String(20), nullable=True)
    poc_name = Column(String(255), nullable=True)
    poc_is_lobbyist = Column(Boolean, default=False, nullable=False)
    lobbyist_organization = Column(String(500), nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    met_with_congressman = Column(String(500), nullable=True)
    meeting_date = Column(String(50), nullable=True)
    multiple_requests = Column(Boolean, default=False, nullable=False)
    request_priority = Column(String(50), nullable=True)

    # Section II - Budgetary Legislative Proposal
    official_project_name = Column(String(500), nullable=True)
    funding_agency = Column(String(500), nullable=True)
    budget_account = Column(String(500), nullable=True)
    sub_account_1 = Column(String(500), nullable=True)
    sub_account_2 = Column(String(500), nullable=True)
    line_title = Column(String(500), nullable=True)
    line_number = Column(String(100), nullable=True)
    hasc_subcommittee = Column(String(255), nullable=True)
    funded_in_pb = Column(Boolean, default=False, nullable=False)
    program_element = Column(String(255), nullable=True)
    additional_funding_amount = Column(Integer, nullable=True)
    is_scalable = Column(Boolean, default=False, nullable=False)
    scalable_amount = Column(Integer, nullable=True)
    fy26_bill_amount = Column(Integer, nullable=True)
    unfunded_priority_list = Column(Boolean, default=False, nullable=False)
    unfunded_ranking = Column(String(50), nullable=True)
    unfunded_amount = Column(Integer, nullable=True)

    # Section III - Policy Legislative Proposal
    proposed_bill_language = Column(Text, nullable=True)
    proposed_report_language = Column(Text, nullable=True)
    items_of_special_interest = Column(Text, nullable=True)

    # Section IV - Proposal Explanation
    justification = Column(Text, nullable=True)
    program_description = Column(Text, nullable=True)
    military_value = Column(Text, nullable=True)
    tx11_impact = Column(Text, nullable=True)
    partners = Column(Text, nullable=True)
    other_offices_engaged = Column(Text, nullable=True)
    committee_staff_engaged = Column(Text, nullable=True)
    additional_notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    request = relationship("Request", back_populates="ndaa_details")
