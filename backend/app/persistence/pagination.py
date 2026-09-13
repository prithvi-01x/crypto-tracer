"""
Generic Keyset / Cursor-Based Pagination Engine for Crypto-Tracer.
Provides URL-safe Base64 cursor encoding/decoding and dialect-safe SQLAlchemy query building.
"""
import base64
from datetime import datetime, timezone
from typing import Optional, Tuple, TypeVar, List, Any
from sqlalchemy import Select, and_, or_, desc, asc

T = TypeVar("T")


def encode_cursor(dt: datetime, item_id: str) -> str:
    """
    Encodes a datetime timestamp and primary key into a URL-safe Base64 cursor.
    Ensures UTC timezone awareness.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    raw = f"{dt.isoformat()}|{item_id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def decode_cursor(cursor: str) -> Tuple[datetime, str]:
    """
    Decodes a URL-safe Base64 cursor into a tuple of (datetime, item_id).
    Raises ValueError on malformed, corrupted, or non-Base64 cursor inputs.
    """
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        parts = raw.split("|", 1)
        if len(parts) != 2:
            raise ValueError("Expected format 'timestamp|id'")
        iso_str = parts[0]
        if iso_str.endswith("Z"):
            iso_str = iso_str[:-1] + "+00:00"
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt, parts[1]
    except Exception as ex:
        raise ValueError(f"Malformed pagination cursor: {ex}") from ex


def apply_keyset_pagination(
    query: Select,
    model_cls: Any,
    cursor: Optional[str] = None,
    limit: int = 50,
    timestamp_col_name: str = "created_at",
    id_col_name: str = "id",
    descending: bool = True,
) -> Tuple[Select, Optional[Tuple[datetime, str]]]:
    """
    Applies keyset condition and deterministic tie-breaker sorting to a query.
    Fetches limit + 1 records to enable lookahead has_more evaluation without an extra COUNT query.
    """
    ts_col = getattr(model_cls, timestamp_col_name)
    id_col = getattr(model_cls, id_col_name)

    decoded = None
    if cursor:
        decoded = decode_cursor(cursor)
        cur_dt, cur_id = decoded
        if descending:
            # (timestamp, id) < (cur_dt, cur_id)
            query = query.where(
                or_(
                    ts_col < cur_dt,
                    and_(ts_col == cur_dt, id_col < cur_id),
                )
            )
        else:
            # (timestamp, id) > (cur_dt, cur_id)
            query = query.where(
                or_(
                    ts_col > cur_dt,
                    and_(ts_col == cur_dt, id_col > cur_id),
                )
            )

    if descending:
        query = query.order_by(desc(ts_col), desc(id_col))
    else:
        query = query.order_by(asc(ts_col), asc(id_col))

    # Fetch limit + 1 items
    query = query.limit(limit + 1)
    return query, decoded


def process_keyset_results(
    items: List[T],
    limit: int,
    timestamp_col_name: str = "created_at",
    id_col_name: str = "id",
) -> Tuple[List[T], Optional[str], bool]:
    """
    Splits the limit + 1 result set into current page items, next_cursor, and has_more boolean.
    """
    if len(items) > limit:
        has_more = True
        page_items = items[:limit]
        last_item = page_items[-1]
        dt = getattr(last_item, timestamp_col_name)
        item_id = getattr(last_item, id_col_name)
        next_cursor = encode_cursor(dt, str(item_id))
    else:
        has_more = False
        page_items = items
        next_cursor = None

    return page_items, next_cursor, has_more
