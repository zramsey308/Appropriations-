"""
Storage abstraction layer.

Uses Supabase Storage in production (when SUPABASE_URL and SUPABASE_SERVICE_KEY
are set) and falls back to local filesystem for local development.
"""
import os
import uuid
from typing import Optional, Tuple

from app.config import settings


def _get_supabase_client():
    from supabase import create_client
    return create_client(settings.supabase_url, settings.supabase_service_key)


def _ensure_bucket():
    """Create the storage bucket if it doesn't exist."""
    client = _get_supabase_client()
    try:
        client.storage.get_bucket(settings.supabase_storage_bucket)
    except Exception:
        client.storage.create_bucket(
            settings.supabase_storage_bucket,
            options={"public": False},
        )


def generate_storage_path(request_id: int, filename: str) -> Tuple[str, str]:
    """Generate a unique storage path. Returns (unique_filename, storage_path)."""
    ext = os.path.splitext(filename)[1] if filename else ""
    unique_filename = f"{uuid.uuid4()}{ext}"
    storage_path = f"{request_id}/{unique_filename}"
    return unique_filename, storage_path


def upload_file(storage_path: str, content: bytes, content_type: str) -> str:
    """
    Upload file content. Returns the storage path used.
    Uses Supabase Storage in production, local filesystem otherwise.
    """
    if settings.use_supabase_storage:
        _ensure_bucket()
        client = _get_supabase_client()
        client.storage.from_(settings.supabase_storage_bucket).upload(
            path=storage_path,
            file=content,
            file_options={"content-type": content_type},
        )
        return storage_path
    else:
        # Local filesystem fallback
        local_path = os.path.join(settings.attachments_dir, storage_path)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(content)
        return local_path


def download_file(storage_path: str) -> Optional[bytes]:
    """Download file content by storage path."""
    if settings.use_supabase_storage:
        client = _get_supabase_client()
        return client.storage.from_(settings.supabase_storage_bucket).download(storage_path)
    else:
        if not os.path.exists(storage_path):
            return None
        with open(storage_path, "rb") as f:
            return f.read()


def delete_file(storage_path: str) -> bool:
    """Delete a file from storage."""
    if settings.use_supabase_storage:
        client = _get_supabase_client()
        client.storage.from_(settings.supabase_storage_bucket).remove([storage_path])
        return True
    else:
        if os.path.exists(storage_path):
            os.remove(storage_path)
        return True
