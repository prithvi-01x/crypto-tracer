from fastapi import APIRouter, Depends
from backend.app.core.auth import OfficerSession
from backend.app.api.deps import get_current_officer

router = APIRouter(tags=["Auth"])


@router.get("/auth/me", response_model=OfficerSession)
async def get_current_officer_endpoint(
    current_officer: OfficerSession = Depends(get_current_officer),
) -> OfficerSession:
    """
    Returns the active investigator profile and tenant context.
    Decodes OIDC/JWT RS256/HS256 tokens or falls back to development mock session.
    """
    return current_officer
