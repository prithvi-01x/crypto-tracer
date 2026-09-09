from typing import Optional, Dict, List, Any
from backend.app.domain.models import Transfer, TransferPage
from backend.app.adapters.base import BlockchainProvider


class FixtureProvider(BlockchainProvider):
    """
    Deterministic fixture provider for demo replay and test isolation.
    Serves predefined transfer records without making outbound network requests.
    """

    def __init__(self, fixtures: Optional[Dict[str, List[Dict[str, Any]]]] = None):
        self.fixtures = fixtures or {}

    def register_fixture(self, address: str, transfers: List[Transfer]):
        self.fixtures[address] = [t.model_dump() if hasattr(t, "model_dump") else t for t in transfers]

    async def get_transfers(
        self,
        address: str,
        asset_contract: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 20,
        direction: Optional[str] = None,
    ) -> TransferPage:
        raw_items = self.fixtures.get(address, [])
        transfers = [Transfer(**item) if isinstance(item, dict) else item for item in raw_items]

        # Apply simple in-memory pagination
        start_idx = int(cursor) if cursor and cursor.isdigit() else 0
        end_idx = start_idx + limit
        page_transfers = transfers[start_idx:end_idx]

        next_cursor = str(end_idx) if end_idx < len(transfers) else None
        has_more = next_cursor is not None

        return TransferPage(
            transfers=page_transfers,
            next_cursor=next_cursor,
            has_more=has_more,
            cached=True,
            total_fetched=len(page_transfers),
        )
