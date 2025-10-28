"""CLI tool for managing API keys."""

import json
import sys
from datetime import datetime, timezone
from typing import Optional

import boto3
import click
import requests
from botocore.exceptions import ClientError
from heare import ids

from .models import SecretType


def generate_key_pair() -> tuple[str, str]:
    """
    Generate a key ID and secret using heare-ids.
    
    Generates a 64-character secret with high entropy for security.

    Returns:
        Tuple of (key_id, secret)
    """
    key_id = ids.new("key")
    secret = ids.new("sec", entropy=51)  # 64 chars total (sec_ + metadata + 51 entropy)
    return key_id, secret


class CLI:
    """CLI operations for managing API keys."""

    def __init__(self, bucket: str, key: str, region: str, storage_secret: Optional[str] = None):
        """
        Initialize the CLI.

        Args:
            bucket: S3 bucket name
            key: S3 key (file path)
            region: AWS region
            storage_secret: Optional secret for encrypting data at rest
        """
        self.bucket = bucket
        self.key = key
        self.storage_secret = storage_secret
        self.s3 = boto3.client("s3", region_name=region)

    def load_keys(self) -> list:
        """
        Load keys from S3 with encryption support.

        Returns:
            List of key dictionaries
        """
        from .storage import KeyStore
        
        store = KeyStore(
            bucket=self.bucket,
            key=self.key,
            region="us-east-1",
            storage_secret=self.storage_secret,
        )
        
        try:
            store.load_from_s3()
            return store.get_all_keys()
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return []
            raise

    def save_keys(self, keys: list) -> None:
        """
        Save keys to S3 with encryption support.

        Args:
            keys: List of key dictionaries to save
        """
        from .storage import KeyStore
        
        store = KeyStore(
            bucket=self.bucket,
            key=self.key,
            region="us-east-1",
            storage_secret=self.storage_secret,
        )
        store.save_to_s3(keys)

    def create(
        self,
        name: str,
        metadata: dict,
        secret_type: str,
        expires_at: Optional[str],
        refresh_url: Optional[str],
    ) -> dict:
        """
        Create a new API key.

        Args:
            name: Human-readable name for the key
            metadata: Arbitrary metadata dictionary
            secret_type: Type of secret (shared_secret, etc.)
            expires_at: Optional expiration timestamp (ISO 8601)
            refresh_url: Optional URL to trigger refresh

        Returns:
            The created key dictionary
        """
        keys = self.load_keys()

        key_id, secret = generate_key_pair()
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        new_key = {
            "id": key_id,
            "secret": secret,
            "name": name,
            "secret_type": secret_type,
            "created_at": now,
            "updated_at": None,
            "expires_at": expires_at,
            "metadata": metadata,
        }

        keys.append(new_key)
        self.save_keys(keys)

        # Trigger refresh if URL provided
        if refresh_url:
            try:
                requests.post(refresh_url, timeout=5)
            except Exception as e:
                click.echo(f"Warning: Failed to refresh service: {e}", err=True)

        return new_key

    def list_keys(self) -> list:
        """
        List all API keys.

        Returns:
            List of key dictionaries
        """
        return self.load_keys()

    def delete(self, key_id: str, refresh_url: Optional[str]) -> dict:
        """
        Delete an API key by its ID.

        Args:
            key_id: The key ID to delete
            refresh_url: Optional URL to trigger refresh

        Returns:
            The deleted key dictionary

        Raises:
            ValueError: If the key is not found
        """
        keys = self.load_keys()

        # Find the key to delete
        key_to_delete = None
        for k in keys:
            if k["id"] == key_id:
                key_to_delete = k
                break

        if not key_to_delete:
            raise ValueError(f"API key not found: {key_id}")

        # Remove the key
        keys = [k for k in keys if k["id"] != key_id]
        self.save_keys(keys)

        # Trigger refresh if URL provided
        if refresh_url:
            try:
                requests.post(refresh_url, timeout=5)
            except Exception as e:
                click.echo(f"Warning: Failed to refresh service: {e}", err=True)

        return key_to_delete


@click.group()
def main():
    """Heare Auth - Simple API Key Management"""
    pass


