import abc
import os
import hmac
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional, Dict, Any, Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from backend.app.config import settings
from backend.app.core.crypto import get_encryption_key, NONCE_LENGTH_BYTES


class StorageBackendType(str, Enum):
    MEMORY = "memory"
    LOCAL = "local"
    S3 = "s3"
    MINIO = "minio"


class EncryptionMode(str, Enum):
    NONE = "none"
    SSE_S3 = "sse-s3"
    SSE_KMS = "sse-kms"
    CLIENT_AES_GCM = "client-aes-gcm"


@dataclass
class StoredDocument:
    key: str
    size_bytes: int
    content_hash: str  # SHA-256
    storage_backend: str
    content_type: str = "application/pdf"
    encryption_mode: str = EncryptionMode.NONE.value
    encryption_metadata: Dict[str, Any] = field(default_factory=dict)
    stored_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class StorageProvider(abc.ABC):
    """Abstract interface for encrypted document storage and pre-signed URL generation."""

    @property
    @abc.abstractmethod
    def backend_type(self) -> StorageBackendType:
        raise NotImplementedError

    @abc.abstractmethod
    async def put_object(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/pdf",
        encrypt: bool = True,
        metadata: Optional[Dict[str, str]] = None,
    ) -> StoredDocument:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_object(self, key: str) -> Tuple[bytes, StoredDocument]:
        raise NotImplementedError

    @abc.abstractmethod
    async def generate_presigned_url(
        self,
        key: str,
        expires_in_seconds: int = 900,
        filename: Optional[str] = None,
        tenant_id: Optional[str] = None,
        report_id: Optional[str] = None,
    ) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    async def delete_object(self, key: str) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    async def exists(self, key: str) -> bool:
        raise NotImplementedError


