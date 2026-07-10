"""System capabilities: live view of the active evolution-seam backends."""

from fastapi import APIRouter

from app.interfaces import active_backends
from app.runner.stage_runner import LLM_MODEL

router = APIRouter()


@router.get("/capabilities")
async def capabilities():
    """Which storage/queue/auth adapter is live, plus the planned roadmap.

    Backs the settings page so it reports real state instead of static text.
    `llm_model` reflects MAAS_LLM_MODEL if set, so the settings page can't
    drift out of sync with the model actually driving the pipeline the way
    a hardcoded display string would.
    """
    return {"backends": active_backends(), "llm_model": LLM_MODEL}
