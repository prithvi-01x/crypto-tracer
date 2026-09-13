import time
import json
import logging
from typing import Optional, Dict, Any, Tuple
from collections import OrderedDict
from backend.app.domain.models import TransferPage

logger = logging.getLogger("crypto_tracer.adapters.cache")


class InMemoryL1Cache:
    """
    High-performance LRU in-memory cache with per-item monotonic TTL expiration.
    Thread and coroutine safe within a single process.
    """

    def __init__(self, max_entries: int = 1000, default_ttl: float = 60.0):
        self.max_entries = max(1, max_entries)
        self.default_ttl = max(0.1, default_ttl)
        self._cache: OrderedDict[str, Tuple[TransferPage, float]] = OrderedDict()

    def get(self, key: str) -> Optional[TransferPage]:
        now = time.monotonic()
        if key in self._cache:
            page, expire_at = self._cache[key]
            if now <= expire_at:
                self._cache.move_to_end(key)
                return page.model_copy(deep=True)
            else:
                del self._cache[key]
        return None

    def set(self, key: str, page: TransferPage, ttl: Optional[float] = None) -> None:
        now = time.monotonic()
        effective_ttl = ttl if ttl is not None else self.default_ttl
        expire_at = now + effective_ttl

        if key in self._cache:
            del self._cache[key]
        elif len(self._cache) >= self.max_entries:
            self._cache.popitem(last=False)

        self._cache[key] = (page.model_copy(deep=True), expire_at)

    def clear(self):
        self._cache.clear()

    def __len__(self):
        return len(self._cache)


class TwoTierBlockchainCache:
    """
    Two-Tier Blockchain Cache combining L1 In-Memory LRU with L2 Distributed Redis.
    Distinguishes between volatile head data (short TTL) and finalized historical data (long TTL).
    """

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        default_ttl: int = 300,
        finalized_ttl: int = 86400,
        l1_max_entries: int = 1000,
        l1_ttl: float = 60.0,
    ):
        self.redis = redis_client
        self.default_ttl = default_ttl
        self.finalized_ttl = finalized_ttl
        self.l1 = InMemoryL1Cache(max_entries=l1_max_entries, default_ttl=l1_ttl)

    def build_key(
        self,
        chain: str,
        address: str,
        asset_contract: str,
        direction: Optional[str] = None,
        limit: int = 20,
        cursor: Optional[str] = None,
    ) -> str:
        c_part = cursor or "head"
        d_part = direction or "all"
        return f"{chain.lower()}:trc20:{address}:{asset_contract}:{d_part}:{limit}:{c_part}"

    async def get(self, key: str) -> Optional[TransferPage]:
        # 1. Check L1 in-memory
        l1_hit = self.l1.get(key)
        if l1_hit is not None:
            l1_hit.cached = True
            logger.debug(f"L1 In-Memory cache hit for {key}")
            return l1_hit

        # 2. Check L2 Redis
        if self.redis is not None:
            try:
                raw_data = await self.redis.get(key)
                if raw_data:
                    logger.debug(f"L2 Redis cache hit for {key}")
                    if isinstance(raw_data, bytes):
                        raw_data = raw_data.decode("utf-8")
                    page_dict = json.loads(raw_data)
                    page_dict["cached"] = True
                    page = TransferPage(**page_dict)
                    # Backfill into L1
                    self.l1.set(key, page)
                    return page
            except Exception as e:
                logger.warning(f"L2 Redis cache read error for key {key}: {e}")

        return None

    async def set(
        self,
        key: str,
        page: TransferPage,
        ttl: Optional[int] = None,
        is_finalized: bool = False,
    ) -> None:
        effective_ttl = ttl if ttl is not None else (self.finalized_ttl if is_finalized else self.default_ttl)

        # 1. Populate L1 (capped at 300s in local RAM to prevent stale worker state)
        try:
            self.l1.set(key, page, ttl=min(effective_ttl, 300))
        except Exception as e:
            logger.warning(f"L1 In-Memory cache write error: {e}")

        # 2. Populate L2 Redis
        if self.redis is not None and effective_ttl > 0:
            try:
                await self.redis.setex(
                    key,
                    int(effective_ttl),
                    page.model_dump_json()
                )
            except Exception as e:
                logger.warning(f"L2 Redis cache write error for key {key}: {e}")

    def clear_l1(self):
        self.l1.clear()
