"""Pipeline catalogue — lists the engine's runnable pipelines for the UI."""

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("")
async def list_pipelines_endpoint():
    """Every pipeline_defs/*.yaml the web platform can run, with UI metadata."""
    from app.pipeline_catalog import list_manifest_names, load_manifest

    out = []
    for name in list_manifest_names():
        try:
            m = load_manifest(name)
        except Exception:
            continue
        stages = m.get("stages", [])
        out.append({
            "name": name,
            "description": (m.get("description") or "").strip(),
            "category": m.get("category"),
            "stability": m.get("stability"),
            "stages": [s["name"] for s in stages],
            "approval_stages": [s["name"] for s in stages if s.get("human_approval_default")],
        })
    return {"pipelines": out}


@router.get("/{name}")
async def get_pipeline(name: str):
    from app.pipeline_catalog import load_manifest
    try:
        m = load_manifest(name)
    except FileNotFoundError:
        raise HTTPException(404, f"Pipeline '{name}' not found")
    except Exception as exc:
        raise HTTPException(400, f"Failed to load pipeline '{name}': {exc}")
    stages = m.get("stages", [])
    return {
        "name": name,
        "description": (m.get("description") or "").strip(),
        "category": m.get("category"),
        "stability": m.get("stability"),
        "stages": [
            {"name": s["name"], "approval": bool(s.get("human_approval_default", False))}
            for s in stages
        ],
    }
