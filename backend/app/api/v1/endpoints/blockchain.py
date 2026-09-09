from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
import redis.asyncio as aioredis

from backend.app.persistence.redis import get_redis
from backend.app.adapters.tron_provider import TronProvider
from backend.app.domain.models import TransferPage
from backend.app.adapters.base import (
    InvalidAddressError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    BlockchainProviderError,
)

router = APIRouter(prefix="/blockchain/tron", tags=["Blockchain Ingestion"])


@router.get("/transfers/{address}", response_model=TransferPage)
async def get_tron_transfers(
    address: str,
    contract_address: Optional[str] = Query(None, description="TRC-20 token contract (defaults to USDT)"),
    cursor: Optional[str] = Query(None, description="Pagination cursor fingerprint"),
    limit: int = Query(20, ge=1, le=200, description="Maximum transfers to fetch per page"),
    direction: Optional[str] = Query(None, description="Filter direction: 'outgoing'/'only_from', 'incoming'/'only_to'"),
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    Ingest and normalize TRC-20 token transfers for a given TRON address.
    Demonstrates normalized response, deduplication, and Redis caching.
    """
    provider = TronProvider(redis_client=redis)
    try:
        page = await provider.get_transfers(
            address=address,
            asset_contract=contract_address,
            cursor=cursor,
            limit=limit,
            direction=direction,
        )
        return page
    except InvalidAddressError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ProviderRateLimitError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
    except ProviderTimeoutError as e:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(e))
    except BlockchainProviderError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
