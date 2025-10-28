"""Pydantic models for API requests and responses."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SecretType(str, Enum):
    """Enum for secret types."""

    SHARED_SECRET = "shared_secret"


class VerifyRequest(BaseModel):
    """Request model for the /verify endpoint."""

    api_key: str = Field(..., description="The API secret to verify")


class VerifyResponse(BaseModel):
    """Response model for the /verify endpoint."""

    valid: bool = Field(..., description="Whether the API key is valid")
    key_id: Optional[str] = Field(None, description="The key ID (if valid)")
    name: Optional[str] = Field(None, description="The key name (if valid)")
    metadata: dict = Field(default_factory=dict, description="Key metadata (if valid)")
    error: Optional[str] = Field(None, description="Error message (if invalid)")


class RefreshResponse(BaseModel):
    """Response model for the /refresh endpoint."""

    success: bool = Field(..., description="Whether the refresh was successful")
    keys_loaded: int = Field(..., description="Number of keys loaded from S3")
    timestamp: str = Field(..., description="Timestamp of the refresh operation")


class HealthResponse(BaseModel):
    """Response model for the /health endpoint."""

    status: str = Field(..., description="Health status")
    keys_count: int = Field(..., description="Number of keys currently loaded")
