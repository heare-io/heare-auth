"""Tests for storage module."""

from heare_auth.storage import KeyStore


def test_keystore_initialization():
    """Test KeyStore initialization."""
    store = KeyStore("test-bucket", "keys.json", "us-east-1")
    assert store.bucket == "test-bucket"
    assert store.key == "keys.json"
    assert store.keys_by_secret == {}
    assert store.keys_by_id == {}


def test_get_by_secret():
    """Test getting key by secret."""
    store = KeyStore("test-bucket", "keys.json")
    store.keys_by_secret = {
        "sec_test123": {
            "id": "key_test456",
            "secret": "sec_test123",
            "name": "Test Key",
            "metadata": {"env": "test"},
        }
    }

    key = store.get_by_secret("sec_test123")
    assert key is not None
    assert key["id"] == "key_test456"
    assert key["name"] == "Test Key"

    # Test non-existent key
    assert store.get_by_secret("invalid") is None


def test_get_by_id():
    """Test getting key by ID."""
    store = KeyStore("test-bucket", "keys.json")
    store.keys_by_id = {
        "key_test456": {
            "id": "key_test456",
            "secret": "sec_test123",
            "name": "Test Key",
            "metadata": {},
        }
    }

    key = store.get_by_id("key_test456")
    assert key is not None
    assert key["secret"] == "sec_test123"

    # Test non-existent key
    assert store.get_by_id("invalid") is None


def test_get_all_keys():
    """Test getting all keys."""
    store = KeyStore("test-bucket", "keys.json")
    store.keys_by_id = {
        "key_1": {"id": "key_1", "name": "Key 1"},
        "key_2": {"id": "key_2", "name": "Key 2"},
    }

    keys = store.get_all_keys()
    assert len(keys) == 2
    assert any(k["id"] == "key_1" for k in keys)
    assert any(k["id"] == "key_2" for k in keys)
