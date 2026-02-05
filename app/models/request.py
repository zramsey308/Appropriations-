from datetime import datetime
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Text
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

    # Programmatic fields
    program_name = Column(String(500), nullable=True)
    requested_amount = Column(BigInteger, nullable=True)  # Changed to BigInteger for large funding amounts
    programmatic_justification = Column(Text, nullable=True)

    # Language fields
    bill_section = Column(String(255), nullable=True)
    proposed_language = Column(Text, nullable=True)
    language_justification = Column(Text, nullable=True)

    # Routing
    assigned_to = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    cpf_details = relationship("CPFDetails", back_populates="request", uselist=False, cascade="all, delete-orphan")
    attachments = relationship("Attachment", back_populates="request", cascade="all, delete-orphan")
