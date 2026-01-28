from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.db import Base
from app.models.enums import AttachmentType


class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("requests.id", ondelete="CASCADE"), nullable=False, index=True)

    filename = Column(String(500), nullable=False)
    original_filename = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=False)
    file_size = Column(Integer, nullable=True)
    content_type = Column(String(255), nullable=True)
    attachment_type = Column(SQLEnum(AttachmentType), default=AttachmentType.other, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    request = relationship("Request", back_populates="attachments")
