from __future__ import annotations

import hashlib
import os
import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from core.access_control import COMPANY_MANAGEMENT_ROLES, TenantContext
from database.config.config import settings
from database.models.chat import ChatMessageAttachment, ChatMessage, ChatParticipant
from database.models.file_management import ManagedFile
from services.crypto_service import decrypt_file_bytes, encrypt_file_bytes


ALLOWED_MIME_TYPES = {
    'application/pdf',
    'image/jpeg',
    'image/png',
    'image/webp',
    'text/plain',
    'text/csv',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'audio/webm',
    'audio/ogg',
    'audio/mpeg',
    'audio/mp4',
    'audio/wav',
    'audio/x-wav',
}

BLOCKED_EXTENSIONS = {
    'exe', 'dll', 'com', 'bat', 'cmd', 'ps1', 'sh', 'js', 'mjs', 'html',
    'htm', 'svg', 'php', 'py', 'jar', 'apk', 'msi', 'scr', 'vbs',
}

OFFICE_ZIP_TYPES = {
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
}


def storage_root() -> Path:
    root = Path(settings.FILE_STORAGE_PATH).expanduser()
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[1] / root
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def safe_filename(value: str) -> str:
    cleaned = re.sub(r'[^A-Za-z0-9._ -]+', '_', Path(value).name).strip()
    return cleaned[:240] or 'document'


def file_reference() -> str:
    return f'FILE-{uuid.uuid4().hex[:12].upper()}'


def _detect_mime(content: bytes, declared: str, extension: str | None) -> str:
    head = content[:32]
    if head.startswith(b'%PDF-'):
        return 'application/pdf'
    if head.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if head.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if len(head) >= 12 and head[:4] == b'RIFF' and head[8:12] == b'WEBP':
        return 'image/webp'
    if head.startswith(b'OggS'):
        return 'audio/ogg'
    if head.startswith(b'\x1aE\xdf\xa3'):
        return 'audio/webm'
    if len(head) >= 12 and head[:4] == b'RIFF' and head[8:12] == b'WAVE':
        return 'audio/wav'
    if head.startswith(b'ID3') or (len(head) > 1 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0):
        return 'audio/mpeg'
    if len(head) >= 12 and b'ftyp' in head[4:12] and declared.startswith('audio/'):
        return 'audio/mp4'
    if head.startswith(b'PK\x03\x04') and declared in OFFICE_ZIP_TYPES:
        return declared
    if head.startswith(b'\xd0\xcf\x11\xe0') and declared in {
        'application/msword',
        'application/vnd.ms-excel',
    }:
        return declared
    if declared in {'text/plain', 'text/csv'}:
        try:
            content[:8192].decode('utf-8')
            return declared
        except UnicodeDecodeError as error:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail='Text files must use UTF-8 encoding',
            ) from error
    if extension in {'docx', 'xlsx'} and head.startswith(b'PK\x03\x04'):
        return declared
    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail='The file content does not match an allowed document, image, PDF or audio format',
    )


def _validate_content(
    content: bytes,
    *,
    original_name: str,
    declared_mime: str,
) -> tuple[str, str | None]:
    if not content:
        raise HTTPException(status_code=400, detail='The uploaded file is empty')

    extension = Path(original_name).suffix.lower().lstrip('.') or None
    if extension in BLOCKED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail='Executable or active-content files are not allowed',
        )

    detected = _detect_mime(content, declared_mime, extension)
    if detected not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail='This file type is not allowed',
        )
    return detected, extension


def _atomic_write(destination: Path, content: bytes) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f'.{destination.name}.{uuid.uuid4().hex}.tmp')
    try:
        with temporary.open('wb') as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


async def save_upload(
    db: Session,
    upload: UploadFile,
    context: TenantContext,
    *,
    category: str = 'general',
    visibility: str = 'private',
    description: str | None = None,
    linked_entity_type: str | None = None,
    linked_entity_id: str | None = None,
    is_confidential: bool = False,
    company_id=None,
    branch_id=None,
) -> ManagedFile:
    declared_mime = (upload.content_type or 'application/octet-stream').lower()
    original_name = safe_filename(upload.filename or 'document')

    maximum_mb = (
        settings.FILE_AUDIO_MAX_UPLOAD_MB
        if declared_mime.startswith('audio/')
        else settings.FILE_MAX_UPLOAD_MB
    )
    maximum = max(1, maximum_mb) * 1024 * 1024
    content = bytearray()

    try:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            content.extend(chunk)
            if len(content) > maximum:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f'File exceeds the {maximum_mb} MB limit',
                )
    finally:
        await upload.close()

    plaintext = bytes(content)
    detected_mime, extension = _validate_content(
        plaintext,
        original_name=original_name,
        declared_mime=declared_mime,
    )

    reference = file_reference()
    stored_name = f'{uuid.uuid4().hex}.bin' if settings.FILE_ENCRYPTION_ENABLED else (
        f"{uuid.uuid4().hex}{('.' + extension) if extension else ''}"
    )
    relative_key = Path(str(company_id or context.company_id or context.user.id)) / stored_name
    destination = storage_root() / relative_key

    payload = plaintext
    encryption_nonce = None
    encryption_version = None
    if settings.FILE_ENCRYPTION_ENABLED:
        payload, encryption_nonce, encryption_version = encrypt_file_bytes(plaintext)

    _atomic_write(destination, payload)

    record = ManagedFile(
        owner_user_id=context.user.id,
        company_id=company_id if company_id is not None else context.company_id,
        branch_id=branch_id if branch_id is not None else context.branch_id,
        reference=reference,
        original_name=original_name,
        stored_name=stored_name,
        storage_key=str(relative_key),
        storage_provider='local',
        mime_type=detected_mime,
        detected_mime_type=detected_mime,
        extension=extension,
        size_bytes=len(plaintext),
        checksum_sha256=hashlib.sha256(plaintext).hexdigest(),
        is_encrypted=settings.FILE_ENCRYPTION_ENABLED,
        encryption_nonce=encryption_nonce,
        encryption_version=encryption_version,
        scan_status='validated',
        category=category.strip().lower()[:80] or 'general',
        visibility=visibility,
        description=description,
        linked_entity_type=linked_entity_type,
        linked_entity_id=linked_entity_id,
        is_confidential=is_confidential,
    )
    db.add(record)
    db.flush()
    return record


