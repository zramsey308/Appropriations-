from datetime import datetime
from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DateTime, Text
from sqlalchemy.orm import relationship

from app.db import Base


class Request(Base):
    __tablename__ = "requests"

    id = Column(Integer, primary_key=True, index=True)
    fiscal_year = Column(Integer, nullable=False, default=2027, index=True)
    request_type = Column(String(50), nullable=False, index=True)
    subcommittee = Column(String(100), nullable=False, index=True)
    status = Column(String(50), default="draft", nullable=False, index=True)

    # General intake fields
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    requester_name = Column(String(255), nullable=True)
    requester_email = Column(String(255), nullable=True)
    requester_phone = Column(String(50), nullable=True)
    requester_organization = Column(String(255), nullable=True)

    # Shared funding field
    requested_amount = Column(BigInteger, nullable=True)

    # Programmatic fields
    program_name = Column(String(500), nullable=True)
    agency = Column(String(500), nullable=True)
    bureau = Column(String(500), nullable=True)
    account = Column(String(500), nullable=True)
    program_funding = Column(String(100), nullable=True)  # "increase", "new", "maintain", etc.
    programmatic_justification = Column(Text, nullable=True)

    # Defense programmatic fields
    component = Column(String(500), nullable=True)
    budget_activity = Column(String(500), nullable=True)
    program_element = Column(String(255), nullable=True)
    line_number = Column(String(255), nullable=True)
    project_program_name = Column(String(500), nullable=True)
    funding_amount_enacted_previous_year = Column(BigInteger, nullable=True)
    funding_amount_presidents_budget = Column(BigInteger, nullable=True)
    location = Column(String(500), nullable=True)

    # Language fields
    bill_section = Column(String(255), nullable=True)
    proposed_language = Column(Text, nullable=True)
    language_justification = Column(Text, nullable=True)
    language_location = Column(String(500), nullable=True)

    # Programmatic / Language shared fields
    priority_rank = Column(String(50), nullable=True)
    problem_statement = Column(Text, nullable=True)
    goals_outcomes = Column(Text, nullable=True)
    other_members = Column(Text, nullable=True)
    prior_year_submission = Column(Boolean, nullable=True)
    prior_year_details = Column(Text, nullable=True)

    # Priority ordering (for drag-reorder in CPF expanded view)
    priority_order = Column(Integer, nullable=True, index=True)

    # Routing
    assigned_to = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    cpf_details = relationship("CPFDetails", back_populates="request", uselist=False, cascade="all, delete-orphan")
    ndaa_details = relationship("NdaaDetails", back_populates="request", uselist=False, cascade="all, delete-orphan")
    attachments = relationship("Attachment", back_populates="request", cascade="all, delete-orphan")
