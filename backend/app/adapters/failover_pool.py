import time
import random
import asyncio
import logging
from typing import List, Optional, Dict, Any
import httpx

from backend.app.core.circuit_breaker import CircuitBreaker, CircuitState
from backend.app.adapters.base import (
    BlockchainProviderError,
    ProviderTimeoutError,
    ProviderRateLimitError,
    InvalidAddressError,
    CircuitBreakerOpenError,
    NodeExhaustionError,
)

logger = logging.getLogger("crypto_tracer.adapters.failover_pool")


class RpcNode:
    """Represents a single blockchain RPC/API endpoint node with health telemetry."""

    def __init__(
        self,
        url: str,
        priority: int = 0,
        weight: int = 1,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ):
        self.url = url.rstrip("/")
        self.priority = priority
        self.weight = weight
        self.circuit_breaker = circuit_breaker or CircuitBreaker(name=self.url)
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.latency_samples: List[float] = []

    @property
    def avg_latency_ms(self) -> float:
        if not self.latency_samples:
            return 0.0
        return sum(self.latency_samples) / len(self.latency_samples)

    def record_latency(self, latency_ms: float):
        self.latency_samples.append(latency_ms)
        if len(self.latency_samples) > 50:
            self.latency_samples.pop(0)

    @property
    def is_available(self) -> bool:
        return self.circuit_breaker.allow_request()

    def get_health(self) -> Dict[str, Any]:
        state = self.circuit_breaker.state
        status_str = "HEALTHY" if state == CircuitState.CLOSED else (
            "DEGRADED" if state == CircuitState.HALF_OPEN else "UNHEALTHY"
        )
        return {
            "url": self.url,
            "priority": self.priority,
            "status": status_str,
            "circuit_state": state.value,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "total_requests": self.total_requests,
            "failed_requests": self.failed_requests,
        }


