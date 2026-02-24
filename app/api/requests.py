from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.enums import RequestType, Subcommittee, RequestStatus, AttachmentType
from app.models import Attachment
from app.schemas import (
    RequestCreate,
    RequestUpdate,
    RequestResponse,
    RequestListResponse,
    CPFDetailsCreate,
    CPFDetailsUpdate,
    CPFDetailsResponse,
    CPFValidationResult,
    AttachmentResponse,
)
from app.services import RequestService, CPFService, AttachmentService

router = APIRouter()


@router.post("", response_model=RequestResponse, status_code=201)
def create_request(data: RequestCreate, db: Session = Depends(get_db)):
    """Create a new appropriations request."""
    service = RequestService(db)
    request = service.create(data)
    return request


@router.get("", response_model=RequestListResponse)
def list_requests(
    fy: Optional[int] = None,
    type: Optional[RequestType] = None,
    subcommittee: Optional[Subcommittee] = None,
    status: Optional[RequestStatus] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """List appropriations requests with optional filters."""
    service = RequestService(db)
    items, total = service.list(
        fy=fy,
        request_type=type,
        subcommittee=subcommittee,
        status=status,
        skip=skip,
        limit=limit,
    )
    return RequestListResponse(items=items, total=total)


@router.get("/{request_id}", response_model=RequestResponse)
def get_request(request_id: int, db: Session = Depends(get_db)):
    """Get a single request by ID."""
    service = RequestService(db)
    request = service.get(request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    return request


@router.patch("/{request_id}", response_model=RequestResponse)
def update_request(request_id: int, data: RequestUpdate, db: Session = Depends(get_db)):
    """Update a request."""
    service = RequestService(db)
    request = service.update(request_id, data)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    return request


@router.delete("/{request_id}", status_code=204)
def delete_request(request_id: int, db: Session = Depends(get_db)):
    """Delete a request."""
    service = RequestService(db)
    if not service.delete(request_id):
        raise HTTPException(status_code=404, detail="Request not found")


@router.post("/{request_id}/cpf", response_model=CPFDetailsResponse, status_code=201)
def create_or_update_cpf_details(
    request_id: int,
    data: CPFDetailsCreate,
    db: Session = Depends(get_db),
):
    """Create or update CPF details for a request."""
    service = CPFService(db)
    try:
        cpf_details = service.create_or_update(request_id, data)
        if not cpf_details:
            raise HTTPException(status_code=404, detail="Request not found")
        return cpf_details
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{request_id}/cpf", response_model=CPFDetailsResponse)
def get_cpf_details(request_id: int, db: Session = Depends(get_db)):
    """Get CPF details for a request."""
    service = CPFService(db)
    cpf_details = service.get_by_request(request_id)
    if not cpf_details:
        raise HTTPException(status_code=404, detail="CPF details not found")
    return cpf_details


@router.post("/{request_id}/cpf/validate", response_model=CPFValidationResult)
def validate_cpf(request_id: int, db: Session = Depends(get_db)):
    """Validate CPF compliance for a request."""
    service = CPFService(db)
    return service.validate(request_id)


@router.post("/{request_id}/cpf/select", response_model=CPFDetailsResponse)
def select_cpf(
    request_id: int,
    slot: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Select a CPF request for funding (enforces 15 cap)."""
    service = CPFService(db)
    try:
        cpf_details = service.select(request_id, slot)
        return cpf_details
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{request_id}/attachments", response_model=List[AttachmentResponse])
def list_attachments(request_id: int, db: Session = Depends(get_db)):
    """List all attachments for a request."""
    attachments = db.query(Attachment).filter(Attachment.request_id == request_id).all()
    return attachments


@router.post("/{request_id}/attachments", response_model=AttachmentResponse, status_code=201)
def upload_attachment(
    request_id: int,
    file: UploadFile = File(...),
    attachment_type: AttachmentType = Form(AttachmentType.other),
    db: Session = Depends(get_db),
):
    """Upload an attachment for a request."""
    service = AttachmentService(db)
    attachment = service.upload(request_id, file, attachment_type)
    if not attachment:
        raise HTTPException(status_code=404, detail="Request not found")
    return attachment


@router.get("/{request_id}/attachments/{attachment_id}/download")
def download_attachment(request_id: int, attachment_id: int, db: Session = Depends(get_db)):
    """Download an attachment file."""
    attachment = db.query(Attachment).filter(
        Attachment.id == attachment_id,
        Attachment.request_id == request_id
    ).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    service = AttachmentService(db)
    content = service.download(attachment)
    if content is None:
        raise HTTPException(status_code=404, detail="File not found in storage")

    return Response(
        content=content,
        media_type=attachment.content_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{attachment.original_filename}"'
        },
    )


@router.delete("/{request_id}/attachments/{attachment_id}", status_code=204)
def delete_attachment(request_id: int, attachment_id: int, db: Session = Depends(get_db)):
    """Delete an attachment."""
    service = AttachmentService(db)
    attachment = service.get(attachment_id)
    if not attachment or attachment.request_id != request_id:
        raise HTTPException(status_code=404, detail="Attachment not found")
    service.delete(attachment_id)
