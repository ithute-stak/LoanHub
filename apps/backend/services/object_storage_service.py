from __future__ import annotations

from functools import lru_cache
from pathlib import Path, PurePosixPath
import os
import uuid

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from database.config.config import settings


class StorageUnavailableError(RuntimeError):
    pass


def _safe_key(value: str) -> str:
    key = str(PurePosixPath(value.replace('\\', '/'))).lstrip('/')
    if not key or key == '.' or '..' in PurePosixPath(key).parts:
        raise ValueError('Invalid storage key')
    return key


class LocalObjectStorage:
    provider = 'local'

    def __init__(self, root: str) -> None:
        path = Path(root).expanduser()
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[1] / path
        path.mkdir(parents=True, exist_ok=True)
        self.root = path.resolve()

    def _path(self, key: str) -> Path:
        path = (self.root / _safe_key(key)).resolve()
        if self.root != path and self.root not in path.parents:
            raise ValueError('Invalid storage key')
        return path

    def put(self, key: str, content: bytes) -> None:
        destination = self._path(key)
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

    def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.exists():
            raise FileNotFoundError(key)
        return path.read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class S3ObjectStorage:
    provider = 's3'

    def __init__(self) -> None:
        if not settings.S3_BUCKET:
            raise StorageUnavailableError('S3_BUCKET is required for S3 storage')
        kwargs: dict[str, object] = {
            'service_name': 's3',
            'region_name': settings.S3_REGION,
            'config': Config(s3={'addressing_style': settings.S3_ADDRESSING_STYLE}),
        }
        if settings.S3_ENDPOINT_URL:
            kwargs['endpoint_url'] = settings.S3_ENDPOINT_URL
        if settings.S3_ACCESS_KEY_ID:
            kwargs['aws_access_key_id'] = settings.S3_ACCESS_KEY_ID
        if settings.S3_SECRET_ACCESS_KEY:
            kwargs['aws_secret_access_key'] = settings.S3_SECRET_ACCESS_KEY
        self.client = boto3.client(**kwargs)
        self.bucket = settings.S3_BUCKET
        self.prefix = settings.S3_PREFIX.strip('/')

    def _key(self, key: str) -> str:
        safe = _safe_key(key)
        return f'{self.prefix}/{safe}' if self.prefix else safe

    def put(self, key: str, content: bytes) -> None:
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=self._key(key),
                Body=content,
                ContentType='application/octet-stream',
                ServerSideEncryption='AES256',
            )
        except (BotoCoreError, ClientError) as error:
            raise StorageUnavailableError('Object storage write failed') from error

    def get(self, key: str) -> bytes:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=self._key(key))
            return response['Body'].read()
        except self.client.exceptions.NoSuchKey as error:
            raise FileNotFoundError(key) from error
        except (BotoCoreError, ClientError) as error:
            raise StorageUnavailableError('Object storage read failed') from error

    def delete(self, key: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=self._key(key))
        except (BotoCoreError, ClientError) as error:
            raise StorageUnavailableError('Object storage delete failed') from error


@lru_cache(maxsize=4)
def get_storage(provider: str | None = None):
    selected = (provider or settings.FILE_STORAGE_BACKEND or 'local').strip().lower()
    if selected == 'local':
        return LocalObjectStorage(settings.FILE_STORAGE_PATH)
    if selected in {'s3', 'minio'}:
        return S3ObjectStorage()
    raise ValueError(f'Unsupported file storage backend: {selected}')
