import json
import hashlib
from decimal import Decimal
from datetime import datetime, date, timezone
from typing import Any, Union


def normalize_timestamp(dt: Union[datetime, date, str]) -> str:
    """Normalize timestamp to deterministic UTC ISO 8601 string with microsecond precision."""
    if isinstance(dt, str):
        # Handle ISO strings with Z or timezone offset
        clean_str = dt.replace("Z", "+00:00")
        try:
            dt_obj = datetime.fromisoformat(clean_str)
        except ValueError:
            return dt
    elif isinstance(dt, datetime):
        dt_obj = dt
    elif isinstance(dt, date):
        dt_obj = datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
    else:
        return str(dt)

    if dt_obj.tzinfo is None:
        dt_obj = dt_obj.replace(tzinfo=timezone.utc)
    else:
        dt_obj = dt_obj.astimezone(timezone.utc)

    return dt_obj.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return str(obj)
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    if hasattr(obj, "value"):
        return obj.value
    return str(obj)


def _normalize_obj(obj: Any) -> Any:
    """Recursively normalize objects for deterministic RFC 8785 canonical JSON serialization."""
    if obj is None or isinstance(obj, (int, float, str, bool)):
        return obj
    if isinstance(obj, (datetime, date)):
        return normalize_timestamp(obj)
    if isinstance(obj, Decimal):
        return str(obj)
    if hasattr(obj, "model_dump"):
        return _normalize_obj(obj.model_dump(mode="json"))
    if hasattr(obj, "value"):
        return _normalize_obj(obj.value)
    if hasattr(obj, "__dict__"):
        return _normalize_obj(obj.__dict__)
    if isinstance(obj, dict):
        return {str(k): _normalize_obj(v) for k, v in sorted(obj.items(), key=lambda x: str(x[0]))}
    if isinstance(obj, (list, tuple, set)):
        return [_normalize_obj(x) for x in obj]
    return str(obj)


def canonicalize_rfc8785(data: Any) -> str:
    """
    RFC 8785 compliant canonical JSON serialization:
    - Keys sorted lexicographically
    - Compact separators (no whitespace around ',' and ':')
    - UTF-8 characters preserved without ASCII escaping
    """
    normalized = _normalize_obj(data)
    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


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
        ensure_ascii=False,
    )


def compute_content_hash(data: Any) -> str:
    """
    Calculate deterministic SHA-256 digest of canonicalized payload.
    Returns 64-character lowercase hex string.
    """
    canonical_str = canonicalize_payload(data)
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


def compute_genesis_hash(case_id: str) -> str:
    """
    Genesis block anchor:
    Hash_0 = SHA256("GENESIS:" || case_id)
    """
    message = f"GENESIS:{case_id}"
    return hashlib.sha256(message.encode("utf-8")).hexdigest()


def compute_chain_hash(
    prev_hash: str,
    canonical_payload: str,
    timestamp: Union[datetime, date, str],
    actor_id: str,
) -> str:
    """
    Cryptographic hash chain formula:
    Hash_i = SHA256(Hash_{i-1} || ":" || CanonicalPayload_i || ":" || Timestamp_i || ":" || ActorID_i)
    Uses ':' delimiter to prevent boundary ambiguity.
    """
    ts_str = normalize_timestamp(timestamp)
    message = f"{prev_hash}:{canonical_payload}:{ts_str}:{actor_id}"
    return hashlib.sha256(message.encode("utf-8")).hexdigest()
