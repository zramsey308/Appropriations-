from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional

from app.models.enums import AttachmentType


class AttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_id: int
    filename: str
    original_filename: str
    file_path: str
    file_size: Optional[int] = None
    content_type: Optional[str] = None
    attachment_type: AttachmentType
    created_at: datetime
