from typing import Protocol, Optional, runtime_checkable
from backend.app.domain.models import TransferPage, Transfer


class BlockchainProviderError(Exception):
    """Base exception for blockchain provider failures."""
    pass


class ProviderTimeoutError(BlockchainProviderError):
    """Provider timed out during request execution."""
    pass


class ProviderRateLimitError(BlockchainProviderError):
    """Provider returned 429 Too Many Requests."""
    pass


class InvalidAddressError(BlockchainProviderError):
    """Supplied address does not conform to blockchain format."""
    pass


@runtime_checkable
class BlockchainProvider(Protocol):
    """
    Unified abstract contract for blockchain ingestion providers.
    Isolates chain-specific API/RPC responses from the domain and tracing layers.
    """

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
        ...
