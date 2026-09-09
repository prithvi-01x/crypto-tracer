from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["Auth"])


class OfficerSession(BaseModel):
    officer_id: str
    name: str
    badge_number: str
    unit: str
    role: str
    is_authenticated: bool


@router.get("/auth/me", response_model=OfficerSession)
async def get_current_officer():
    """
    Mocked authentication endpoint for SIH prototype.
    Returns the active investigator profile without external SSO dependency.
    """
    return OfficerSession(
        officer_id="OFFICER-DL-812",
        name="Inspector P. Sharma",
        badge_number="CYBER-DELHI-4029",
        unit="District Cyber Crime Cell, IFSO Unit",
        role="INVESTIGATING_OFFICER",
        is_authenticated=True,
    )
