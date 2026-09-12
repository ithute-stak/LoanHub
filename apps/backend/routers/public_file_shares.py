from datetime import datetime, timezone
from io import BytesIO
from urllib.parse import quote
import hashlib

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database.models.file_management import ManagedFile
from database.models.file_sharing import ExternalFileShare
from database.session import get_db
from services.file_service import read_file_bytes

router = APIRouter(prefix="/public/file-shares", tags=["Public File Shares"])


@router.get('/{token}', name='download_public_file_share')
def download_public_file_share(token: str, db: Session = Depends(get_db)):
    token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
    now = datetime.now(timezone.utc)
    row = (
        db.query(ExternalFileShare)
        .filter(ExternalFileShare.token_hash == token_hash)
        .first()
    )
    expires_at = row.expires_at if row else None
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if not row or row.revoked_at is not None or not expires_at or expires_at <= now:
        raise HTTPException(status_code=404, detail='This share link is invalid or has expired')
    record = db.query(ManagedFile).filter(
        ManagedFile.id == row.file_id,
        ManagedFile.is_deleted.is_(False),
    ).first()
    if not record or record.scan_status == 'quarantined':
        raise HTTPException(status_code=404, detail='Shared file is unavailable')

    content = read_file_bytes(record)
    row.access_count = int(row.access_count or 0) + 1
    row.last_accessed_at = now
    db.commit()

    encoded_name = quote(record.original_name, safe='')
    disposition = 'attachment' if row.allow_download else 'inline'
    return StreamingResponse(
        BytesIO(content),
        media_type=record.mime_type,
        headers={
            'Content-Disposition': f"{disposition}; filename=\"shared-file\"; filename*=UTF-8''{encoded_name}",
            'Content-Length': str(len(content)),
            'Cache-Control': 'private, no-store',
            'X-Content-Type-Options': 'nosniff',
        },
    )
