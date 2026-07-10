"""FastAPI entrypoint for OpenMontage server (Agent execution sidecar)."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routers import jobs, events, health, brands, system, pipelines

OM_ROOT = Path(__file__).parent.parent.parent

app = FastAPI(title="OpenMontage Server", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(jobs.router, prefix="/jobs")
app.include_router(events.router, prefix="/jobs")
app.include_router(brands.router, prefix="/brands")
app.include_router(system.router, prefix="/system")
app.include_router(pipelines.router, prefix="/pipelines")

# Serve generated project files (videos, images, audio) at /media/
projects_dir = OM_ROOT / "projects"
projects_dir.mkdir(exist_ok=True)
app.mount("/media", StaticFiles(directory=str(projects_dir)), name="media")

# Serve brand kit assets (currently just reference images) at /brand-media/ —
# kept separate from /media rather than folded into projects/, since brand
# kits are reused across many jobs and aren't per-run output. This mount is
# for the web UI to preview what was uploaded; the agent itself never fetches
# this URL (stage_runner.py embeds the file's bytes as a base64 data URI in
# the prompt instead, since MAAS_API_BASE is a remote gateway that can't
# reach back into this box's localhost to fetch it).
brand_kits_dir = OM_ROOT / "brand_kits"
brand_kits_dir.mkdir(exist_ok=True)
app.mount("/brand-media", StaticFiles(directory=str(brand_kits_dir)), name="brand_media")
