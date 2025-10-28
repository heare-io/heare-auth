"""FastAPI server for API key verification."""

import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import structlog
from fastapi import FastAPI, HTTPException, Request

from .models import RefreshResponse, VerifyRequest, VerifyResponse
from .stats import get_stats_client
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
    storage_secret=os.getenv("STORAGE_SECRET"),
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown."""
    # Startup
    start_time = time.time()
    stats_client = get_stats_client()
    
    try:
        count = store.load_from_s3()
        logger.info("startup", keys_loaded=count)
        
        # Track startup metrics
        if stats_client:
            try:
                with stats_client.pipeline() as pipe:
                    pipe.incr('startup.success')
                    pipe.gauge('keys.count', count)
                    pipe.time('startup.duration', (time.time() - start_time) * 1000)
            except Exception:
                pass
    except Exception as e:
        logger.error("startup_failed", error=str(e))
        
        # Track startup failure
        if stats_client:
            try:
                with stats_client.pipeline() as pipe:
                    pipe.incr('startup.failed')
            except Exception:
                pass
        
        raise

    yield

    # Shutdown
    if stats_client:
        try:
            with stats_client.pipeline() as pipe:
                pipe.incr('shutdown')
        except Exception:
            pass


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
    start_time = time.time()
    user_agent = http_request.headers.get("user-agent", "unknown")
    
    # Get stats client
    stats_client = get_stats_client()

    # Look up by secret
    key_data = store.get_by_secret(request.api_key)

    if key_data is None:
        logger.warning(
            "verification_failed",
            secret_prefix=request.api_key[:4] if len(request.api_key) >= 4 else "***",
            user_agent=user_agent,
        )
        
        # Track failed verification
        if stats_client:
            try:
                with stats_client.pipeline() as pipe:
                    pipe.incr('verify.requests')
                    pipe.incr('verify.failed')
                    pipe.time('verify.duration', (time.time() - start_time) * 1000)
            except Exception:
                pass  # Don't let metrics failures affect the API
        
        raise HTTPException(status_code=403, detail={"valid": False, "error": "Invalid API key"})

    # Log successful verification with key_id (NOT secret)
    logger.info(
        "verification_success",
        key_id=key_data["id"],
        key_name=key_data["name"],
        user_agent=user_agent,
    )
    
    # Track successful verification
    if stats_client:
        try:
            with stats_client.pipeline() as pipe:
                pipe.incr('verify.requests')
                pipe.incr('verify.success')
                pipe.time('verify.duration', (time.time() - start_time) * 1000)
        except Exception:
            pass  # Don't let metrics failures affect the API

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
    start_time = time.time()
    stats_client = get_stats_client()
    
    # Check if request is from localhost
    client_host = request.client.host if request.client else None
    forwarded_for = request.headers.get("x-forwarded-for", "").split(",")[0].strip()

    if client_host not in ("127.0.0.1", "localhost", None) and forwarded_for not in (
        "127.0.0.1",
        "localhost",
        "",
    ):
        logger.warning("refresh_rejected", client_host=client_host, forwarded_for=forwarded_for)
        
        # Track rejected refresh
        if stats_client:
            try:
                with stats_client.pipeline() as pipe:
                    pipe.incr('refresh.requests')
                    pipe.incr('refresh.rejected')
            except Exception:
                pass
        
        raise HTTPException(
            status_code=403, detail={"error": "Refresh endpoint only accessible from localhost"}
        )

    try:
        count = store.load_from_s3()
        logger.info("refresh_success", keys_loaded=count)
        
        # Track successful refresh
        if stats_client:
            try:
                with stats_client.pipeline() as pipe:
                    pipe.incr('refresh.requests')
                    pipe.incr('refresh.success')
                    pipe.gauge('keys.count', count)
                    pipe.time('refresh.duration', (time.time() - start_time) * 1000)
            except Exception:
                pass

        return RefreshResponse(
            success=True,
            keys_loaded=count,
            timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )
    except Exception as e:
        logger.error("refresh_failed", error=str(e))
        
        # Track failed refresh
        if stats_client:
            try:
                with stats_client.pipeline() as pipe:
                    pipe.incr('refresh.requests')
                    pipe.incr('refresh.failed')
            except Exception:
                pass
        
        raise HTTPException(status_code=500, detail={"error": f"Failed to refresh keys: {str(e)}"})


@app.get("/health")
async def health():
    """
    Health check endpoint.

    Returns:
        Minimal health response without revealing service details
    """
    stats_client = get_stats_client()
    keys_count = len(store.keys_by_secret)
    
    # Track health check
    if stats_client:
        try:
            with stats_client.pipeline() as pipe:
                pipe.incr('health.requests')
                pipe.gauge('keys.count', keys_count)
        except Exception:
            pass
    
    # Return minimal response - just "ok" without revealing it's an auth service
    return {"status": "ok"}
