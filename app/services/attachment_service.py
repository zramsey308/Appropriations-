import os
import uuid
from typing import Optional
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Request, Attachment
from app.models.enums import AttachmentType
from app.services.cpf_service import CPFService
from app.services import storage


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

        # Read file content
        content = file.file.read()

        # Generate unique filename and storage path
        unique_filename, storage_path = storage.generate_storage_path(
            request_id, file.filename or "unknown"
        )

        # Upload to storage (Supabase or local filesystem)
        file_path = storage.upload_file(
            storage_path, content, file.content_type or "application/octet-stream"
        )

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

    def download(self, attachment: Attachment) -> Optional[bytes]:
        """Download file content from storage."""
        return storage.download_file(attachment.file_path)

    def delete(self, attachment_id: int) -> bool:
        attachment = self.get(attachment_id)
        if not attachment:
            return False

        # Delete file from storage (Supabase or local filesystem)
        storage.delete_file(attachment.file_path)

        self.db.delete(attachment)
        self.db.commit()
        return True
