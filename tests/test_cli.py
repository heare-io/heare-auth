"""Tests for CLI module."""

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from heare_auth.cli import CLI, generate_key_pair, main


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


# --- Tests for CLI.update_metadata ---


class TestUpdateMetadata:
    """Tests for CLI.update_metadata method."""

    def _make_cli(self):
        """Create a CLI instance with mocked S3."""
        cli = CLI("test-bucket", "keys.json", "us-east-1")
        return cli

    def _sample_keys(self):
        return [
            {
                "id": "key_abc123",
                "secret": "sec_abc123",
                "name": "Test Key",
                "secret_type": "shared_secret",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": None,
                "expires_at": None,
                "metadata": {"env": "test"},
            }
        ]

    @patch.object(CLI, "save_keys")
    @patch.object(CLI, "load_keys")
    def test_update_metadata_replace(self, mock_load, mock_save):
        """Test replacing metadata entirely."""
        cli = self._make_cli()
        mock_load.return_value = self._sample_keys()

        result = cli.update_metadata("key_abc123", {"team": "backend"})

        assert result["metadata"] == {"team": "backend"}
        assert result["updated_at"] is not None
        mock_save.assert_called_once()

    @patch.object(CLI, "save_keys")
    @patch.object(CLI, "load_keys")
    def test_update_metadata_merge(self, mock_load, mock_save):
        """Test merging metadata with existing values."""
        cli = self._make_cli()
        mock_load.return_value = self._sample_keys()

        result = cli.update_metadata("key_abc123", {"team": "backend"}, merge=True)

        assert result["metadata"] == {"env": "test", "team": "backend"}
        assert result["updated_at"] is not None
        mock_save.assert_called_once()

    @patch.object(CLI, "save_keys")
    @patch.object(CLI, "load_keys")
    def test_update_metadata_merge_overwrites_existing_key(self, mock_load, mock_save):
        """Test that merge overwrites conflicting keys."""
        cli = self._make_cli()
        mock_load.return_value = self._sample_keys()

        result = cli.update_metadata("key_abc123", {"env": "production"}, merge=True)

        assert result["metadata"] == {"env": "production"}

    @patch.object(CLI, "load_keys")
    def test_update_metadata_key_not_found(self, mock_load):
        """Test updating metadata for non-existent key."""
        cli = self._make_cli()
        mock_load.return_value = self._sample_keys()

        try:
            cli.update_metadata("key_nonexistent", {"team": "backend"})
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "not found" in str(e)


# --- Tests for CLI verify command ---


class TestVerifyCommand:
    """Tests for the verify CLI command."""

    def test_verify_remote_success(self):
        """Test verify command against running service (success)."""
        runner = CliRunner()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "valid": True,
            "key_id": "key_abc123",
            "name": "Test Key",
            "metadata": {"env": "test"},
        }

        with patch("heare_auth.cli.requests.post", return_value=mock_response):
            result = runner.invoke(main, ["verify", "sec_test123"])

        assert result.exit_code == 0
        assert "Valid API key" in result.output
        assert "key_abc123" in result.output
        assert "Test Key" in result.output
        assert "test" in result.output

    def test_verify_remote_invalid(self):
        """Test verify command against running service (invalid key)."""
        runner = CliRunner()
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.json.return_value = {"valid": False, "error": "Invalid API key"}

        with patch("heare_auth.cli.requests.post", return_value=mock_response):
            result = runner.invoke(main, ["verify", "sec_invalid"])

        assert result.exit_code == 1
        assert "Invalid API key" in result.output

    def test_verify_remote_connection_error(self):
        """Test verify command when service is not running."""
        import requests as req

        runner = CliRunner()

        with patch(
            "heare_auth.cli.requests.post",
            side_effect=req.exceptions.ConnectionError("refused"),
        ):
            result = runner.invoke(main, ["verify", "sec_test123"])

        assert result.exit_code == 1
        assert "Could not connect" in result.output
        assert "--local" in result.output

    def test_verify_local_success(self):
        """Test verify command with --local flag (success)."""
        runner = CliRunner()

        mock_store_cls = MagicMock()
        mock_store = MagicMock()
        mock_store_cls.return_value = mock_store
        mock_store.load_from_s3.return_value = 1
        mock_store.get_by_secret.return_value = {
            "id": "key_abc123",
            "secret": "sec_test123",
            "name": "Test Key",
            "expires_at": None,
            "metadata": {"env": "staging"},
        }

        with patch("heare_auth.cli.KeyStore", mock_store_cls):
            result = runner.invoke(main, [
                "verify", "sec_test123", "--local", "--bucket", "test-bucket"
            ])

        assert result.exit_code == 0
        assert "Valid API key" in result.output
        assert "key_abc123" in result.output
        assert "staging" in result.output

    def test_verify_local_invalid(self):
        """Test verify command with --local flag (invalid key)."""
        runner = CliRunner()

        mock_store_cls = MagicMock()
        mock_store = MagicMock()
        mock_store_cls.return_value = mock_store
        mock_store.load_from_s3.return_value = 1
        mock_store.get_by_secret.return_value = None

        with patch("heare_auth.cli.KeyStore", mock_store_cls):
            result = runner.invoke(main, [
                "verify", "sec_invalid", "--local", "--bucket", "test-bucket"
            ])

        assert result.exit_code == 1
        assert "Invalid API key" in result.output

    def test_verify_local_requires_bucket(self):
        """Test that --local requires --bucket."""
        runner = CliRunner()
        # Clear S3_BUCKET env var to ensure it's not set
        result = runner.invoke(main, ["verify", "sec_test123", "--local"], env={"S3_BUCKET": ""})

        assert result.exit_code == 1
        assert "--bucket is required" in result.output


