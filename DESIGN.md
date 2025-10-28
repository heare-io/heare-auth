# Heare Auth - Simple API Key Service

## Overview

An extremely simple API key validation service. API keys are managed via CLI and stored in S3. The service loads keys into memory on startup and provides a single validation endpoint.

## Core Requirements

1. **Single API endpoint**: Accepts API key as JSON payload, returns metadata or 403
2. **S3 storage**: Single JSON file containing all API keys
3. **CLI management**: Create/list/delete keys via command line
4. **In-memory operation**: Load on startup, refresh via localhost endpoint
5. **Dokku deployment**: Environment-based AWS credentials

## Architecture

```
┌─────────────┐
│   CLI Tool  │
│             │
│ - create    │
│ - list      │
│ - delete    │
└──────┬──────┘
       │
       │ Read/Write
       │
       ▼
┌─────────────┐
│  S3 Bucket  │
│             │
│  keys.json  │
└──────┬──────┘
       │
       │ Load on startup
       │ Refresh on /refresh
       │
       ▼
┌─────────────┐
│  Web API    │
│             │
│ - /verify   │
│ - /refresh  │
└─────────────┘
```

## Data Model

### keys.json Structure

```json
{
  "keys": [
    {
      "id": "key_A1h2xcejqtf2nbrexx3vqjhp41",
      "secret": "sec_A1h2xdfjqtf2nbrexx3vqjhp42",
      "name": "Production Service",
      "created_at": "2024-01-20T10:30:00Z",
      "metadata": {
        "service": "api-gateway",
        "environment": "production"
      }
    },
    {
      "id": "key_A1h2xegjqtf2nbrexx3vqjhp43",
      "secret": "sec_A1h2xfhjqtf2nbrexx3vqjhp44",
      "name": "Staging Service",
      "created_at": "2024-01-20T11:00:00Z",
      "metadata": {
        "service": "worker",
        "environment": "staging"
      }
    }
  ]
}
```

### Key Format (using heare-ids)

Both the **key ID** and **secret** are generated using heare-ids:

- **Key ID**: `key_` prefix (for display and logging)
  - Format: `key_<generation><timestamp><entropy>`
  - Example: `key_A1h2xcejqtf2nbrexx3vqjhp41`
  - Base62-encoded components
  
- **Secret**: `sec_` prefix (for actual authentication)
  - Format: `sec_<generation><timestamp><entropy>`
  - Example: `sec_A1h2xdfjqtf2nbrexx3vqjhp42`
  - Base62-encoded components
  - This is the sensitive value that should be kept secure

The **key ID** is used for logging and tracking, while the **secret** is used for authentication.

## API Specification

### POST /verify

Validate an API key and return its metadata.

**Request:**
```http
POST /verify
Content-Type: application/json
User-Agent: MyService/1.0

{
  "api_key": "sec_A1h2xdfjqtf2nbrexx3vqjhp42"
}
```

**Response 200 OK:**
```json
{
  "valid": true,
  "key_id": "key_A1h2xcejqtf2nbrexx3vqjhp41",
  "name": "Production Service",
  "metadata": {
    "service": "api-gateway",
    "environment": "production"
  }
}
```

**Response 403 Forbidden:**
```json
{
  "valid": false,
  "error": "Invalid API key"
}
```

**Response 400 Bad Request:**
```json
{
  "error": "Missing api_key field"
}
```

**Logging:**

Every verification attempt is logged with structlog:
- **Successful verification**: `info` level
- **Failed verification**: `warning` level
- Includes: `key_id`, `user_agent`, `timestamp`, `result`

### POST /refresh

Reload keys from S3. **Only accessible from localhost.**

**Request:**
```http
POST /refresh
X-Forwarded-For: 127.0.0.1

{}
```

**Response 200 OK:**
```json
{
  "success": true,
  "keys_loaded": 5,
  "timestamp": "2024-01-20T15:30:00Z"
}
```

**Response 403 Forbidden:**
```json
{
  "error": "Refresh endpoint only accessible from localhost"
}
```

