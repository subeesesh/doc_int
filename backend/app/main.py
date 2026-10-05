"""Main FastAPI application."""
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.api.router import api_router
from app.config.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Prometheus metrics (optional)
try:
    from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
    REQUEST_COUNT = Counter("http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"])
    REQUEST_LATENCY = Histogram("http_request_duration_seconds", "HTTP request latency")
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Enterprise Document Intelligence Platform")
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="Enterprise Document Intelligence",
    description="Document processing, search, and RAG platform",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time"] = f"{duration:.3f}s"

    if METRICS_AVAILABLE:
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code,
        ).inc()
        REQUEST_LATENCY.observe(duration)

    return response


# API routes
app.include_router(api_router)


# Metrics endpoint
if METRICS_AVAILABLE:
    from starlette.responses import Response

    @app.get("/metrics", include_in_schema=False)
    async def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# Serve frontend
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir / "static")), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_frontend():
        return FileResponse(str(frontend_dir / "index.html"))