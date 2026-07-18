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