## CLI Tool

### Commands

#### Create a new API key

```bash
heare-auth create --name "Production Service" --metadata '{"service": "api-gateway", "environment": "production"}'
```

**Output:**
```
Created API key:
  ID:     key_A1h2xcejqtf2nbrexx3vqjhp41
  Secret: sec_A1h2xdfjqtf2nbrexx3vqjhp42
  Name:   Production Service
  Created: 2024-01-20T10:30:00Z

⚠️  Save the SECRET securely - it will not be shown again!
    Use the ID for reference and logging.
```

**Process:**
1. Generate random key
2. Download current keys.json from S3
3. Add new key to list
4. Upload updated keys.json to S3
5. Trigger /refresh endpoint (if --refresh-url provided)

#### List all API keys

```bash
heare-auth list
```

**Output:**
```
API Keys:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Name                  Key ID                             Created
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Production Service    key_A1h2xcejqtf2nbrexx3vqjhp41    2024-01-20
Staging Service       key_A1h2xegjqtf2nbrexx3vqjhp43    2024-01-20
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total: 2 keys
```

Note: Secrets are never shown in list view.

#### Delete an API key

```bash
heare-auth delete key_A1h2xcejqtf2nbrexx3vqjhp41
```

**Output:**
```
Delete API key 'key_A1h2xcejqtf2nbrexx3vqjhp41' (Production Service)? [y/N]: y
Deleted successfully.
```

Note: You delete by key ID, not by secret.

**Process:**
1. Download current keys.json from S3
2. Remove key from list
3. Upload updated keys.json to S3
4. Trigger /refresh endpoint (if --refresh-url provided)

## Configuration

### Environment Variables

```bash
# S3 Configuration
S3_BUCKET=heare-auth-keys
S3_KEY=keys.json
S3_REGION=us-east-1

# AWS Credentials (provided by Dokku/environment)
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...

# Web Server
PORT=8080
HOST=0.0.0.0
```

### CLI Configuration

Optional `~/.heare-auth.toml`:

```toml
[default]
s3_bucket = "heare-auth-keys"
s3_key = "keys.json"
s3_region = "us-east-1"
refresh_url = "http://localhost:8080/refresh"
```

## Implementation Details

### File Structure

```
heare-auth/
├── pyproject.toml
├── README.md
├── DESIGN.md
├── heare_auth/
│   ├── __init__.py
│   ├── main.py          # FastAPI server
│   ├── storage.py       # S3 operations
│   ├── models.py        # Pydantic models
│   └── cli.py           # CLI tool
└── tests/
    ├── test_api.py
    ├── test_storage.py
    └── test_cli.py
```

### Core Components

#### 1. Storage Module (storage.py)

```python
import json
import boto3
from typing import Dict, List, Optional

class KeyStore:
    """Manage API keys in S3 and memory."""
    
    def __init__(self, bucket: str, key: str):
        self.bucket = bucket
        self.key = key
        self.s3 = boto3.client('s3')
        self.keys_by_secret: Dict[str, dict] = {}  # secret -> full key data
        self.keys_by_id: Dict[str, dict] = {}      # id -> full key data
    
    def load_from_s3(self) -> int:
        """Load keys from S3 into memory. Returns count."""
        try:
            response = self.s3.get_object(Bucket=self.bucket, Key=self.key)
            data = json.loads(response['Body'].read())
            
            # Build both indices
            self.keys_by_secret = {k['secret']: k for k in data['keys']}
            self.keys_by_id = {k['id']: k for k in data['keys']}
            
            return len(self.keys_by_secret)
        except self.s3.exceptions.NoSuchKey:
            self.keys_by_secret = {}
            self.keys_by_id = {}
            return 0
    
    def save_to_s3(self, keys: List[dict]):
        """Save keys to S3."""
        data = {'keys': keys}
        self.s3.put_object(
            Bucket=self.bucket,
            Key=self.key,
            Body=json.dumps(data, indent=2),
            ContentType='application/json'
        )
    
    def get_by_secret(self, secret: str) -> Optional[dict]:
        """Get key metadata by secret (for authentication)."""
        return self.keys_by_secret.get(secret)
    
    def get_by_id(self, key_id: str) -> Optional[dict]:
        """Get key metadata by ID (for lookup)."""
        return self.keys_by_id.get(key_id)
```

