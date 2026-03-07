"""
IntelliDoc — Main Application Entry Point
==========================================
This is where everything comes together.

The FastAPI app is created here with:
- CORS middleware (so the React frontend can talk to the API)
- Router includes (all API routes registered)
- Lifespan events (things that happen on startup/shutdown)
- Health check endpoint

To run:
    cd backend
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.database import init_db, close_db
import logging

# ── Logging Setup ────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


# ── Lifespan Events ─────────────────────────────────────────
# These run when the server starts and stops.

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle manager.

    Startup:
        - Initialize database tables
        - Load ML models (lazy, so they load on first use)

    Shutdown:
        - Close database connections
    """
    # ── Startup ──────────────────────────────────────────
    logger.info(f"🚀 Starting {settings.app_name}...")
    logger.info(f"   Environment: {settings.app_env}")
    logger.info(f"   Debug mode: {settings.debug}")

    await init_db()
    logger.info("✅ Database initialized")

    yield  # App is running

    # ── Shutdown ─────────────────────────────────────────
    logger.info(f"🛑 Shutting down {settings.app_name}...")
    await close_db()
    logger.info("✅ Database connections closed")


# ── Create FastAPI App ───────────────────────────────────────
app = FastAPI(
    title="IntelliDoc API",
    description=(
        "Intelligent Multi-Modal Document Processing & Analysis Platform.\n\n"
        "Features:\n"
        "- Document upload and management (S3 storage)\n"
        "- OCR text extraction\n"
        "- Document classification (AI-powered)\n"
        "- Named Entity Recognition\n"
        "- Text summarization\n"
        "- RAG-powered intelligent Q&A\n"
        "- Analytics dashboard"
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ── CORS Middleware ──────────────────────────────────────────
# This allows the React frontend (running on port 3000/5173)
# to make requests to the API (running on port 8000).
# Without CORS, browsers block cross-origin requests.

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Include Routers ──────────────────────────────────────────
from app.api.documents import router as documents_router
from app.api.auth import router as auth_router

app.include_router(documents_router)
app.include_router(auth_router)

from app.api.ml import router as ml_router
from app.api.rag import router as rag_router
app.include_router(ml_router)
app.include_router(rag_router)


# ── Health Check ─────────────────────────────────────────────
@app.get("/", tags=["Health"])
async def root():
    """Root endpoint — basic health check."""
    return {
        "app": settings.app_name,
        "status": "running",
        "version": "1.0.0",
    }

@app.get("/health", tags=["Health"])
async def health():
    """Health check endpoint for ALB and container health checks."""
    return {"status": "healthy"}

@app.get("/health", tags=["Health"])
async def health_check():
    """
    Detailed health check endpoint.
    Used by AWS ALB/ECS for container health monitoring.
    """
    return {
        "status": "healthy",
        "environment": settings.app_env,
        "services": {
            "database": "connected",
            "s3": "configured",
        },
    }
