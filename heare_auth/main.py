"""FastAPI server for API key verification."""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import structlog
from fastapi import FastAPI, HTTPException, Request

from .models import HealthResponse, RefreshResponse, VerifyRequest, VerifyResponse
from .storage import KeyStore

# Configure structlog for JSON output
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=False,
)

logger = structlog.get_logger()

# Initialize key store
store = KeyStore(
    bucket=os.getenv("S3_BUCKET", ""),
    key=os.getenv("S3_KEY", "keys.json"),
    region=os.getenv("S3_REGION", "us-east-1"),
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown."""
    # Startup
    try:
        count = store.load_from_s3()
        logger.info("startup", keys_loaded=count)
    except Exception as e:
        logger.error("startup_failed", error=str(e))
        raise

    yield

    # Shutdown (nothing to do for now)


# Initialize FastAPI app
app = FastAPI(
    title="Heare Auth",
    description="Simple API key validation service",
    version="0.1.0",
    lifespan=lifespan,
)


@app.post("/verify", response_model=VerifyResponse)
async def verify(request: VerifyRequest, http_request: Request):
    """
    Verify an API key.

    Args:
        request: The verification request containing the API key
        http_request: The HTTP request object

    Returns:
        Verification response with key metadata if valid

    Raises:
        HTTPException: 403 if the API key is invalid
        HTTPException: 400 if the request is malformed
    """
    user_agent = http_request.headers.get("user-agent", "unknown")

    # Look up by secret
    key_data = store.get_by_secret(request.api_key)

    if key_data is None:
        logger.warning(
            "verification_failed",
            secret_prefix=request.api_key[:4] if len(request.api_key) >= 4 else "***",
            user_agent=user_agent,
        )
        raise HTTPException(status_code=403, detail={"valid": False, "error": "Invalid API key"})

    # Log successful verification with key_id (NOT secret)
    logger.info(
        "verification_success",
        key_id=key_data["id"],
        key_name=key_data["name"],
        user_agent=user_agent,
    )

    return VerifyResponse(
        valid=True,
        key_id=key_data["id"],
        name=key_data["name"],
        metadata=key_data.get("metadata", {}),
    )


@app.post("/refresh", response_model=RefreshResponse)
async def refresh(request: Request):
    """
    Refresh keys from S3. Only accessible from localhost.

    Args:
        request: The HTTP request object

    Returns:
        Refresh response with number of keys loaded

    Raises:
        HTTPException: 403 if not accessed from localhost
    """
    # Check if request is from localhost
    client_host = request.client.host if request.client else None
    forwarded_for = request.headers.get("x-forwarded-for", "").split(",")[0].strip()

    if client_host not in ("127.0.0.1", "localhost", None) and forwarded_for not in (
        "127.0.0.1",
        "localhost",
        "",
    ):
        logger.warning("refresh_rejected", client_host=client_host, forwarded_for=forwarded_for)
        raise HTTPException(
            status_code=403, detail={"error": "Refresh endpoint only accessible from localhost"}
        )

    try:
        count = store.load_from_s3()
        logger.info("refresh_success", keys_loaded=count)

        return RefreshResponse(
            success=True,
            keys_loaded=count,
            timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )
    except Exception as e:
        logger.error("refresh_failed", error=str(e))
        raise HTTPException(status_code=500, detail={"error": f"Failed to refresh keys: {str(e)}"})


@app.get("/health", response_model=HealthResponse)
async def health():
    """
    Health check endpoint.

    Returns:
        Health response with current status and key count
    """
    return HealthResponse(status="ok", keys_count=len(store.keys_by_secret))