#### 2. API Server (main.py)

```python
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from datetime import datetime
from .storage import KeyStore
import os
import structlog

# Configure structlog
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=False,
)

logger = structlog.get_logger()

app = FastAPI(title="Heare Auth")

# Initialize key store
store = KeyStore(
    bucket=os.getenv('S3_BUCKET'),
    key=os.getenv('S3_KEY', 'keys.json')
)

@app.on_event("startup")
async def startup():
    """Load keys from S3 on startup."""
    count = store.load_from_s3()
    logger.info("startup", keys_loaded=count)

class VerifyRequest(BaseModel):
    api_key: str

class VerifyResponse(BaseModel):
    valid: bool
    key_id: str | None = None
    name: str | None = None
    metadata: dict = {}
    error: str | None = None

@app.post("/verify", response_model=VerifyResponse)
async def verify(request: VerifyRequest, http_request: Request):
    """Verify an API key."""
    user_agent = http_request.headers.get('user-agent', 'unknown')
    
    # Look up by secret
    key_data = store.get_by_secret(request.api_key)
    
    if key_data is None:
        logger.warning(
            "verification_failed",
            secret_prefix=request.api_key[:4] if len(request.api_key) >= 4 else "***",
            user_agent=user_agent,
        )
        raise HTTPException(status_code=403, detail={
            "valid": False,
            "error": "Invalid API key"
        })
    
    # Log successful verification with key_id (NOT secret)
    logger.info(
        "verification_success",
        key_id=key_data['id'],
        key_name=key_data['name'],
        user_agent=user_agent,
    )
    
    return VerifyResponse(
        valid=True,
        key_id=key_data['id'],
        name=key_data['name'],
        metadata=key_data.get('metadata', {})
    )

@app.post("/refresh")
async def refresh(request: Request):
    """Refresh keys from S3. Only accessible from localhost."""
    # Check if request is from localhost
    client_host = request.client.host
    forwarded_for = request.headers.get('x-forwarded-for', '').split(',')[0].strip()
    
    if client_host not in ('127.0.0.1', 'localhost') and \
       forwarded_for not in ('127.0.0.1', 'localhost', ''):
        logger.warning("refresh_rejected", client_host=client_host, forwarded_for=forwarded_for)
        raise HTTPException(status_code=403, detail={
            "error": "Refresh endpoint only accessible from localhost"
        })
    
    count = store.load_from_s3()
    logger.info("refresh_success", keys_loaded=count)
    
    return {
        "success": True,
        "keys_loaded": count,
        "timestamp": datetime.utcnow().isoformat() + 'Z'
    }

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "keys_count": len(store.keys_by_secret)}
```

#### 3. CLI Tool (cli.py)