class MemoryStorageProvider(StorageProvider):
    """Hermetic in-memory storage for unit tests with zero disk/network dependencies."""

    def __init__(self):
        self._vault: Dict[str, Tuple[bytes, StoredDocument]] = {}

    @property
    def backend_type(self) -> StorageBackendType:
        return StorageBackendType.MEMORY

    async def put_object(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/pdf",
        encrypt: bool = False,
        metadata: Optional[Dict[str, str]] = None,
    ) -> StoredDocument:
        content_hash = hashlib.sha256(data).hexdigest()
        doc = StoredDocument(
            key=key,
            size_bytes=len(data),
            content_hash=content_hash,
            storage_backend=self.backend_type.value,
            content_type=content_type,
            encryption_mode=EncryptionMode.NONE.value,
            encryption_metadata=metadata or {},
        )
        self._vault[key] = (data, doc)
        return doc

    async def get_object(self, key: str) -> Tuple[bytes, StoredDocument]:
        if key not in self._vault:
            raise KeyError(f"Object '{key}' not found in memory vault.")
        return self._vault[key]

    async def generate_presigned_url(
        self,
        key: str,
        expires_in_seconds: int = 900,
        filename: Optional[str] = None,
        tenant_id: Optional[str] = None,
        report_id: Optional[str] = None,
    ) -> str:
        exp = int((datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)).timestamp())
        sig = hmac.new(
            settings.secret_key_value.encode("utf-8"),
            f"{key}:{exp}:{tenant_id or ''}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        target_id = report_id or os.path.basename(key).split(".")[0]
        return f"/api/v1/reports/{target_id}/download?token={sig}&expires={exp}&tenant={tenant_id or ''}"

    async def delete_object(self, key: str) -> bool:
        return bool(self._vault.pop(key, None))

    async def exists(self, key: str) -> bool:
        return key in self._vault


class LocalStorageProvider(StorageProvider):
    """Local filesystem storage with AES-256-GCM encryption at rest."""

    def __init__(self, base_dir: Optional[str] = None, encrypt_at_rest: bool = True):
        self.base_dir = os.path.abspath(base_dir or settings.REPORTS_DIR)
        self.encrypt_at_rest = encrypt_at_rest
        os.makedirs(self.base_dir, exist_ok=True)

    @property
    def backend_type(self) -> StorageBackendType:
        return StorageBackendType.LOCAL

    def _resolve_path(self, key: str) -> str:
        safe_key = os.path.normpath(key).lstrip(os.sep)
        full_path = os.path.abspath(os.path.join(self.base_dir, safe_key))
        if not full_path.startswith(self.base_dir):
            raise ValueError(f"Path traversal detected: {key}")
        return full_path

    async def put_object(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/pdf",
        encrypt: bool = True,
        metadata: Optional[Dict[str, str]] = None,
    ) -> StoredDocument:
        full_path = self._resolve_path(key)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        content_hash = hashlib.sha256(data).hexdigest()

        if self.encrypt_at_rest and encrypt:
            aes_key = get_encryption_key()
            aesgcm = AESGCM(aes_key)
            nonce = os.urandom(NONCE_LENGTH_BYTES)
            ciphertext = aesgcm.encrypt(nonce, data, associated_data=key.encode("utf-8"))
            payload_to_write = nonce + ciphertext
            enc_mode = EncryptionMode.CLIENT_AES_GCM.value
            enc_meta = {"algorithm": "AES-256-GCM", "nonce_bytes": NONCE_LENGTH_BYTES}
        else:
            payload_to_write = data
            enc_mode = EncryptionMode.NONE.value
            enc_meta = {}

        with open(full_path, "wb") as f:
            f.write(payload_to_write)

        return StoredDocument(
            key=key,
            size_bytes=len(data),
            content_hash=content_hash,
            storage_backend=self.backend_type.value,
            content_type=content_type,
            encryption_mode=enc_mode,
            encryption_metadata=enc_meta,
        )

    async def get_object(self, key: str) -> Tuple[bytes, StoredDocument]:
        full_path = self._resolve_path(key)
        if not os.path.exists(full_path):
            raise KeyError(f"Object '{key}' not found on local storage.")

        with open(full_path, "rb") as f:
            raw_bytes = f.read()

        # Decrypt if payload is encrypted with AES-256-GCM
        try:
            aes_key = get_encryption_key()
            aesgcm = AESGCM(aes_key)
            nonce = raw_bytes[:NONCE_LENGTH_BYTES]
            ciphertext = raw_bytes[NONCE_LENGTH_BYTES:]
            decrypted = aesgcm.decrypt(nonce, ciphertext, associated_data=key.encode("utf-8"))
            data = decrypted
            enc_mode = EncryptionMode.CLIENT_AES_GCM.value
        except Exception:
            # Fallback for unencrypted legacy or plain files
            data = raw_bytes
            enc_mode = EncryptionMode.NONE.value

        doc = StoredDocument(
            key=key,
            size_bytes=len(data),
            content_hash=hashlib.sha256(data).hexdigest(),
            storage_backend=self.backend_type.value,
            content_type="application/pdf",
            encryption_mode=enc_mode,
        )
        return data, doc

    async def generate_presigned_url(
        self,
        key: str,
        expires_in_seconds: int = 900,
        filename: Optional[str] = None,
        tenant_id: Optional[str] = None,
        report_id: Optional[str] = None,
    ) -> str:
        exp = int((datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)).timestamp())
        sig = hmac.new(
            settings.secret_key_value.encode("utf-8"),
            f"{key}:{exp}:{tenant_id or ''}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        target_id = report_id or os.path.basename(key).split(".")[0]
        return f"/api/v1/reports/{target_id}/download?token={sig}&expires={exp}&tenant={tenant_id or ''}"

    async def delete_object(self, key: str) -> bool:
        full_path = self._resolve_path(key)
        if os.path.exists(full_path):
            os.remove(full_path)
            return True
        return False

    async def exists(self, key: str) -> bool:
        full_path = self._resolve_path(key)
        return os.path.exists(full_path)


class S3StorageProvider(StorageProvider):
    """AWS S3 & MinIO storage provider with SSE-S3/KMS and lazy boto3 import."""

    def __init__(
        self,
        bucket_name: str,
        endpoint_url: Optional[str] = None,
        region_name: str = "us-east-1",
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        sse_mode: str = "AES256",
        kms_key_id: Optional[str] = None,
    ):
        self.bucket_name = bucket_name
        self.endpoint_url = endpoint_url
        self.region_name = region_name
        self.access_key = access_key
        self.secret_key = secret_key
        self.sse_mode = sse_mode
        self.kms_key_id = kms_key_id
        self._client = None

    @property
    def backend_type(self) -> StorageBackendType:
        return StorageBackendType.S3

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            import boto3
            from botocore.config import Config
        except ImportError:
            raise RuntimeError("boto3 is required for S3StorageProvider. Install boto3 or configure LocalStorageProvider.")

        config = Config(signature_version="s3v4", retries={"max_attempts": 3, "mode": "standard"})
        self._client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            region_name=self.region_name,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            config=config,
        )
        return self._client

    async def put_object(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/pdf",
        encrypt: bool = True,
        metadata: Optional[Dict[str, str]] = None,
    ) -> StoredDocument:
        client = self._get_client()
        content_hash = hashlib.sha256(data).hexdigest()

        extra_args: Dict[str, Any] = {
            "Bucket": self.bucket_name,
            "Key": key,
            "Body": data,
            "ContentType": content_type,
            "Metadata": metadata or {},
        }
        if encrypt:
            if self.sse_mode == "aws:kms" and self.kms_key_id:
                extra_args["ServerSideEncryption"] = "aws:kms"
                extra_args["SSEKMSKeyId"] = self.kms_key_id
            else:
                extra_args["ServerSideEncryption"] = "AES256"

        client.put_object(**extra_args)

        return StoredDocument(
            key=key,
            size_bytes=len(data),
            content_hash=content_hash,
            storage_backend=self.backend_type.value,
            content_type=content_type,
            encryption_mode=EncryptionMode.SSE_S3.value if encrypt else EncryptionMode.NONE.value,
        )

    async def get_object(self, key: str) -> Tuple[bytes, StoredDocument]:
        client = self._get_client()
        response = client.get_object(Bucket=self.bucket_name, Key=key)
        data = response["Body"].read()
        doc = StoredDocument(
            key=key,
            size_bytes=len(data),
            content_hash=hashlib.sha256(data).hexdigest(),
            storage_backend=self.backend_type.value,
            content_type=response.get("ContentType", "application/pdf"),
        )
        return data, doc

    async def generate_presigned_url(
        self,
        key: str,
        expires_in_seconds: int = 900,
        filename: Optional[str] = None,
        tenant_id: Optional[str] = None,
        report_id: Optional[str] = None,
    ) -> str:
        client = self._get_client()
        params = {"Bucket": self.bucket_name, "Key": key}
        if filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'
        return client.generate_presigned_url("get_object", Params=params, ExpiresIn=expires_in_seconds)

    async def delete_object(self, key: str) -> bool:
        client = self._get_client()
        client.delete_object(Bucket=self.bucket_name, Key=key)
        return True

    async def exists(self, key: str) -> bool:
        client = self._get_client()
        try:
            client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except Exception:
            return False


