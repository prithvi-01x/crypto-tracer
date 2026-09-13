import abc
from typing import Optional, Dict, Any
from backend.app.domain.models import TransferPage, Transfer


class BlockchainProviderError(Exception):
    """Base exception for all blockchain provider failures."""
    pass


class ProviderTimeoutError(BlockchainProviderError):
    """Provider request timed out (connect or read timeout)."""
    pass


class ProviderRateLimitError(BlockchainProviderError):
    """Provider rate limit exhausted (HTTP 429)."""
    pass


class InvalidAddressError(BlockchainProviderError):
    """Supplied address does not conform to blockchain network format."""
    pass


class CircuitBreakerOpenError(BlockchainProviderError):
    """Circuit breaker is OPEN; request fast-failed to prevent cascade."""
    def __init__(self, endpoint: str, retry_after: float = 0.0, message: Optional[str] = None):
        self.endpoint = endpoint
        self.retry_after = retry_after
        msg = message or f"Circuit breaker is OPEN for endpoint '{endpoint}'. Retry after {retry_after:.1f}s."
        super().__init__(msg)


class NodeExhaustionError(BlockchainProviderError):
    """All RPC nodes in the failover pool are unavailable or circuit-broken."""
    pass


class TransactionExecutionError(BlockchainProviderError):
    """On-chain transaction execution failed or reverted."""
    pass


class BlockchainProvider(abc.ABC):
    """
    Abstract Base Class (ABC) defining the mandatory contract for blockchain ingestion.
    Isolates chain-specific RPC/API implementations from forensic domain services.
    """

    @property
    def chain_name(self) -> str:
        """Name of the blockchain network (e.g. 'TRON', 'ETHEREUM')."""
        return "TRON"

    @abc.abstractmethod
    async def get_transfers(
        self,
        address: str,
        asset_contract: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 20,
        direction: Optional[str] = None,
    ) -> TransferPage:
        """
        Retrieve a paginated set of normalized token transfers for the given address.

        :param address: Wallet address to inspect.
        :param asset_contract: Token contract address (e.g. TRC-20 USDT).
        :param cursor: Pagination cursor (e.g. TronGrid fingerprint).
        :param limit: Maximum number of transfers to return.
        :param direction: Transfer direction ('only_from', 'only_to', or None for both).
        :return: TransferPage with normalized Transfer items.
        """
        raise NotImplementedError

    def validate_address(self, address: str) -> bool:
        """Validate address format against chain rules. Default returns True."""
        return True

    def normalize_transfer(self, raw_item: Dict[str, Any], default_contract: str) -> Optional[Transfer]:
        """Transform raw provider transfer JSON into canonical Transfer model."""
        return None

    async def health_check(self) -> Dict[str, Any]:
        """Perform active health probe on provider. Default returns HEALTHY."""
        return {"status": "HEALTHY", "latency_ms": 0.0, "error": None}

    async def get_account_balance(self, address: str, asset_contract: Optional[str] = None) -> Dict[str, Any]:
        """Retrieve token or native balance for address."""
        return {"address": address, "balance": "0.00"}
