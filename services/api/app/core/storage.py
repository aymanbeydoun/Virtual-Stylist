import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

from app.config import get_settings


class StorageBackend(Protocol):
    async def signed_upload_url(self, key: str, content_type: str) -> tuple[str, datetime]: ...
    async def signed_read_url(self, key: str) -> str: ...
    async def write_bytes(self, key: str, data: bytes) -> None: ...
    async def read_bytes(self, key: str) -> bytes: ...


class LocalStorage:
    def __init__(self, root: str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = self.root / key
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    async def signed_upload_url(self, key: str, content_type: str) -> tuple[str, datetime]:
        url = f"/api/v1/wardrobe/_local_upload/{key}"
        return url, datetime.now(UTC) + timedelta(minutes=15)

    async def signed_read_url(self, key: str) -> str:
        return f"/api/v1/wardrobe/_local_read/{key}"

    async def write_bytes(self, key: str, data: bytes) -> None:
        self._path(key).write_bytes(data)

    async def read_bytes(self, key: str) -> bytes:
        return self._path(key).read_bytes()


class GCSStorage:
    def __init__(self, bucket: str) -> None:
        from google.cloud import storage

        self._client = storage.Client()
        self._bucket = self._client.bucket(bucket)

    async def signed_upload_url(self, key: str, content_type: str) -> tuple[str, datetime]:
        blob = self._bucket.blob(key)
        expires = datetime.now(UTC) + timedelta(minutes=15)
        url = blob.generate_signed_url(
            expiration=expires, method="PUT", content_type=content_type, version="v4"
        )
        return url, expires

    async def signed_read_url(self, key: str) -> str:
        blob = self._bucket.blob(key)
        url: str = blob.generate_signed_url(
            expiration=datetime.now(UTC) + timedelta(hours=1), method="GET", version="v4"
        )
        return url

    async def write_bytes(self, key: str, data: bytes) -> None:
        self._bucket.blob(key).upload_from_string(data)

    async def read_bytes(self, key: str) -> bytes:
        data: bytes = self._bucket.blob(key).download_as_bytes()
        return data


def get_storage() -> StorageBackend:
    settings = get_settings()
    if settings.storage_backend == "gcs":
        if not settings.gcs_bucket:
            raise RuntimeError("GCS_BUCKET must be set when STORAGE_BACKEND=gcs")
        return GCSStorage(settings.gcs_bucket)
    return LocalStorage(settings.storage_local_path)


def new_object_key(prefix: str, content_type: str) -> str:
    ext = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}.get(content_type, "bin")
    return f"{prefix}/{uuid.uuid4()}.{ext}"
