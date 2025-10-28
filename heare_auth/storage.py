"""S3 storage and in-memory key store."""

import json
from typing import Dict, List, Optional

import boto3
from botocore.exceptions import ClientError


class KeyStore:
    """Manage API keys in S3 and memory."""

    def __init__(self, bucket: str, key: str, region: str = "us-east-1"):
        """
        Initialize the key store.

        Args:
            bucket: S3 bucket name
            key: S3 key (file path)
            region: AWS region
        """
        self.bucket = bucket
        self.key = key
        self.s3 = boto3.client("s3", region_name=region)
        self.keys_by_secret: Dict[str, dict] = {}  # secret -> full key data
        self.keys_by_id: Dict[str, dict] = {}  # id -> full key data

    def load_from_s3(self) -> int:
        """
        Load keys from S3 into memory.

        Returns:
            Number of keys loaded
        """
        try:
            response = self.s3.get_object(Bucket=self.bucket, Key=self.key)
            data = json.loads(response["Body"].read())

            # Build both indices for fast lookup
            self.keys_by_secret = {k["secret"]: k for k in data["keys"]}
            self.keys_by_id = {k["id"]: k for k in data["keys"]}

            return len(self.keys_by_secret)
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                # File doesn't exist yet, start with empty store
                self.keys_by_secret = {}
                self.keys_by_id = {}
                return 0
            raise

    def save_to_s3(self, keys: List[dict]) -> None:
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

    def get_by_secret(self, secret: str) -> Optional[dict]:
        """
        Get key metadata by secret (for authentication).

        Args:
            secret: The secret value to look up

        Returns:
            Key data dictionary if found, None otherwise
        """
        return self.keys_by_secret.get(secret)

    def get_by_id(self, key_id: str) -> Optional[dict]:
        """
        Get key metadata by ID (for lookup).

        Args:
            key_id: The key ID to look up

        Returns:
            Key data dictionary if found, None otherwise
        """
        return self.keys_by_id.get(key_id)

    def get_all_keys(self) -> List[dict]:
        """
        Get all keys.

        Returns:
            List of all key dictionaries
        """
        return list(self.keys_by_id.values())