_storage_provider_instance: Optional[StorageProvider] = None


def get_storage_service(backend_type: Optional[str] = None) -> StorageProvider:
    """Factory retrieving the configured StorageProvider."""
    global _storage_provider_instance
    if _storage_provider_instance is not None and backend_type is None:
        return _storage_provider_instance

    b_type = (backend_type or getattr(settings, "STORAGE_BACKEND", "LOCAL")).upper()
    if b_type == "MEMORY":
        provider = MemoryStorageProvider()
    elif b_type in ("S3", "MINIO") and settings.APP_ENV.lower() == "production":
        provider = S3StorageProvider(
            bucket_name=getattr(settings, "S3_BUCKET_NAME", "crypto-tracer-vault"),
            endpoint_url=getattr(settings, "S3_ENDPOINT_URL", None),
            access_key=getattr(settings, "AWS_ACCESS_KEY_ID", None),
            secret_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", None),
        )
    else:
        provider = LocalStorageProvider(base_dir=settings.REPORTS_DIR, encrypt_at_rest=True)

    if backend_type is None:
        _storage_provider_instance = provider
    return provider


def set_storage_service(provider: Optional[StorageProvider]) -> None:
    """Set or reset the global storage provider instance (useful for unit tests)."""
    global _storage_provider_instance
    _storage_provider_instance = provider
