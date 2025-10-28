"""Tests for CLI module."""

from heare_auth.cli import generate_key_pair


def test_generate_key_pair():
    """Test generating a key pair."""
    key_id, secret = generate_key_pair()

    # Check prefixes
    assert key_id.startswith("key_")
    assert secret.startswith("sec_")

    # Check they are different
    assert key_id != secret

    # Check they have reasonable length (heare-ids format)
    assert len(key_id) > 10
    assert len(secret) > 10


def test_generate_key_pair_uniqueness():
    """Test that generated keys are unique."""
    key_id1, secret1 = generate_key_pair()
    key_id2, secret2 = generate_key_pair()

    # All should be different
    assert key_id1 != key_id2
    assert secret1 != secret2
    assert key_id1 != secret1
    assert key_id2 != secret2


def test_secret_length():
    """Test that secrets are 64 characters for high entropy."""
    key_id, secret = generate_key_pair()
    
    assert len(secret) == 64, f"Secret should be 64 chars, got {len(secret)}"
    assert secret.startswith("sec_")
    
    # Test multiple generations to ensure consistency
    for _ in range(10):
        _, s = generate_key_pair()
        assert len(s) == 64