# --- Tests for CLI set-metadata command ---


class TestSetMetadataCommand:
    """Tests for the set-metadata CLI command."""

    @patch.object(CLI, "save_keys")
    @patch.object(CLI, "load_keys")
    def test_set_metadata_replace(self, mock_load, mock_save):
        """Test set-metadata command replaces metadata."""
        mock_load.return_value = [
            {
                "id": "key_abc123",
                "secret": "sec_abc123",
                "name": "Test Key",
                "metadata": {"old": "value"},
                "updated_at": None,
            }
        ]

        runner = CliRunner()
        result = runner.invoke(main, [
            "set-metadata", "key_abc123", '{"new": "value"}',
            "--bucket", "test-bucket", "--no-refresh",
        ])

        assert result.exit_code == 0
        assert "Metadata updated" in result.output
        assert "new" in result.output

    @patch.object(CLI, "save_keys")
    @patch.object(CLI, "load_keys")
    def test_set_metadata_merge(self, mock_load, mock_save):
        """Test set-metadata command with --merge flag."""
        mock_load.return_value = [
            {
                "id": "key_abc123",
                "secret": "sec_abc123",
                "name": "Test Key",
                "metadata": {"existing": "value"},
                "updated_at": None,
            }
        ]

        runner = CliRunner()
        result = runner.invoke(main, [
            "set-metadata", "key_abc123", '{"new": "value"}',
            "--merge", "--bucket", "test-bucket", "--no-refresh",
        ])

        assert result.exit_code == 0
        assert "Metadata updated" in result.output
        # Both old and new keys should be in the output
        assert "existing" in result.output
        assert "new" in result.output

    def test_set_metadata_invalid_json(self):
        """Test set-metadata command with invalid JSON."""
        runner = CliRunner()
        result = runner.invoke(main, [
            "set-metadata", "key_abc123", "not-json",
            "--bucket", "test-bucket", "--no-refresh",
        ])

        assert result.exit_code == 1
        assert "Invalid JSON" in result.output

    def test_set_metadata_non_dict_json(self):
        """Test set-metadata command with non-dict JSON."""
        runner = CliRunner()
        result = runner.invoke(main, [
            "set-metadata", "key_abc123", '["a", "b"]',
            "--bucket", "test-bucket", "--no-refresh",
        ])

        assert result.exit_code == 1
        assert "must be a JSON object" in result.output

    @patch.object(CLI, "load_keys")
    def test_set_metadata_key_not_found(self, mock_load):
        """Test set-metadata command with non-existent key."""
        mock_load.return_value = []

        runner = CliRunner()
        result = runner.invoke(main, [
            "set-metadata", "key_nonexistent", '{"a": "b"}',
            "--bucket", "test-bucket", "--no-refresh",
        ])

        assert result.exit_code == 1
        assert "not found" in result.output
