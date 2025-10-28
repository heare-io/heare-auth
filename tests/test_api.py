"""Tests for FastAPI endpoints."""

import pytest
from fastapi.testclient import TestClient

from heare_auth.main import app, store

client = TestClient(app)


@pytest.fixture
def setup_test_keys():
    """Setup test keys in the store."""
    store.keys_by_secret = {
        "sec_test123": {
            "id": "key_test456",
            "secret": "sec_test123",
            "name": "Test Key",
            "metadata": {"env": "test"},
        }
    }
    store.keys_by_id = {
        "key_test456": {
            "id": "key_test456",
            "secret": "sec_test123",
            "name": "Test Key",
            "metadata": {"env": "test"},
        }
    }
    yield
    # Cleanup
    store.keys_by_secret = {}
    store.keys_by_id = {}


def test_verify_valid_key(setup_test_keys):
    """Test verifying a valid API key."""
    response = client.post(
        "/verify", json={"api_key": "sec_test123"}, headers={"User-Agent": "TestClient/1.0"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["key_id"] == "key_test456"
    assert data["name"] == "Test Key"
    assert data["metadata"] == {"env": "test"}


def test_verify_invalid_key():
    """Test verifying an invalid API key."""
    store.keys_by_secret = {}

    response = client.post("/verify", json={"api_key": "invalid_secret"})

    assert response.status_code == 403


def test_verify_missing_api_key():
    """Test verify endpoint with missing api_key field."""
    response = client.post("/verify", json={})
    assert response.status_code == 422  # Validation error


def test_health_endpoint(setup_test_keys):
    """Test the health check endpoint."""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["keys_count"] == 1


def test_refresh_endpoint():
    """Test the refresh endpoint."""
    # Mock the load_from_s3 method
    original_load = store.load_from_s3
    store.load_from_s3 = lambda: 5

    try:
        response = client.post("/refresh")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["keys_loaded"] == 5
        assert "timestamp" in data
    finally:
        store.load_from_s3 = original_load