```python
import json
import boto3
import click
from datetime import datetime
from typing import Optional
import requests
from heare import ids

def generate_key_pair() -> tuple[str, str]:
    """Generate a key ID and secret using heare-ids."""
    key_id = ids.new('key')
    secret = ids.new('sec')
    return key_id, secret

class CLI:
    def __init__(self, bucket: str, key: str, region: str):
        self.bucket = bucket
        self.key = key
        self.s3 = boto3.client('s3', region_name=region)
    
    def load_keys(self) -> list:
        """Load keys from S3."""
        try:
            response = self.s3.get_object(Bucket=self.bucket, Key=self.key)
            data = json.loads(response['Body'].read())
            return data['keys']
        except self.s3.exceptions.NoSuchKey:
            return []
    
    def save_keys(self, keys: list):
        """Save keys to S3."""
        data = {'keys': keys}
        self.s3.put_object(
            Bucket=self.bucket,
            Key=self.key,
            Body=json.dumps(data, indent=2),
            ContentType='application/json'
        )
    
    def create(self, name: str, metadata: dict, refresh_url: Optional[str]):
        """Create a new API key."""
        keys = self.load_keys()
        
        key_id, secret = generate_key_pair()
        
        new_key = {
            'id': key_id,
            'secret': secret,
            'name': name,
            'created_at': datetime.utcnow().isoformat() + 'Z',
            'metadata': metadata
        }
        
        keys.append(new_key)
        self.save_keys(keys)
        
        # Trigger refresh if URL provided
        if refresh_url:
            try:
                requests.post(refresh_url, timeout=5)
            except Exception as e:
                click.echo(f"Warning: Failed to refresh service: {e}")
        
        return new_key
    
    def list(self) -> list:
        """List all API keys."""
        return self.load_keys()
    
    def delete(self, key_id: str, refresh_url: Optional[str]):
        """Delete an API key by its ID."""
        keys = self.load_keys()
        original_count = len(keys)
        keys = [k for k in keys if k['id'] != key_id]
        
        if len(keys) == original_count:
            raise ValueError(f"API key not found: {key_id}")
        
        self.save_keys(keys)
        
        # Trigger refresh if URL provided
        if refresh_url:
            try:
                requests.post(refresh_url, timeout=5)
            except Exception as e:
                click.echo(f"Warning: Failed to refresh service: {e}")

@click.group()
def main():
    """Heare Auth - Simple API Key Management"""
    pass

@main.command()
@click.option('--name', required=True, help='Name for the API key')
@click.option('--metadata', default='{}', help='JSON metadata')
@click.option('--bucket', envvar='S3_BUCKET', required=True)
@click.option('--key', envvar='S3_KEY', default='keys.json')
@click.option('--region', envvar='S3_REGION', default='us-east-1')
@click.option('--refresh-url', envvar='REFRESH_URL')
def create(name, metadata, bucket, key, region, refresh_url):
    """Create a new API key."""
    cli = CLI(bucket, key, region)
    metadata_dict = json.loads(metadata)
    
    new_key = cli.create(name, metadata_dict, refresh_url)
    
    click.echo(f"\nCreated API key:")
    click.echo(f"  ID:     {new_key['id']}")
    click.echo(f"  Secret: {new_key['secret']}")
    click.echo(f"  Name:   {new_key['name']}")
    click.echo(f"  Created: {new_key['created_at']}")
    click.echo("\n⚠️  Save the SECRET securely - it will not be shown again!")
    click.echo("    Use the ID for reference and logging.")

@main.command()
@click.option('--bucket', envvar='S3_BUCKET', required=True)
@click.option('--key', envvar='S3_KEY', default='keys.json')
@click.option('--region', envvar='S3_REGION', default='us-east-1')
def list(bucket, key, region):
    """List all API keys."""
    cli = CLI(bucket, key, region)
    keys = cli.list()
    
    if not keys:
        click.echo("No API keys found.")
        return
    
    click.echo("\nAPI Keys:")
    click.echo("━" * 80)
    click.echo(f"{'Name':<30} {'Key ID':<35} {'Created':<15}")
    click.echo("━" * 80)
    
    for k in keys:
        created = k['created_at'][:10]
        click.echo(f"{k['name']:<30} {k['id']:<35} {created:<15}")
    
    click.echo("━" * 80)
    click.echo(f"Total: {len(keys)} keys\n")

@main.command()
@click.argument('key_id')
@click.option('--bucket', envvar='S3_BUCKET', required=True)
@click.option('--key', envvar='S3_KEY', default='keys.json')
@click.option('--region', envvar='S3_REGION', default='us-east-1')
@click.option('--refresh-url', envvar='REFRESH_URL')
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation')
def delete(key_id, bucket, key, region, refresh_url, yes):
    """Delete an API key by its ID."""
    cli = CLI(bucket, key, region)
    
    # Find the key to show name
    keys = cli.list()
    key_to_delete = next((k for k in keys if k['id'] == key_id), None)
    
    if not key_to_delete:
        click.echo(f"Error: API key not found: {key_id}")
        return
    
    if not yes:
        if not click.confirm(f"Delete API key '{key_id}' ({key_to_delete['name']})?"):
            click.echo("Cancelled.")
            return
    
    cli.delete(key_id, refresh_url)
    click.echo("Deleted successfully.")

if __name__ == '__main__':
    main()
```