class RpcFailoverPool:
    """
    Multi-Node RPC Failover Pool with automatic health checking and priority routing.
    Distributes queries across primary and fallback nodes with circuit breaker protection.
    """

    def __init__(
        self,
        primary_url: str,
        fallback_urls: Optional[List[str]] = None,
        timeout_seconds: float = 10.0,
        max_retries_per_node: int = 3,
    ):
        self.timeout_seconds = timeout_seconds
        self.max_retries_per_node = max_retries_per_node
        self.nodes: List[RpcNode] = []

        seen = set()
        clean_primary = (primary_url or "").rstrip("/")
        if clean_primary:
            self.nodes.append(RpcNode(url=clean_primary, priority=0))
            seen.add(clean_primary)

        if fallback_urls:
            for idx, fb in enumerate(fallback_urls):
                clean_fb = fb.rstrip("/") if fb else ""
                if clean_fb and clean_fb not in seen:
                    self.nodes.append(RpcNode(url=clean_fb, priority=idx + 1))
                    seen.add(clean_fb)

    def get_candidates(self) -> List[RpcNode]:
        """Get sorted list of available nodes based on priority and latency."""
        available = [n for n in self.nodes if n.is_available]
        available.sort(key=lambda n: (n.priority, n.avg_latency_ms))
        return available

    async def execute_request(
        self,
        path: str,
        params: Dict[str, Any],
        headers: Dict[str, str],
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> Dict[str, Any]:
        candidates = self.get_candidates()
        if not candidates:
            if not self.nodes:
                raise NodeExhaustionError("No RPC nodes configured in failover pool.")
            shortest_cooldown_node = min(self.nodes, key=lambda n: n.circuit_breaker.get_remaining_cooldown())
            remaining = shortest_cooldown_node.circuit_breaker.get_remaining_cooldown()
            raise CircuitBreakerOpenError(
                endpoint=shortest_cooldown_node.url,
                retry_after=remaining,
                message=f"All RPC nodes in failover pool are circuit-broken. Earliest recovery in {remaining:.1f}s."
            )

        last_exception: Optional[Exception] = None

        for node_idx, node in enumerate(candidates):
            url = f"{node.url}{path}"
            attempt = 0
            backoff = 0.5

            while attempt < self.max_retries_per_node:
                attempt += 1
                node.total_requests += 1
                start_time = time.perf_counter()

                try:
                    if http_client:
                        resp = await http_client.get(url, params=params, headers=headers, timeout=self.timeout_seconds)
                    else:
                        async with httpx.AsyncClient() as client:
                            resp = await client.get(url, params=params, headers=headers, timeout=self.timeout_seconds)

                    latency_ms = (time.perf_counter() - start_time) * 1000
                    node.record_latency(latency_ms)

                    if resp.status_code == 200:
                        try:
                            parsed = resp.json()
                        except Exception as jerr:
                            logger.warning(f"Malformed JSON from {node.url}: {jerr}")
                            last_exception = BlockchainProviderError(f"Malformed JSON response from TronGrid: {jerr}")
                            await node.circuit_breaker.record_failure(last_exception)
                            node.failed_requests += 1
                            break

                        if not isinstance(parsed, dict):
                            last_exception = BlockchainProviderError("Malformed TronGrid response: expected JSON object")
                            await node.circuit_breaker.record_failure(last_exception)
                            node.failed_requests += 1
                            break

                        if parsed.get("success") is False:
                            err_msg = parsed.get("error", "Unspecified provider error")
                            logger.warning(f"TronGrid reported failure on {node.url}: {err_msg}")
                            last_exception = BlockchainProviderError(f"TronGrid error: {err_msg}")
                            await node.circuit_breaker.record_failure(last_exception)
                            node.failed_requests += 1
                            break

                        await node.circuit_breaker.record_success()
                        node.successful_requests += 1
                        return parsed

                    elif resp.status_code == 400:
                        err_text = resp.text[:250]
                        try:
                            err_json = resp.json()
                            if isinstance(err_json, dict) and "error" in err_json:
                                err_text = str(err_json["error"])
                        except Exception:
                            pass
                        raise InvalidAddressError(f"TronGrid rejected address: {err_text}")

                    elif resp.status_code == 429:
                        last_exception = ProviderRateLimitError(f"TronGrid rate limit reached on {node.url}.")
                        node.failed_requests += 1
                        if attempt < self.max_retries_per_node:
                            retry_after = resp.headers.get("Retry-After")
                            wait_time = float(retry_after) if retry_after and retry_after.replace(".", "", 1).isdigit() else backoff
                            jitter = random.uniform(0.1, 0.4)
                            await asyncio.sleep(wait_time + jitter)
                            backoff *= 2
                        else:
                            await node.circuit_breaker.record_failure(last_exception)
                            break

                    elif resp.status_code >= 500:
                        last_exception = BlockchainProviderError(
                            f"TronGrid server returned status {resp.status_code} on {node.url}"
                        )
                        node.failed_requests += 1
                        if attempt < self.max_retries_per_node:
                            jitter = random.uniform(0.1, 0.4)
                            await asyncio.sleep(backoff + jitter)
                            backoff *= 2
                        else:
                            await node.circuit_breaker.record_failure(last_exception)
                            break

                    else:
                        raise BlockchainProviderError(
                            f"TronGrid request failed with HTTP {resp.status_code}: {resp.text[:200]}"
                        )

                except InvalidAddressError:
                    raise
                except httpx.TimeoutException as tex:
                    node.failed_requests += 1
                    last_exception = ProviderTimeoutError(
                        f"TronGrid connection to {node.url} timed out after {self.max_retries_per_node} attempts."
                    )
                    if attempt < self.max_retries_per_node:
                        jitter = random.uniform(0.1, 0.4)
                        await asyncio.sleep(backoff + jitter)
                        backoff *= 2
                    else:
                        await node.circuit_breaker.record_failure(tex)
                        break
                except httpx.RequestError as rex:
                    node.failed_requests += 1
                    last_exception = BlockchainProviderError(f"TronGrid network request failed on {node.url}: {rex}")
                    if attempt < self.max_retries_per_node:
                        jitter = random.uniform(0.1, 0.4)
                        await asyncio.sleep(backoff + jitter)
                        backoff *= 2
                    else:
                        await node.circuit_breaker.record_failure(rex)
                        break

            if node_idx < len(candidates) - 1:
                logger.warning(
                    f"Node {node.url} exhausted attempts; failing over to {candidates[node_idx + 1].url}"
                )

        if last_exception:
            raise last_exception
        raise NodeExhaustionError("No response received from any configured TRON provider endpoint.")
