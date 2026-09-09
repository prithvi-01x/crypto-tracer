import json
import hashlib
from decimal import Decimal
from datetime import datetime, date
from typing import Any


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return str(obj)
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return str(obj)


def canonicalize_payload(data: Any) -> str:
    """
    Produce a canonical, deterministic JSON string representation of data
    with sorted keys and compact separators.
    """
    return json.dumps(
        data,
        default=_json_default,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def compute_content_hash(data: Any) -> str:
    """
    Calculate deterministic SHA-256 digest of canonicalized payload.
    Returns 64-character lowercase hex string.
    """
    canonical_str = canonicalize_payload(data)
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
