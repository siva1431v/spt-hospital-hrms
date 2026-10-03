"""
SPT Hospital HRMS — Main FastAPI Application
"""
import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.core.config import settings

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL, logging.INFO))
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Create upload directories on startup
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "pdfs"), exist_ok=True)
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "salary_slips"), exist_ok=True)
    logger.info(f"SPT Hospital HRMS starting — uploads dir: {settings.UPLOAD_DIR}")
    yield
    logger.info("SPT Hospital HRMS shutting down")


app = FastAPI(
    title="SPT Hospital HRMS API",
    description="""
    ## SPT Hospital Human Resource Management System

    Complete attendance management, payroll processing, and HR reporting system
    built for SPT Hospital. Designed to process eSSL attendance PDFs and automate
    payroll generation.

    ### Features
    - PDF attendance import (eSSL format)
    - Employee & department management
    - Configurable shift management
    - Leave management
    - Salary calculation engine
    - Payroll finalization
    - Salary slip generation
    - Comprehensive reports
    """,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)




from starlette.exceptions import HTTPException as StarletteHTTPException

# ── Health Check ───────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint for load balancers and monitoring."""
    from app.services.storage import storage_service
    storage_info = await storage_service.health_check()
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "storage": storage_info,
    }


# ── Include Routers ────────────────────────────────────────────────────────────
from app.api.v1.router import api_router
app.include_router(api_router, prefix="/api/v1")


# ── Exception Handlers ─────────────────────────────────────────────────────────
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return friendly validation error messages."""
    errors = []
    for error in exc.errors():
        field = " → ".join(str(loc) for loc in error["loc"] if loc != "body")
        errors.append({"field": field, "message": error["msg"]})
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation error",
            "errors": errors,
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected error occurred. Please contact the system administrator."
        },
    )

# ── CORS Middleware ────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=None if settings.is_production else (settings.CORS_ORIGIN_REGEX or None),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
