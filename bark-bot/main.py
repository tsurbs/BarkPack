import uvicorn
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.surfaces.web import router as web_router
from app.surfaces.slack import router as slack_router
from app.api.tools import router as tools_router
from app.api.agents import router as agents_router
from app.api.dashboard import router as dashboard_router
from app.core.orchestrator import ensure_agents_initialized
from app.db.session import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle for the application."""
    # 1. Sync and load skills from S3
    try:
        logger.info("Syncing and loading skills from S3...")
        await ensure_agents_initialized()
        logger.info("Skills loaded successfully.")
    except Exception as e:
        logger.error(f"CRITICAL: Failed to initialize agents from S3: {e}")
        # We don't crash here so the healthcheck can still pass, 
        # but the bot might be degraded.
    
    # 2. Tool Registry Sync (Postgres)
    try:
        from app.tools.registry import ensure_tools_initialized
        logger.info("Syncing native tools to database...")
        await ensure_tools_initialized()
        logger.info("Tools synced successfully.")
    except Exception as e:
        logger.error(f"CRITICAL: Failed to sync native tools to database: {e}")
    
    yield
    
    # Shutdown: Close database connections
    logger.info("Closing database connections...")
    await engine.dispose()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="Bark Bot API", 
    description="Multi-modal agentic AI backend",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for standard web frontends to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include surface routers
app.include_router(web_router)
app.include_router(slack_router)
app.include_router(tools_router)
app.include_router(agents_router)
app.include_router(dashboard_router)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