def store_bytes(
    db: Session,
    *,
    content: bytes,
    original_name: str,
    mime_type: str,
    owner_user_id,
    company_id=None,
    branch_id=None,
    category: str,
    visibility: str,
    description: str | None = None,
    linked_entity_type: str | None = None,
    linked_entity_id: str | None = None,
) -> ManagedFile:
    clean_name = safe_filename(original_name)
    detected_mime, extension = _validate_content(
        content,
        original_name=clean_name,
        declared_mime=mime_type,
    )
    stored_name = f'{uuid.uuid4().hex}.bin' if settings.FILE_ENCRYPTION_ENABLED else (
        f"{uuid.uuid4().hex}{('.' + extension) if extension else ''}"
    )
    folder = str(company_id or owner_user_id or 'platform')
    relative_key = Path(folder) / stored_name
    destination = storage_root() / relative_key

    payload = content
    encryption_nonce = None
    encryption_version = None
    if settings.FILE_ENCRYPTION_ENABLED:
        payload, encryption_nonce, encryption_version = encrypt_file_bytes(content)
    _atomic_write(destination, payload)

    record = ManagedFile(
        owner_user_id=owner_user_id,
        company_id=company_id,
        branch_id=branch_id,
        reference=file_reference(),
        original_name=clean_name,
        stored_name=stored_name,
        storage_key=str(relative_key),
        storage_provider='local',
        mime_type=detected_mime,
        detected_mime_type=detected_mime,
        extension=extension,
        size_bytes=len(content),
        checksum_sha256=hashlib.sha256(content).hexdigest(),
        is_encrypted=settings.FILE_ENCRYPTION_ENABLED,
        encryption_nonce=encryption_nonce,
        encryption_version=encryption_version,
        scan_status='validated',
        category=category,
        visibility=visibility,
        description=description,
        linked_entity_type=linked_entity_type,
        linked_entity_id=linked_entity_id,
    )
    db.add(record)
    db.flush()
    return record


def physical_path(file: ManagedFile) -> Path:
    root = storage_root()
    path = (root / file.storage_key).resolve()
    if root != path and root not in path.parents:
        raise HTTPException(status_code=400, detail='Invalid file path')
    return path


def read_file_bytes(file: ManagedFile) -> bytes:
    path = physical_path(file)
    if not path.exists():
        raise HTTPException(status_code=410, detail='Stored file is unavailable')
    content = path.read_bytes()
    if file.is_encrypted:
        try:
            content = decrypt_file_bytes(
                content,
                file.encryption_nonce,
                file.encryption_version,
            )
        except ValueError as error:
            raise HTTPException(
                status_code=500,
                detail='Stored file integrity verification failed',
            ) from error

    checksum = hashlib.sha256(content).hexdigest()
    if checksum != file.checksum_sha256:
        raise HTTPException(
            status_code=500,
            detail='Stored file checksum verification failed',
        )
    return content


def can_access_file(db: Session, context: TenantContext, file: ManagedFile) -> bool:
    if file.is_deleted or file.scan_status == 'quarantined':
        return False
    if context.is_platform_admin:
        return True
    if file.owner_user_id == context.user.id:
        return True
    if file.visibility == 'private':
        return False
    if file.visibility == 'conversation':
        return bool(
            db.query(ChatMessageAttachment.id)
            .join(ChatMessage, ChatMessage.id == ChatMessageAttachment.message_id)
            .join(ChatParticipant, ChatParticipant.conversation_id == ChatMessage.conversation_id)
            .filter(
                ChatMessageAttachment.file_id == file.id,
                ChatParticipant.user_id == context.user.id,
                ChatParticipant.is_active.is_(True),
            )
            .first()
        )
    if file.visibility == 'platform':
        return False
    if not context.company_id or file.company_id != context.company_id:
        return False

    is_company_manager = bool(
        context.staff and context.staff.role in COMPANY_MANAGEMENT_ROLES
    )
    if file.is_confidential and not is_company_manager:
        return False
    if file.visibility == 'company':
        return True
    if file.visibility == 'branch':
        if is_company_manager:
            return True
        return bool(context.branch_id and file.branch_id == context.branch_id)
    return False
