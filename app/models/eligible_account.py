from sqlalchemy import Column, Integer, String, Boolean, Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.db import Base
from app.models.enums import Subcommittee


class EligibleAccount(Base):
    __tablename__ = "eligible_accounts"

    id = Column(Integer, primary_key=True, index=True)
    subcommittee = Column(SQLEnum(Subcommittee), nullable=False, index=True)
    subcategory = Column(String(255), nullable=True)
    agency = Column(String(255), nullable=False)
    account_name = Column(String(500), nullable=False)
    is_new = Column(Boolean, default=False, nullable=False)
    notes = Column(String(1000), nullable=True)
    active = Column(Boolean, default=True, nullable=False)

    cpf_details = relationship("CPFDetails", back_populates="eligible_account")
