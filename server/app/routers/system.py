"""System capabilities: live view of the active evolution-seam backends."""

from fastapi import APIRouter

from app.interfaces import active_backends

router = APIRouter()


@router.get("/capabilities")
async def capabilities():
    """Which storage/queue/auth adapter is live, plus the planned roadmap.

    Backs the settings page so it reports real state instead of static text.
    """
    return {"backends": active_backends()}
