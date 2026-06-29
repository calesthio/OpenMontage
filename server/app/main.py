"""FastAPI entrypoint for OpenMontage server (Agent execution sidecar)."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import jobs, events, health

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
