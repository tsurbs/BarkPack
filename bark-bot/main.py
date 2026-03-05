import uvicorn
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.surfaces.web import router as web_router
from app.surfaces.slack import router as slack_router
from app.core.orchestrator import ensure_agents_initialized

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle for the application."""
    logger.info("Syncing and loading skills from S3...")
    await ensure_agents_initialized()
    logger.info("Skills loaded successfully.")
    yield


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

@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