@main.command()
@click.option("--name", required=True, help="Name for the API key")
@click.option("--metadata", default="{}", help="JSON metadata")
@click.option(
    "--secret-type",
    type=click.Choice([SecretType.SHARED_SECRET.value], case_sensitive=False),
    default=SecretType.SHARED_SECRET.value,
    help="Type of secret",
)
@click.option("--expires-at", help="Expiration date/time in ISO 8601 format (e.g., 2025-12-31T23:59:59Z)")
@click.option("--bucket", envvar="S3_BUCKET", required=True, help="S3 bucket name")
@click.option("--key", envvar="S3_KEY", default="keys.json", help="S3 key path")
@click.option("--region", envvar="S3_REGION", default="us-east-1", help="AWS region")
@click.option("--storage-secret", envvar="STORAGE_SECRET", help="Secret for encrypting data at rest")
@click.option("--refresh-url", envvar="REFRESH_URL", default="http://localhost:8080/refresh", help="URL to trigger refresh")
@click.option("--no-refresh", is_flag=True, help="Skip automatic refresh")
def create(name, metadata, secret_type, expires_at, bucket, key, region, storage_secret, refresh_url, no_refresh):
    """Create a new API key."""
    try:
        metadata_dict = json.loads(metadata)
    except json.JSONDecodeError as e:
        click.echo(f"Error: Invalid JSON in metadata: {e}", err=True)
        sys.exit(1)

    # Validate expires_at if provided
    if expires_at:
        try:
            datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        except ValueError as e:
            click.echo(f"Error: Invalid expires_at format: {e}", err=True)
            click.echo("Use ISO 8601 format: YYYY-MM-DDTHH:MM:SSZ", err=True)
            sys.exit(1)

    try:
        cli = CLI(bucket, key, region, storage_secret)
        new_key = cli.create(
            name,
            metadata_dict,
            secret_type,
            expires_at,
            refresh_url if not no_refresh else None,
        )

        click.echo("\nCreated API key:")
        click.echo(f"  ID:          {new_key['id']}")
        click.echo(f"  Secret:      {new_key['secret']}")
        click.echo(f"  Name:        {new_key['name']}")
        click.echo(f"  Secret Type: {new_key['secret_type']}")
        click.echo(f"  Created:     {new_key['created_at']}")
        if new_key.get('expires_at'):
            click.echo(f"  Expires:     {new_key['expires_at']}")
        else:
            click.echo(f"  Expires:     Never")
        
        # Try to refresh if not skipped
        if not no_refresh:
            try:
                response = requests.post(refresh_url, timeout=5)
                response.raise_for_status()
                data = response.json()
                if data.get("success"):
                    click.echo(f"\n✓ Service refreshed - {data.get('keys_loaded', 0)} keys loaded")
            except Exception as e:
                click.echo(f"\n⚠️  Warning: Could not refresh service: {e}", err=True)
                click.echo("   The key was created but the service was not refreshed.", err=True)
                click.echo("   Run 'heare-auth refresh' manually to load the new key.", err=True)
        
        click.echo("\n⚠️  Save the SECRET securely - it will not be shown again!")
        click.echo("    Use the ID for reference and logging.")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option("--bucket", envvar="S3_BUCKET", required=True, help="S3 bucket name")
@click.option("--key", envvar="S3_KEY", default="keys.json", help="S3 key path")
@click.option("--region", envvar="S3_REGION", default="us-east-1", help="AWS region")
@click.option("--storage-secret", envvar="STORAGE_SECRET", help="Secret for encrypting data at rest")
@click.option("--detailed", "-d", is_flag=True, help="Show detailed information")
def list(bucket, key, region, storage_secret, detailed):
    """List all API keys."""
    try:
        cli = CLI(bucket, key, region, storage_secret)
        keys = cli.list_keys()

        if not keys:
            click.echo("No API keys found.")
            return

        if detailed:
            # Detailed view with all fields
            click.echo("\nAPI Keys (Detailed):")
            click.echo("━" * 120)
            for i, k in enumerate(keys):
                if i > 0:
                    click.echo()
                click.echo(f"Name:        {k['name']}")
                click.echo(f"Key ID:      {k['id']}")
                click.echo(f"Secret Type: {k.get('secret_type', 'shared_secret')}")
                click.echo(f"Created:     {k.get('created_at', 'N/A')}")
                click.echo(f"Updated:     {k.get('updated_at', 'Never')}")
                click.echo(f"Expires:     {k.get('expires_at', 'Never')}")
                if k.get('metadata'):
                    click.echo(f"Metadata:    {json.dumps(k['metadata'])}")
            click.echo("━" * 120)
            click.echo(f"Total: {len(keys)} keys\n")
        else:
            # Simple table view
            click.echo("\nAPI Keys:")
            click.echo("━" * 100)
            click.echo(f"{'Name':<30} {'Key ID':<35} {'Type':<15} {'Created':<15}")
            click.echo("━" * 100)

            for k in keys:
                created = k.get("created_at", "N/A")[:10] if k.get("created_at") else "N/A"
                secret_type = k.get("secret_type", "shared_secret")
                click.echo(f"{k['name']:<30} {k['id']:<35} {secret_type:<15} {created:<15}")

            click.echo("━" * 100)
            click.echo(f"Total: {len(keys)} keys\n")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument("key_id")
