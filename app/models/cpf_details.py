from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.db import Base
from app.models.enums import EntityType


class CPFDetails(Base):
    __tablename__ = "cpf_details"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("requests.id", ondelete="CASCADE"), unique=True, nullable=False)

    # CPF Account selection
    cpf_account_id = Column(Integer, ForeignKey("eligible_accounts.id"), nullable=True)

    # TX-11 nexus requirement
    tx11_nexus = Column(Boolean, default=False, nullable=False)
    tx11_nexus_explanation = Column(Text, nullable=True)

    # Entity type
    entity_type = Column(SQLEnum(EntityType), nullable=True)
    entity_name = Column(String(500), nullable=True)
    entity_address = Column(Text, nullable=True)

    # Project info
    project_name = Column(String(500), nullable=True)
    project_address = Column(Text, nullable=True)
    project_description = Column(Text, nullable=True)

    # Funding details
    requested_amount = Column(Integer, nullable=True)
    total_project_cost = Column(Integer, nullable=True)
    cost_share_amount = Column(Integer, nullable=True)
    cost_share_required = Column(Boolean, default=False, nullable=False)
    cost_share_explanation = Column(Text, nullable=True)

    # Justifications
    public_benefit_justification = Column(Text, nullable=True)
    tx11_priority_justification = Column(Text, nullable=True)

    # Stakeholder support
    stakeholders_support = Column(Text, nullable=True)
    support_letters_received = Column(Integer, default=0, nullable=False)

    # Eligibility and compliance
    eligibility_citations = Column(Text, nullable=True)
    timeline = Column(Text, nullable=True)

    # Prior and future funding
    future_federal_funding = Column(Boolean, default=False, nullable=False)
    future_federal_funding_explanation = Column(Text, nullable=True)
    partial_funding_acceptable = Column(Boolean, default=False, nullable=False)
    partial_funding_explanation = Column(Text, nullable=True)

    # Authorization and budget
    authorized_in_law = Column(Boolean, default=False, nullable=False)
    authorization_citation = Column(Text, nullable=True)
    in_presidential_budget = Column(Boolean, default=False, nullable=False)
    presidential_budget_details = Column(Text, nullable=True)

    # Prior funding
    prior_federal_funding = Column(Boolean, default=False, nullable=False)
    prior_funding_details = Column(Text, nullable=True)

    # Derogatory information
    derogatory_info = Column(Boolean, default=False, nullable=False)
    derogatory_info_explanation = Column(Text, nullable=True)

    # Members receiving this request
    members_receiving_request = Column(Text, nullable=True)

    # Selection tracking (hard cap of 15 per FY)
    selected = Column(Boolean, default=False, nullable=False)
    selected_slot = Column(Integer, nullable=True, unique=True)
    selected_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    request = relationship("Request", back_populates="cpf_details")
    eligible_account = relationship("EligibleAccount", back_populates="cpf_details")
