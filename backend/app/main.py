from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.config import get_settings
from backend.app.db import ping_falkordb
from backend.app.routers.admin import router as admin_router
from backend.app.routers.change_requests import router as cr_router
from backend.app.routers.chat import router as chat_router
from backend.app.routers.entities import router as entities_router
from backend.app.routers.facts import router as facts_router

app = FastAPI(
    title="TruthBranch API",
    description="Git for Company Knowledge — Branch, Diff, Review, and Merge",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin_router)
app.include_router(facts_router)
app.include_router(cr_router)
app.include_router(entities_router)
app.include_router(chat_router)


@app.get("/api/health")
def health():
    db_ok = ping_falkordb()
    settings = get_settings()
    return {
        "status": "ok" if db_ok else "degraded",
        "falkordb": "connected" if db_ok else "unreachable",
        "agent_mode": settings.agent_mode,
        "falkordb_host": settings.falkordb_host,
        "falkordb_port": settings.falkordb_port,
    }
