import asyncio
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any
import httpx
import redis.asyncio as aioredis

from backend.app.config import settings
from backend.app.domain.models import Transfer, TransferPage
from backend.app.adapters.base import (
    BlockchainProvider,
    BlockchainProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    InvalidAddressError,
)

logger = logging.getLogger("crypto_tracer.adapters.tron")


def validate_tron_address(address: str) -> bool:
    """
    Validate basic TRON address format (Base58Check starts with 'T', 34 chars).
    """
    if not address or not isinstance(address, str):
        return False
    clean = address.strip()
    return len(clean) == 34 and clean.startswith("T")


class TronProvider(BlockchainProvider):
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        redis_client: Optional[aioredis.Redis] = None,
        cache_ttl: Optional[int] = None,
        timeout_seconds: float = 10.0,
        max_retries: int = 3,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        self.base_url = (base_url or settings.TRON_API_BASE_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.TRON_API_KEY
        self.redis_client = redis_client
        self.cache_ttl = cache_ttl or settings.BLOCKCHAIN_CACHE_TTL_SECONDS
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._external_client = http_client

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "CryptoTracer-Forensics/1.0",
        }
        if self.api_key:
            headers["TRON-PRO-API-KEY"] = self.api_key
        return headers

    def _build_cache_key(
        self,
        address: str,
        asset_contract: str,
        cursor: Optional[str],
        limit: int,
        direction: Optional[str],
    ) -> str:
        c_part = cursor or "head"
        d_part = direction or "all"
        return f"tron:trc20:{address}:{asset_contract}:{d_part}:{limit}:{c_part}"

    def normalize_transfer(self, item: Dict[str, Any], default_contract: str) -> Optional[Transfer]:
        """
        Transform a raw TronGrid TRC-20 item into our internal domain Transfer model.
        Isolates provider-specific fields.
        """
        try:
            tx_hash = item.get("transaction_id")
            if not tx_hash:
                return None

            token_info = item.get("token_info", {})
            decimals = int(token_info.get("decimals", 6))
            contract_addr = token_info.get("address", default_contract)
            symbol = token_info.get("symbol", "USDT")

            value_str = str(item.get("value", "0"))
            amount_raw = int(value_str)
            amount_decimal = Decimal(amount_raw) / Decimal(10 ** decimals)

            block_timestamp = item.get("block_timestamp", 0)
            timestamp = datetime.fromtimestamp(block_timestamp / 1000.0, tz=timezone.utc)

            from_addr = item.get("from", "")
            to_addr = item.get("to", "")

            block_raw = item.get("block_number") if item.get("block_number") is not None else item.get("block")
            block_number = int(block_raw) if block_raw is not None and str(block_raw).strip().isdigit() else None

            return Transfer(
                chain="TRON",
                tx_hash=tx_hash,
                block_number=block_number,
                timestamp=timestamp,
                from_address=from_addr,
                to_address=to_addr,
                asset_contract=contract_addr,
                asset_symbol=symbol,
                amount_raw=amount_raw,
                amount_decimal=amount_decimal,
                source="trongrid",
                raw=item,
            )
        except Exception as ex:
            logger.warning(f"Failed to normalize TronGrid item: {ex}, payload: {item}")
            return None

    async def get_transfers(
        self,
        address: str,
        asset_contract: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 20,
        direction: Optional[str] = None,
    ) -> TransferPage:
        address = address.strip()
        if not validate_tron_address(address):
            raise InvalidAddressError(f"Invalid TRON address format: '{address}'")

        target_contract = asset_contract or settings.TRON_USDT_CONTRACT
        clamped_limit = min(max(limit, 1), 200)

        # 1. Check Redis Cache
        cache_key = self._build_cache_key(address, target_contract, cursor, clamped_limit, direction)
        if self.redis_client:
            try:
                cached_data = await self.redis_client.get(cache_key)
                if cached_data:
                    logger.debug(f"Redis cache hit for {cache_key}")
                    page_dict = json.loads(cached_data)
                    page_dict["cached"] = True
                    return TransferPage(**page_dict)
            except Exception as e:
                logger.warning(f"Redis cache read error: {e}")

        # 2. Build Query Parameters
        params: Dict[str, Any] = {
            "limit": clamped_limit,
            "contract_address": target_contract,
        }
        if cursor:
            params["fingerprint"] = cursor
        if direction in ("outgoing", "only_from"):
            params["only_from"] = "true"
        elif direction in ("incoming", "only_to"):
            params["only_to"] = "true"

        url = f"{self.base_url}/v1/accounts/{address}/transactions/trc20"
        headers = self._get_headers()

        # 3. HTTP Request with Bounded Retries & Backoff
        attempt = 0
        backoff = 0.5
        raw_response: Optional[Dict[str, Any]] = None

        async def _do_fetch(client: httpx.AsyncClient):
            return await client.get(url, params=params, headers=headers, timeout=self.timeout_seconds)

        while attempt < self.max_retries:
            attempt += 1
            try:
                if self._external_client:
                    response = await _do_fetch(self._external_client)
                else:
                    async with httpx.AsyncClient() as client:
                        response = await _do_fetch(client)

                if response.status_code == 200:
                    raw_response = response.json()
                    break
                elif response.status_code == 429:
                    logger.warning(f"TronGrid HTTP 429 Rate Limited (attempt {attempt}/{self.max_retries})")
                    if attempt >= self.max_retries:
                        raise ProviderRateLimitError("TronGrid rate limit reached after retries.")
                    await asyncio.sleep(backoff)
                    backoff *= 2
                elif response.status_code >= 500:
                    logger.warning(f"TronGrid HTTP {response.status_code} server error (attempt {attempt}/{self.max_retries})")
                    if attempt >= self.max_retries:
                        raise BlockchainProviderError(f"TronGrid server returned status {response.status_code}")
                    await asyncio.sleep(backoff)
                    backoff *= 2
                else:
                    raise BlockchainProviderError(
                        f"TronGrid request failed with HTTP {response.status_code}: {response.text[:200]}"
                    )
            except httpx.TimeoutException as tex:
                logger.warning(f"TronGrid timeout on attempt {attempt}/{self.max_retries}: {tex}")
                if attempt >= self.max_retries:
                    raise ProviderTimeoutError(f"TronGrid connection timed out after {self.max_retries} attempts.")
                await asyncio.sleep(backoff)
                backoff *= 2
            except httpx.RequestError as rex:
                logger.warning(f"TronGrid network error on attempt {attempt}/{self.max_retries}: {rex}")
                if attempt >= self.max_retries:
                    raise BlockchainProviderError(f"TronGrid network request failed: {rex}")
                await asyncio.sleep(backoff)
                backoff *= 2

        if raw_response is None:
            raise BlockchainProviderError("No response received from TronGrid.")

        # 4. Normalize and Deduplicate Transfers
        data_items = raw_response.get("data", [])
        seen_keys = set()
        normalized_transfers: List[Transfer] = []

        for item in data_items:
            tx = self.normalize_transfer(item, target_contract)
            if not tx:
                continue

            # Deduplication key: combination of tx_hash, from, to, amount
            dedup_key = (tx.tx_hash, tx.from_address, tx.to_address, tx.amount_raw)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)
            normalized_transfers.append(tx)

        # 5. Extract Pagination Meta
        meta = raw_response.get("meta", {})
        next_fingerprint = meta.get("fingerprint")
        has_more = bool(next_fingerprint)

        result_page = TransferPage(
            transfers=normalized_transfers,
            next_cursor=next_fingerprint if has_more else None,
            has_more=has_more,
            cached=False,
            total_fetched=len(normalized_transfers),
        )

        # 6. Store in Redis Cache
        if self.redis_client and self.cache_ttl > 0:
            try:
                # Use model_dump_json to serialize
                await self.redis_client.setex(
                    cache_key,
                    self.cache_ttl,
                    result_page.model_dump_json()
                )
            except Exception as e:
                logger.warning(f"Failed to cache TronGrid transfers to Redis: {e}")

        return result_page
