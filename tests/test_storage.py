"""Tests for storage module."""

from datetime import datetime, timedelta, timezone

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


def test_get_by_secret_expired():
    """Test that expired keys are not returned."""
    store = KeyStore("test-bucket", "keys.json")
    
    # Create an expired key
    expired_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    store.keys_by_secret = {
        "sec_expired": {
            "id": "key_expired",
            "secret": "sec_expired",
            "name": "Expired Key",
            "expires_at": expired_time,
        }
    }
    
    # Should return None for expired key
    key = store.get_by_secret("sec_expired")
    assert key is None


def test_get_by_secret_not_expired():
    """Test that non-expired keys are returned."""
    store = KeyStore("test-bucket", "keys.json")
    
    # Create a future expiry key
    future_time = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    store.keys_by_secret = {
        "sec_valid": {
            "id": "key_valid",
            "secret": "sec_valid",
            "name": "Valid Key",
            "expires_at": future_time,
        }
    }
    
    # Should return the key
    key = store.get_by_secret("sec_valid")
    assert key is not None
    assert key["id"] == "key_valid"


def test_get_by_secret_no_expiry():
    """Test that keys without expiry are returned."""
    store = KeyStore("test-bucket", "keys.json")
    
    store.keys_by_secret = {
        "sec_noexpiry": {
            "id": "key_noexpiry",
            "secret": "sec_noexpiry",
            "name": "No Expiry Key",
            "expires_at": None,
        }
    }
    
    # Should return the key
    key = store.get_by_secret("sec_noexpiry")
    assert key is not None
    assert key["id"] == "key_noexpiry"


def test_encryption_roundtrip():
    """Test that data can be encrypted and decrypted."""
    store = KeyStore("test-bucket", "keys.json", storage_secret="test-secret-key")
    
    test_data = b'{"keys": [{"id": "test", "secret": "sec123"}]}'
    
    # Encrypt
    encrypted = store._encrypt_data(test_data)
    
    # Should have header
    assert encrypted.startswith(store.ENCRYPTION_HEADER)
    assert encrypted != test_data
    
    # Decrypt
    decrypted = store._decrypt_data(encrypted)
    assert decrypted == test_data


def test_encryption_disabled():
    """Test that encryption is disabled without storage_secret."""
    store = KeyStore("test-bucket", "keys.json")
    
    test_data = b'{"keys": []}'
    
    # Without storage_secret, data should not be encrypted
    encrypted = store._encrypt_data(test_data)
    assert encrypted == test_data
    assert not encrypted.startswith(store.ENCRYPTION_HEADER)


def test_decrypt_unencrypted_data():
    """Test that unencrypted data passes through decryption."""
    store = KeyStore("test-bucket", "keys.json", storage_secret="test-secret")
    
    unencrypted_data = b'{"keys": []}'
    
    # Should return unchanged
    decrypted = store._decrypt_data(unencrypted_data)
    assert decrypted == unencrypted_data