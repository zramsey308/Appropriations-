import os
import uuid
from typing import Optional
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Request, Attachment
from app.models.enums import AttachmentType
from app.services.cpf_service import CPFService


class AttachmentService:
    def __init__(self, db: Session):
        self.db = db

    def upload(
        self,
        request_id: int,
        file: UploadFile,
        attachment_type: AttachmentType = AttachmentType.other,
    ) -> Optional[Attachment]:
        request = self.db.query(Request).filter(Request.id == request_id).first()
        if not request:
            return None

        # Create directory for this request
        request_dir = os.path.join(settings.attachments_dir, str(request_id))
        os.makedirs(request_dir, exist_ok=True)

        # Generate unique filename
        ext = os.path.splitext(file.filename)[1] if file.filename else ""
        unique_filename = f"{uuid.uuid4()}{ext}"
        file_path = os.path.join(request_dir, unique_filename)

        # Save file
        content = file.file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        # Create attachment record
        attachment = Attachment(
            request_id=request_id,
            filename=unique_filename,
            original_filename=file.filename or "unknown",
            file_path=file_path,
            file_size=len(content),
            content_type=file.content_type,
            attachment_type=attachment_type,
        )
        self.db.add(attachment)
        self.db.commit()
        self.db.refresh(attachment)

        # Increment support letters count if this is a CPF support letter
        if attachment_type == AttachmentType.cpf_support_letter:
            cpf_service = CPFService(self.db)
            cpf_service.increment_support_letters(request_id)

        return attachment

    def get(self, attachment_id: int) -> Optional[Attachment]:
        return self.db.query(Attachment).filter(Attachment.id == attachment_id).first()

    def delete(self, attachment_id: int) -> bool:
        attachment = self.get(attachment_id)
        if not attachment:
            return False

        # Delete file
        if os.path.exists(attachment.file_path):
            os.remove(attachment.file_path)

        self.db.delete(attachment)
        self.db.commit()
        return True
