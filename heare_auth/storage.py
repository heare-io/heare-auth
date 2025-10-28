"""S3 storage and in-memory key store."""

import base64
import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

import boto3
from botocore.exceptions import ClientError
from cryptography.fernet import Fernet, InvalidToken


class KeyStore:
    """Manage API keys in S3 and memory with optional encryption."""
    
    ENCRYPTION_HEADER = b"HEARE_ENCRYPTED_V1:"

    def __init__(self, bucket: str, key: str, region: str = "us-east-1", storage_secret: Optional[str] = None):
        """
        Initialize the key store.

        Args:
            bucket: S3 bucket name
            key: S3 key (file path)
            region: AWS region
            storage_secret: Optional secret for encrypting data at rest
        """
        self.bucket = bucket
        self.key = key
        self.s3 = boto3.client("s3", region_name=region)
        self.keys_by_secret: Dict[str, dict] = {}  # secret -> full key data
        self.keys_by_id: Dict[str, dict] = {}  # id -> full key data
        
        # Set up encryption if storage_secret is provided
        self.encryption_enabled = storage_secret is not None
        self.fernet = None
        if self.encryption_enabled:
            # Derive a Fernet key from the storage secret
            key_bytes = hashlib.sha256(storage_secret.encode()).digest()
            fernet_key = base64.urlsafe_b64encode(key_bytes)
            self.fernet = Fernet(fernet_key)

    def _decrypt_data(self, raw_data: bytes) -> bytes:
        """
        Decrypt data if it's encrypted, otherwise return as-is.
        
        Args:
            raw_data: Raw bytes from S3
            
        Returns:
            Decrypted or original data
        """
        # Check if data is encrypted
        if raw_data.startswith(self.ENCRYPTION_HEADER):
            if not self.fernet:
                raise ValueError("Data is encrypted but no STORAGE_SECRET provided")
            
            # Remove header and decrypt
            encrypted_payload = raw_data[len(self.ENCRYPTION_HEADER):]
            try:
                return self.fernet.decrypt(encrypted_payload)
            except InvalidToken:
                raise ValueError("Failed to decrypt data - invalid STORAGE_SECRET")
        
        # Data is not encrypted
        return raw_data
    
    def _encrypt_data(self, data: bytes) -> bytes:
        """
        Encrypt data if encryption is enabled.
        
        Args:
            data: Data to encrypt
            
        Returns:
            Encrypted data with header, or original data
        """
        if self.encryption_enabled and self.fernet:
            encrypted = self.fernet.encrypt(data)
            return self.ENCRYPTION_HEADER + encrypted
        
        # No encryption
        return data

    def load_from_s3(self) -> int:
        """
        Load keys from S3 into memory.
        
        Supports both encrypted and unencrypted data for transition.

        Returns:
            Number of keys loaded
        """
        try:
            response = self.s3.get_object(Bucket=self.bucket, Key=self.key)
            raw_data = response["Body"].read()
            
            # Decrypt if needed
            decrypted_data = self._decrypt_data(raw_data)
            
            # Parse JSON
            data = json.loads(decrypted_data)

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
        Save keys to S3 with optional encryption.

        Args:
            keys: List of key dictionaries to save
        """
        data = {"keys": keys}
        json_data = json.dumps(data, indent=2).encode('utf-8')
        
        # Encrypt if enabled
        body_data = self._encrypt_data(json_data)
        
        self.s3.put_object(
            Bucket=self.bucket,
            Key=self.key,
            Body=body_data,
            ContentType="application/octet-stream" if self.encryption_enabled else "application/json",
        )

    def get_by_secret(self, secret: str) -> Optional[dict]:
        """
        Get key metadata by secret (for authentication).
        
        Checks expiration and returns None if expired.

        Args:
            secret: The secret value to look up

        Returns:
            Key data dictionary if found and not expired, None otherwise
        """
        key_data = self.keys_by_secret.get(secret)
        
        if key_data is None:
            return None
        
        # Check if expired
        expires_at = key_data.get("expires_at")
        if expires_at:
            try:
                expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                if now > expiry:
                    return None  # Key has expired
            except (ValueError, AttributeError):
                # Invalid expiry format, treat as not expired
                pass
        
        return key_data

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
