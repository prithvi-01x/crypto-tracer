import asyncio
import json
import logging
import random
import re
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
    CircuitBreakerOpenError,
    NodeExhaustionError,
    TransactionExecutionError,
)
from backend.app.adapters.cache import TwoTierBlockchainCache
from backend.app.adapters.failover_pool import RpcFailoverPool

logger = logging.getLogger("crypto_tracer.adapters.tron")

TRON_ADDRESS_REGEX = re.compile(r"^T[1-9A-HJ-NP-Za-km-z]{33}$")


def validate_tron_address(address: str) -> bool:
    """
    Validate TRON address format (Base58Check starts with 'T', 34 chars, Base58 alphabet).
    """
    if not address or not isinstance(address, str):
        return False
    clean = address.strip()
    return bool(TRON_ADDRESS_REGEX.match(clean))


class TronProvider(BlockchainProvider):
    def __init__(
        self,
        base_url: Optional[str] = None,
        fallback_urls: Optional[List[str]] = None,
        api_key: Optional[str] = None,
        redis_client: Optional[aioredis.Redis] = None,
        cache_ttl: Optional[int] = None,
        timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        primary_url = (base_url or settings.TRON_API_BASE_URL).rstrip("/")
        configured_fallbacks = fallback_urls if fallback_urls is not None else settings.TRON_FALLBACK_API_URLS
        all_candidates = [primary_url] + [u.rstrip("/") for u in configured_fallbacks if u and u.strip()]

        seen_endpoints = set()
        self.endpoints: List[str] = []
        for u in all_candidates:
            if u not in seen_endpoints:
                seen_endpoints.add(u)
                self.endpoints.append(u)

        self.base_url = self.endpoints[0]
        raw_key = api_key if api_key is not None else settings.TRON_API_KEY
        self.api_key = (
            raw_key.get_secret_value()
            if hasattr(raw_key, "get_secret_value")
            else (raw_key or "")
        )
        self.redis_client = redis_client
        self.cache_ttl = cache_ttl if cache_ttl is not None else settings.BLOCKCHAIN_CACHE_TTL_SECONDS
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else settings.TRON_HTTP_TIMEOUT_SECONDS
        self.max_retries = max_retries if max_retries is not None else settings.TRON_MAX_RETRIES
        self._external_client = http_client

        # Feature 29: Two-Tier Cache (L1 LRU + L2 Redis)
        self.cache = TwoTierBlockchainCache(
            redis_client=redis_client,
            default_ttl=self.cache_ttl,
            finalized_ttl=86400,
        )

        # Feature 28: Multi-Node RPC Failover Pool with Circuit Breakers
        self.failover_pool = RpcFailoverPool(
            primary_url=self.endpoints[0],
            fallback_urls=self.endpoints[1:] if len(self.endpoints) > 1 else None,
            timeout_seconds=self.timeout_seconds,
            max_retries_per_node=self.max_retries,
        )

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
        return self.cache.build_key(
            chain="tron",
            address=address,
            asset_contract=asset_contract,
            direction=direction,
            limit=limit,
            cursor=cursor,
        )

    def normalize_transfer(self, item: Dict[str, Any], default_contract: str) -> Optional[Transfer]:
        """
        Transform a raw TronGrid TRC-20 item into our internal domain Transfer model.
        Hardened against reverted transactions, non-Transfer events, and malformed inputs.
        """
        try:
            tx_hash = item.get("transaction_id")
            if not tx_hash:
                return None

            # 1. Hardening Check: Filter non-Transfer events (e.g. Approval)
            event_type = item.get("type", "Transfer")
            if event_type and str(event_type).strip().lower() != "transfer":
                logger.warning(f"Discarding non-transfer event {tx_hash}: type={event_type}")
                return None

            # 2. Hardening Check: Inspect transaction execution status (ret / contractRet)
            ret_list = item.get("ret")
            if isinstance(ret_list, list) and len(ret_list) > 0:
                ret_obj = ret_list[0]
                if isinstance(ret_obj, dict):
                    contract_ret = ret_obj.get("contractRet") or ret_obj.get("ret")
                    if contract_ret and str(contract_ret).upper() not in ("SUCCESS", "1"):
                        logger.warning(
                            f"Discarding reverted TRON transaction {tx_hash}: contractRet={contract_ret}"
                        )
                        return None

            # 3. Hardening Check: Inspect top-level status/result flags
            for flag in ("contract_ret", "contractRet", "finalResult", "result", "status"):
                val = item.get(flag)
                if val is not None and str(val).upper() in (
                    "REVERT", "FAILED", "OUT_OF_ENERGY", "OUT_OF_TIME", "FAILURE", "FAIL"
                ):
                    logger.warning(f"Discarding failed TRON transaction {tx_hash}: {flag}={val}")
                    return None

            token_info = item.get("token_info", {})
            decimals = int(token_info.get("decimals", 6))
            contract_addr = token_info.get("address", default_contract)
            symbol = token_info.get("symbol", "USDT")

            value_str = str(item.get("value", "0"))
            amount_raw = int(value_str)
            if amount_raw <= 0:
                return None

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

    def validate_address(self, address: str) -> bool:
        return validate_tron_address(address)

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

        # 1. Check Two-Tier Cache
        cache_key = self._build_cache_key(address, target_contract, cursor, clamped_limit, direction)
        cached_page = await self.cache.get(cache_key)
        if cached_page is not None:
            return cached_page

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

        headers = self._get_headers()

        # 3. HTTP Request via Multi-Node Failover Pool with Circuit Breaker
        path = f"/v1/accounts/{address}/transactions/trc20"
        raw_response = await self.failover_pool.execute_request(
            path=path,
            params=params,
            headers=headers,
            http_client=self._external_client,
        )

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

        # 6. Store in Two-Tier Cache (Finalized if pagination cursor is present)
        is_finalized = bool(next_fingerprint or cursor)
        await self.cache.set(
            key=cache_key,
            page=result_page,
            is_finalized=is_finalized,
        )

        return result_page

    async def health_check(self) -> Dict[str, Any]:
        node_healths = [n.get_health() for n in self.failover_pool.nodes]
        any_healthy = any(n["status"] == "HEALTHY" for n in node_healths)
        return {
            "status": "HEALTHY" if any_healthy else ("DEGRADED" if any(n["status"] == "DEGRADED" for n in node_healths) else "UNHEALTHY"),
            "nodes": node_healths,
            "primary": self.base_url,
        }