## Deployment

### Dokku Setup

```bash
# Create app
dokku apps:create heare-auth

# Set environment variables
dokku config:set heare-auth \
  S3_BUCKET=heare-auth-keys \
  S3_KEY=keys.json \
  S3_REGION=us-east-1 \
  AWS_ACCESS_KEY_ID=xxx \
  AWS_SECRET_ACCESS_KEY=yyy \
  PORT=8080

# Deploy
git push dokku main

# Check logs
dokku logs heare-auth -t
```

### Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy files
COPY pyproject.toml uv.lock ./
COPY heare_auth ./heare_auth

# Install dependencies
RUN uv sync --frozen

# Expose port
EXPOSE 8080

# Run server
CMD ["uv", "run", "uvicorn", "heare_auth.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

## Dependencies

```toml
[project]
name = "heare-auth"
version = "0.1.0"
description = "Simple API key validation service"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "boto3>=1.34.0",
    "click>=8.1.0",
    "requests>=2.31.0",
    "structlog>=24.1.0",
    "heare-ids>=0.1.0",
]

[project.scripts]
heare-auth = "heare_auth.cli:main"
heare-auth-server = "heare_auth.main:run"
```

## Testing Strategy

### Unit Tests

```python
# tests/test_storage.py
from heare_auth.cli import generate_key_pair

def test_generate_key_pair():
    key_id, secret = generate_key_pair()
    assert key_id.startswith('key_')
    assert secret.startswith('sec_')
    # Both should be heare-ids format
    assert len(key_id) > 10
    assert len(secret) > 10

def test_key_store_get():
    store = KeyStore('bucket', 'key')
    store.keys_by_secret = {
        'sec_test123': {
            'id': 'key_test456',
            'secret': 'sec_test123',
            'name': 'Test',
            'metadata': {}
        }
    }
    assert store.get_by_secret('sec_test123') is not None
    assert store.get_by_secret('invalid') is None
```

### Integration Tests

```python
# tests/test_api.py
from fastapi.testclient import TestClient
from heare_auth.main import app, store

client = TestClient(app)

def test_verify_valid_key():
    store.keys_by_secret = {
        'sec_test123': {
            'id': 'key_test456',
            'secret': 'sec_test123',
            'name': 'Test',
            'metadata': {'env': 'test'}
        }
    }
    
    response = client.post(
        '/verify',
        json={'api_key': 'sec_test123'},
        headers={'User-Agent': 'TestClient/1.0'}
    )
    assert response.status_code == 200
    data = response.json()
    assert data['valid'] is True
    assert data['name'] == 'Test'
    assert data['key_id'] == 'key_test456'

def test_verify_invalid_key():
    store.keys_by_secret = {}
    
    response = client.post('/verify', json={'api_key': 'invalid'})
    assert response.status_code == 403
```

## Usage Examples

### Creating an API Key

```bash
# Set environment variables
export S3_BUCKET=heare-auth-keys
export S3_REGION=us-east-1
export REFRESH_URL=http://localhost:8080/refresh

# Create a key
heare-auth create \
  --name "Production Service" \
  --metadata '{"service": "api-gateway", "env": "prod"}'

# Output:
# Created API key:
#   ID:     key_A1h2xcejqtf2nbrexx3vqjhp41
#   Secret: sec_A1h2xdfjqtf2nbrexx3vqjhp42
#   Name:   Production Service
#   Created: 2024-01-20T10:30:00Z
# 
# ⚠️  Save the SECRET securely - it will not be shown again!
#     Use the ID for reference and logging.
```

### Verifying an API Key

```bash
curl -X POST http://localhost:8080/verify \
  -H "Content-Type: application/json" \
  -H "User-Agent: MyService/1.0" \
  -d '{"api_key": "sec_A1h2xdfjqtf2nbrexx3vqjhp42"}'

# Response:
# {
#   "valid": true,
#   "key_id": "key_A1h2xcejqtf2nbrexx3vqjhp41",
#   "name": "Production Service",
#   "metadata": {
#     "service": "api-gateway",
#     "env": "prod"
#   }
# }

# Logs (structlog JSON output):
# {"event": "verification_success", "key_id": "key_A1h2xcejqtf2nbrexx3vqjhp41", "key_name": "Production Service", "user_agent": "MyService/1.0", "timestamp": "2024-01-20T15:30:00.123456Z", "level": "info"}
```

### Python Client Example

```python
import requests

def verify_api_key(api_key: str, user_agent: str = "MyService/1.0") -> dict:
    response = requests.post(
        'http://localhost:8080/verify',
        json={'api_key': api_key},
        headers={'User-Agent': user_agent}
    )
    
    if response.status_code == 200:
        return response.json()
    else:
        return {'valid': False, 'error': 'Invalid API key'}

# Usage
result = verify_api_key('sec_A1h2xdfjqtf2nbrexx3vqjhp42')
if result['valid']:
    print(f"Valid key ID: {result['key_id']}")
    print(f"Key name: {result['name']}")
    print(f"Metadata: {result['metadata']}")
else:
    print("Invalid key")
```

## Logging

All verification attempts are logged using **structlog** with JSON output for easy parsing and analysis.

### Log Events

#### Successful Verification
```json
{
  "event": "verification_success",
  "key_id": "key_A1h2xcejqtf2nbrexx3vqjhp41",
  "key_name": "Production Service",
  "user_agent": "MyService/1.0",
  "timestamp": "2024-01-20T15:30:00.123456Z",
  "level": "info"
}
```

#### Failed Verification
```json
{
  "event": "verification_failed",
  "secret_prefix": "sec_",
  "user_agent": "UnknownClient/0.1",
  "timestamp": "2024-01-20T15:30:05.789012Z",
  "level": "warning"
}
```

#### Refresh Event
```json
{
  "event": "refresh_success",
  "keys_loaded": 5,
  "timestamp": "2024-01-20T15:35:00.000000Z",
  "level": "info"
}
```

### Security Note

- **Secrets are NEVER logged** - only key IDs
- Failed attempts log only the prefix (`sec_`) to avoid leaking information
- User-Agent is logged to track which services are using each key

## Security Considerations

1. **Key Generation**: Uses `heare-ids` with cryptographic randomness
2. **Separation of Concerns**: Key ID (for logging/reference) separate from secret (for auth)
3. **Storage**: Keys stored in plain text in S3 (rely on S3 encryption at rest)
4. **Transmission**: Use HTTPS in production (configured in reverse proxy)
5. **Refresh Endpoint**: Localhost-only access prevents unauthorized cache invalidation
6. **Logging**: Secrets never logged - only key IDs and user agents tracked
7. **No Rate Limiting**: Add via reverse proxy (nginx, traefik) if needed

## Limitations & Future Enhancements

### Current Limitations
- No key expiration
- No usage tracking
- No rate limiting
- No key scoping/permissions
- No audit logs
- Single S3 file (no sharding)

### Potential Enhancements
- Add key expiration dates
- Track last used timestamp
- Add rate limiting per key
- Support key rotation
- Add usage analytics
- Implement key scoping
- Add audit logging

## Success Criteria

- ✅ CLI can create/list/delete keys
- ✅ API validates keys correctly
- ✅ Server loads keys on startup
- ✅ Refresh endpoint works from localhost
- ✅ Can deploy to Dokku
- ✅ Response time < 10ms for verification

---

**Document Version**: 1.0  
**Status**: Ready for Implementation
