# Heare Auth - Simple API Key Service

An extremely simple API key validation service with S3 storage and CLI management.

## Overview

- **API Keys**: Manage via CLI, stored in S3 as a single JSON file
- **Validation**: Single `/verify` endpoint that accepts API key and returns metadata
- **In-Memory**: Fast lookups with S3 refresh on demand
- **Logging**: Structured logs via structlog tracking key IDs and user agents
- **IDs**: Uses `heare-ids` for both key IDs and secrets

## Quick Start

### Installation

```bash
# Install dependencies
uv sync

# Or with pip
pip install -e .
```

### Configuration

Set environment variables:

```bash
export S3_BUCKET=heare-auth-keys
export S3_REGION=us-east-1
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret

# Optional: Encrypt data at rest in S3
export STORAGE_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
```

**Encryption Notes:**
- If `STORAGE_SECRET` is set, all data written to S3 will be encrypted using Fernet encryption (AES-128)
- The system supports transitioning from unencrypted to encrypted storage - it can read both formats
- **Secret format**: Any string works, but use 32+ characters with high entropy
- **Generate**: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`
- **⚠️ Important**: Back up this secret securely - if lost, you cannot decrypt your data!

#### Optional: Metrics Configuration

To enable metrics collection via [heare-stats-client](https://github.com/heare-io/heare-stats-client):

```bash
export PROTOCOL=http
export DEST_HOST=stats-bridge.dokku.heare.io
export DEST_PORT=443
export SECRET=your_metrics_secret
```

The service will track:
- `heare-auth.verify.requests` - Total verification requests
- `heare-auth.verify.success` - Successful verifications
- `heare-auth.verify.failed` - Failed verifications
- `heare-auth.verify.duration` - Verification response time (ms)
- `heare-auth.refresh.requests` - Total refresh requests
- `heare-auth.refresh.success` - Successful refreshes
- `heare-auth.keys.count` - Current number of loaded keys
- `heare-auth.startup.*` - Startup metrics
- `heare-auth.health.requests` - Health check requests

### Create an API Key

```bash
heare-auth create --name "My Service" --metadata '{"env": "prod"}'
```

Output:
```
Created API key:
  ID:          key_A1h2xcejqtf2nbrexx3vqjhp41
  Secret:      sec_A1h2xdfjqtf2nbrexx3vqjhp42
  Name:        My Service
  Secret Type: shared_secret
  Created:     2024-01-20T10:30:00Z
  Expires:     Never

✓ Service refreshed - 5 keys loaded

⚠️  Save the SECRET securely - it will not be shown again!
    Use the ID for reference and logging.
```

**Note:** When run from inside the container, the service automatically refreshes to load the new key.

### Start the Server

```bash
uvicorn heare_auth.main:app --host 0.0.0.0 --port 8080
```

### Verify an API Key

```bash
curl -X POST http://localhost:8080/verify \
  -H "Content-Type: application/json" \
  -H "User-Agent: MyService/1.0" \
  -d '{"api_key": "sec_A1h2xdfjqtf2nbrexx3vqjhp42"}'
```

Response:
```json
{
  "valid": true,
  "key_id": "key_A1h2xcejqtf2nbrexx3vqjhp41",
  "name": "My Service",
  "metadata": {
    "env": "prod"
  }
}
```

## CLI Commands

### Create a key
```bash
# Basic key
heare-auth create --name "Key Name"

# With metadata
heare-auth create --name "Key Name" --metadata '{"key": "value"}'

# With expiration (ISO 8601 format)
heare-auth create --name "Key Name" --expires-at "2025-12-31T23:59:59Z"

# With specific secret type (currently only shared_secret)
heare-auth create --name "Key Name" --secret-type shared_secret
```

The service will automatically refresh after creating the key (when run from inside the container).

### List all keys
```bash
# Simple list
heare-auth list

# Detailed view with all fields
heare-auth list --detailed
```

### Show key details
```bash
heare-auth show key_A1h2xcejqtf2nbrexx3vqjhp41
```

### Delete a key
```bash
heare-auth delete key_A1h2xcejqtf2nbrexx3vqjhp41
```

The service will automatically refresh after deleting the key (when run from inside the container).

### Manual refresh
If needed, you can manually refresh:

**Local development:**
```bash
heare-auth refresh
```

**Dokku deployment (from host):**
```bash
dokku enter auth web heare-auth refresh
```

To skip automatic refresh, use `--no-refresh`:
```bash
heare-auth create --name "Key Name" --no-refresh
heare-auth delete key_xxx --no-refresh
```

## API Endpoints

### `POST /verify`
Validate an API key and return its metadata.

**Request:**
```json
{
  "api_key": "sec_..."
}
```

**Response (200 OK):**
```json
{
  "valid": true,
  "key_id": "key_...",
  "name": "Service Name",
  "metadata": {}
}
```

**Response (403 Forbidden):**
```json
{
  "valid": false,
  "error": "Invalid API key"
}
```

### `POST /refresh`
Reload keys from S3 (localhost only).

### `GET /health`
Health check endpoint. Returns minimal status information without revealing service details.

**Response (200 OK):**
```json
{
  "status": "ok"
}
```

## Architecture

- **Storage**: Single `keys.json` file in S3
- **In-Memory**: All keys loaded on startup for fast lookups
- **Refresh**: Manual refresh via localhost endpoint (CLI triggers this)
- **IDs**: Each key has two heare-ids:
  - `key_*` - Key ID for logging and reference
  - `sec_*` - Secret for authentication

## Logging

Structured JSON logs via structlog:

**Successful verification:**
```json
{
  "event": "verification_success",
  "key_id": "key_...",
  "key_name": "Service Name",
  "user_agent": "MyService/1.0",
  "timestamp": "2024-01-20T15:30:00Z",
  "level": "info"
}
```

**Failed verification:**
```json
{
  "event": "verification_failed",
  "secret_prefix": "sec_",
  "user_agent": "UnknownClient/1.0",
  "timestamp": "2024-01-20T15:30:00Z",
  "level": "warning"
}
```

**Note:** Secrets are NEVER logged - only key IDs.

## Deployment

### Dokku

```bash
# Create app
dokku apps:create heare-auth

# Set environment
dokku config:set heare-auth \
  S3_BUCKET=heare-auth-keys \
  S3_REGION=us-east-1 \
  AWS_ACCESS_KEY_ID=xxx \
  AWS_SECRET_ACCESS_KEY=yyy

# Deploy
git push dokku main
```

### Docker

```bash
docker build -t heare-auth .
docker run -p 8080:8080 \
  -e S3_BUCKET=heare-auth-keys \
  -e S3_REGION=us-east-1 \
  -e AWS_ACCESS_KEY_ID=xxx \
  -e AWS_SECRET_ACCESS_KEY=yyy \
  heare-auth
```

## Development

```bash
# Install dependencies
uv sync

# Run tests
pytest

# Run server (dev mode)
uvicorn heare_auth.main:app --reload

# Format code
ruff format .

# Lint code
ruff check .
```

## Design

See [DESIGN.md](DESIGN.md) for full design documentation.

## License

MIT