@click.option("--bucket", envvar="S3_BUCKET", required=True, help="S3 bucket name")
@click.option("--key", envvar="S3_KEY", default="keys.json", help="S3 key path")
@click.option("--region", envvar="S3_REGION", default="us-east-1", help="AWS region")
@click.option("--storage-secret", envvar="STORAGE_SECRET", help="Secret for encrypting data at rest")
def show(key_id, bucket, key, region, storage_secret):
    """Show detailed information about a specific API key."""
    try:
        cli = CLI(bucket, key, region, storage_secret)
        keys = cli.list_keys()
        
        key_data = next((k for k in keys if k["id"] == key_id), None)
        
        if not key_data:
            click.echo(f"Error: API key not found: {key_id}", err=True)
            sys.exit(1)
        
        click.echo("\nAPI Key Details:")
        click.echo("━" * 80)
        click.echo(f"Name:        {key_data['name']}")
        click.echo(f"Key ID:      {key_data['id']}")
        click.echo(f"Secret Type: {key_data.get('secret_type', 'shared_secret')}")
        click.echo(f"Created:     {key_data.get('created_at', 'N/A')}")
        click.echo(f"Updated:     {key_data.get('updated_at', 'Never')}")
        click.echo(f"Expires:     {key_data.get('expires_at', 'Never')}")
        if key_data.get('metadata'):
            click.echo(f"Metadata:    {json.dumps(key_data['metadata'], indent=2)}")
        click.echo("━" * 80)
        click.echo("\n⚠️  The secret is not shown for security reasons.")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument("key_id")
@click.option("--bucket", envvar="S3_BUCKET", required=True, help="S3 bucket name")
@click.option("--key", envvar="S3_KEY", default="keys.json", help="S3 key path")
@click.option("--region", envvar="S3_REGION", default="us-east-1", help="AWS region")
@click.option("--storage-secret", envvar="STORAGE_SECRET", help="Secret for encrypting data at rest")
@click.option("--refresh-url", envvar="REFRESH_URL", default="http://localhost:8080/refresh", help="URL to trigger refresh")
@click.option("--no-refresh", is_flag=True, help="Skip automatic refresh")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def delete(key_id, bucket, key, region, storage_secret, refresh_url, no_refresh, yes):
    """Delete an API key by its ID."""
    try:
        cli = CLI(bucket, key, region, storage_secret)

        # Find the key to show name
        keys = cli.list_keys()
        key_to_delete = next((k for k in keys if k["id"] == key_id), None)

        if not key_to_delete:
            click.echo(f"Error: API key not found: {key_id}", err=True)
            sys.exit(1)

        if not yes:
            if not click.confirm(f"Delete API key '{key_id}' ({key_to_delete['name']})?"):
                click.echo("Cancelled.")
                return

        cli.delete(key_id, refresh_url if not no_refresh else None)
        click.echo("✓ Deleted successfully.")
        
        # Try to refresh if not skipped
        if not no_refresh:
            try:
                response = requests.post(refresh_url, timeout=5)
                response.raise_for_status()
                data = response.json()
                if data.get("success"):
                    click.echo(f"✓ Service refreshed - {data.get('keys_loaded', 0)} keys loaded")
            except Exception as e:
                click.echo(f"\n⚠️  Warning: Could not refresh service: {e}", err=True)
                click.echo("   The key was deleted but the service was not refreshed.", err=True)
                click.echo("   Run 'heare-auth refresh' manually to apply the change.", err=True)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option("--url", default="http://localhost:8080/refresh", help="Refresh endpoint URL")
def refresh(url):
    """Trigger a refresh of keys from S3."""
    try:
        response = requests.post(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        if data.get("success"):
            click.echo(f"✓ Refresh successful - loaded {data.get('keys_loaded', 0)} keys")
        else:
            click.echo("✗ Refresh failed", err=True)
            sys.exit(1)
    except requests.exceptions.RequestException as e:
        click.echo(f"Error: Failed to refresh: {e}", err=True)
        click.echo("\nTip: If running against a Dokku deployment, use:", err=True)
        click.echo("  dokku run <app-name> heare-auth refresh", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
