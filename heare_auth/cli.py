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


def generate_key_pair() -> tuple[str, str]:
    """
    Generate a key ID and secret using heare-ids.

    Returns:
        Tuple of (key_id, secret)
    """
    key_id = ids.new("key")
    secret = ids.new("sec")
    return key_id, secret


class CLI:
    """CLI operations for managing API keys."""

    def __init__(self, bucket: str, key: str, region: str):
        """
        Initialize the CLI.

        Args:
            bucket: S3 bucket name
            key: S3 key (file path)
            region: AWS region
        """
        self.bucket = bucket
        self.key = key
        self.s3 = boto3.client("s3", region_name=region)

    def load_keys(self) -> list:
        """
        Load keys from S3.

        Returns:
            List of key dictionaries
        """
        try:
            response = self.s3.get_object(Bucket=self.bucket, Key=self.key)
            data = json.loads(response["Body"].read())
            return data["keys"]
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return []
            raise

    def save_keys(self, keys: list) -> None:
        """
        Save keys to S3.

        Args:
            keys: List of key dictionaries to save
        """
        data = {"keys": keys}
        self.s3.put_object(
            Bucket=self.bucket,
            Key=self.key,
            Body=json.dumps(data, indent=2),
            ContentType="application/json",
        )

    def create(self, name: str, metadata: dict, refresh_url: Optional[str]) -> dict:
        """
        Create a new API key.

        Args:
            name: Human-readable name for the key
            metadata: Arbitrary metadata dictionary
            refresh_url: Optional URL to trigger refresh

        Returns:
            The created key dictionary
        """
        keys = self.load_keys()

        key_id, secret = generate_key_pair()

        new_key = {
            "id": key_id,
            "secret": secret,
            "name": name,
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
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
@click.option("--bucket", envvar="S3_BUCKET", required=True, help="S3 bucket name")
@click.option("--key", envvar="S3_KEY", default="keys.json", help="S3 key path")
@click.option("--region", envvar="S3_REGION", default="us-east-1", help="AWS region")
@click.option("--refresh-url", envvar="REFRESH_URL", help="URL to trigger refresh")
def create(name, metadata, bucket, key, region, refresh_url):
    """Create a new API key."""
    try:
        metadata_dict = json.loads(metadata)
    except json.JSONDecodeError as e:
        click.echo(f"Error: Invalid JSON in metadata: {e}", err=True)
        sys.exit(1)

    try:
        cli = CLI(bucket, key, region)
        new_key = cli.create(name, metadata_dict, refresh_url)

        click.echo("\nCreated API key:")
        click.echo(f"  ID:     {new_key['id']}")
        click.echo(f"  Secret: {new_key['secret']}")
        click.echo(f"  Name:   {new_key['name']}")
        click.echo(f"  Created: {new_key['created_at']}")
        click.echo("\n⚠️  Save the SECRET securely - it will not be shown again!")
        click.echo("    Use the ID for reference and logging.")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option("--bucket", envvar="S3_BUCKET", required=True, help="S3 bucket name")
@click.option("--key", envvar="S3_KEY", default="keys.json", help="S3 key path")
@click.option("--region", envvar="S3_REGION", default="us-east-1", help="AWS region")
def list(bucket, key, region):
    """List all API keys."""
    try:
        cli = CLI(bucket, key, region)
        keys = cli.list_keys()

        if not keys:
            click.echo("No API keys found.")
            return

        click.echo("\nAPI Keys:")
        click.echo("━" * 80)
        click.echo(f"{'Name':<30} {'Key ID':<35} {'Created':<15}")
        click.echo("━" * 80)

        for k in keys:
            created = k["created_at"][:10]
            click.echo(f"{k['name']:<30} {k['id']:<35} {created:<15}")

        click.echo("━" * 80)
        click.echo(f"Total: {len(keys)} keys\n")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument("key_id")
@click.option("--bucket", envvar="S3_BUCKET", required=True, help="S3 bucket name")
@click.option("--key", envvar="S3_KEY", default="keys.json", help="S3 key path")
@click.option("--region", envvar="S3_REGION", default="us-east-1", help="AWS region")
@click.option("--refresh-url", envvar="REFRESH_URL", help="URL to trigger refresh")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def delete(key_id, bucket, key, region, refresh_url, yes):
    """Delete an API key by its ID."""
    try:
        cli = CLI(bucket, key, region)

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

        cli.delete(key_id, refresh_url)
        click.echo("Deleted successfully.")
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
