# Usage Guide - Heare Auth

This guide shows how to use the heare-auth service in various scenarios.

## Setup

### Installation

```bash
# Clone the repository
git clone https://github.com/heare-io/heare-auth.git
cd heare-auth

# Install dependencies
uv sync

# Activate virtual environment
source .venv/bin/activate
```

### Configuration

Set environment variables:

```bash
export S3_BUCKET=heare-auth-keys
export S3_REGION=us-east-1
export AWS_ACCESS_KEY_ID=your_key_id
export AWS_SECRET_ACCESS_KEY=your_secret_key
```

Optional configuration:

```bash
export S3_KEY=keys.json              # S3 file path (default: keys.json)
export REFRESH_URL=http://localhost:8080/refresh  # For CLI auto-refresh
```

## Creating API Keys

### Basic Key Creation

```bash
heare-auth create --name "My Service"
```

Output:
```
Created API key:
  ID:     key_A1h2xcejqtf2nbrexx3vqjhp41
  Secret: sec_A1h2xdfjqtf2nbrexx3vqjhp42
  Name:   My Service
  Created: 2024-01-20T10:30:00Z

✓ Service refreshed - 5 keys loaded

⚠️  Save the SECRET securely - it will not be shown again!
    Use the ID for reference and logging.
```

**Automatic Refresh:** When run from inside the container (e.g., via `dokku enter`), the CLI automatically refreshes the service to load the new key. If the refresh fails, you'll see a warning and can run `heare-auth refresh` manually.

### Key with Metadata

```bash
heare-auth create \
  --name "Production API" \
  --metadata '{"environment": "production", "service": "api-gateway", "owner": "team@example.com"}'
```

### Skip Auto-Refresh

By default, create and delete commands automatically refresh the service. To skip this:

```bash
heare-auth create --name "My Service" --no-refresh
heare-auth delete key_xxx --no-refresh
```

This is useful when creating multiple keys in bulk - skip refresh for each one, then manually refresh once at the end:

```bash
heare-auth create --name "Service 1" --no-refresh
heare-auth create --name "Service 2" --no-refresh
heare-auth create --name "Service 3" --no-refresh
heare-auth refresh
```

## Managing API Keys

### List All Keys

```bash
heare-auth list
```

Output:
```
API Keys:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Name                  Key ID                             Created
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Production API        key_A1h2xcejqtf2nbrexx3vqjhp41    2024-01-20
Staging API           key_A1h2xegjqtf2nbrexx3vqjhp43    2024-01-20
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total: 2 keys
```

### Delete a Key

```bash
# With confirmation
heare-auth delete key_A1h2xcejqtf2nbrexx3vqjhp41

# Skip confirmation
heare-auth delete key_A1h2xcejqtf2nbrexx3vqjhp41 --yes
```

Output:
```
Delete API key 'key_A1h2xcejqtf2nbrexx3vqjhp41' (My Service)? [y/N]: y
✓ Deleted successfully.
✓ Service refreshed - 4 keys loaded
```

The service is automatically refreshed after deletion.

## Running the Server

### Development Mode

```bash
uvicorn heare_auth.main:app --reload --port 8080
```

### Production Mode

```bash
uvicorn heare_auth.main:app --host 0.0.0.0 --port 8080 --workers 4
```

### Docker

```bash
# Build
docker build -t heare-auth .

# Run
docker run -p 8080:8080 \
  -e S3_BUCKET=heare-auth-keys \
  -e S3_REGION=us-east-1 \
  -e AWS_ACCESS_KEY_ID=xxx \
  -e AWS_SECRET_ACCESS_KEY=yyy \
  heare-auth
```

## Using the API

### Verify an API Key

```bash
curl -X POST http://localhost:8080/verify \
  -H "Content-Type: application/json" \
  -H "User-Agent: MyService/1.0" \
  -d '{"api_key": "sec_A1h2xdfjqtf2nbrexx3vqjhp42"}'
```

**Success Response (200):**
```json
{
  "valid": true,
  "key_id": "key_A1h2xcejqtf2nbrexx3vqjhp41",
  "name": "Production API",
  "metadata": {
    "environment": "production",
    "service": "api-gateway"
  }
}
```

**Failure Response (403):**
```json
{
  "valid": false,
  "error": "Invalid API key"
}
```

### Refresh Keys from S3

**Automatic refresh:** Create and delete commands automatically refresh the service when run from inside the container.

**Manual refresh (if needed):**

Local development:
```bash
heare-auth refresh
```

Dokku deployment:
```bash
dokku enter auth web heare-auth refresh
```

Response:
```
✓ Refresh successful - loaded 5 keys
```

**Using curl directly (from localhost only):**
```bash
curl -X POST http://localhost:8080/refresh
```

Response:
```json
{
  "success": true,
  "keys_loaded": 5,
  "timestamp": "2024-01-20T15:30:00Z"
}
```

### Health Check

```bash
curl http://localhost:8080/health
```

Response:
```json
{
  "status": "ok",
  "keys_count": 5
}
```

## Client Integration

### Python Client

```python
import requests

class HeareAuthClient:
    def __init__(self, auth_url: str, api_secret: str, user_agent: str = "MyApp/1.0"):
        self.auth_url = auth_url
        self.api_secret = api_secret
        self.user_agent = user_agent
    
    def verify(self) -> dict:
        """Verify the API key and get metadata."""
        response = requests.post(
            f"{self.auth_url}/verify",
            json={"api_key": self.api_secret},
            headers={"User-Agent": self.user_agent}
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Auth failed: {response.status_code}")

# Usage
client = HeareAuthClient(
    auth_url="http://localhost:8080",
    api_secret="sec_A1h2xdfjqtf2nbrexx3vqjhp42",
    user_agent="MyService/1.0"
)

result = client.verify()
print(f"Authenticated as: {result['name']}")
print(f"Key ID: {result['key_id']}")
print(f"Metadata: {result['metadata']}")
```

### Requests Middleware

```python
import requests

def with_heare_auth(session: requests.Session, api_secret: str, user_agent: str):
    """Add Heare Auth verification to all requests."""
    
    def verify_auth():
        response = session.post(
            "http://localhost:8080/verify",
            json={"api_key": api_secret},
            headers={"User-Agent": user_agent}
        )
        if response.status_code != 200:
            raise Exception("Authentication failed")
        return response.json()
    
    # Verify once at startup
    auth_data = verify_auth()
    
    # Add key_id to session headers for logging
    session.headers["X-Auth-Key-ID"] = auth_data["key_id"]
    session.headers["User-Agent"] = user_agent
    
    return session

# Usage
session = requests.Session()
session = with_heare_auth(
    session,
    api_secret="sec_A1h2xdfjqtf2nbrexx3vqjhp42",
    user_agent="MyService/1.0"
)

# Now all requests have auth headers
response = session.get("https://api.example.com/data")
```

### FastAPI Dependency

```python
from fastapi import FastAPI, HTTPException, Header
import requests

app = FastAPI()

HEARE_AUTH_URL = "http://localhost:8080"

async def verify_api_key(authorization: str = Header(...)):
    """Dependency to verify API key from Authorization header."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    
    api_secret = authorization.replace("Bearer ", "")
    
    response = requests.post(
        f"{HEARE_AUTH_URL}/verify",
        json={"api_key": api_secret}
    )
    
    if response.status_code != 200:
        raise HTTPException(status_code=403, detail="Invalid API key")
    
    return response.json()

@app.get("/protected")
async def protected_route(auth_data: dict = Depends(verify_api_key)):
    """Protected route that requires valid API key."""
    return {
        "message": "Access granted",
        "key_id": auth_data["key_id"],
        "key_name": auth_data["name"]
    }

# Usage:
# curl -H "Authorization: Bearer sec_A1h2xdfjqtf2nbrexx3vqjhp42" \
#      http://localhost:8000/protected
```

## Viewing Logs

The service outputs structured JSON logs via structlog:

### Successful Verification

```json
{
  "event": "verification_success",
  "key_id": "key_A1h2xcejqtf2nbrexx3vqjhp41",
  "key_name": "Production API",
  "user_agent": "MyService/1.0",
  "timestamp": "2024-01-20T15:30:00.123456Z",
  "level": "info"
}
```

### Failed Verification

```json
{
  "event": "verification_failed",
  "secret_prefix": "sec_",
  "user_agent": "UnknownClient/1.0",
  "timestamp": "2024-01-20T15:30:05.789012Z",
  "level": "warning"
}
```

### Parsing Logs with jq

```bash
# View all verification attempts
uvicorn heare_auth.main:app 2>&1 | jq 'select(.event | contains("verification"))'

# Count verifications by key_id
uvicorn heare_auth.main:app 2>&1 | jq -s 'group_by(.key_id) | map({key_id: .[0].key_id, count: length})'

# View failed attempts
uvicorn heare_auth.main:app 2>&1 | jq 'select(.event == "verification_failed")'
```

## Deployment

### Dokku

```bash
# On Dokku server
dokku apps:create heare-auth

# Set config
dokku config:set heare-auth \
  S3_BUCKET=heare-auth-keys \
  S3_REGION=us-east-1 \
  AWS_ACCESS_KEY_ID=xxx \
  AWS_SECRET_ACCESS_KEY=yyy

# Deploy
git push dokku main

# Check logs
dokku logs heare-auth -t
```

### Environment Best Practices

**Development:**
```bash
export S3_BUCKET=heare-auth-dev
export S3_REGION=us-east-1
export REFRESH_URL=http://localhost:8080/refresh
```

**Production:**
```bash
export S3_BUCKET=heare-auth-prod
export S3_REGION=us-east-1
# No REFRESH_URL (manual refresh only)
# Use IAM roles instead of AWS keys if possible
```

## Troubleshooting

### CLI Can't Find S3 Bucket

```bash
# Check AWS credentials
aws s3 ls s3://$S3_BUCKET

# Create bucket if needed
aws s3 mb s3://$S3_BUCKET --region $S3_REGION
```

### Server Won't Start

```bash
# Check if keys.json exists
aws s3 ls s3://$S3_BUCKET/keys.json

# Create empty keys file
echo '{"keys": []}' | aws s3 cp - s3://$S3_BUCKET/keys.json
```

### Refresh Endpoint Returns 403

The refresh endpoint only works from localhost. You need to access it from inside the running container:

**Dokku:**
```bash
# Enter the running container
dokku enter auth web
# Then inside:
heare-auth refresh
# or
curl -X POST http://localhost:8080/refresh
```

**Docker:**
```bash
# Execute inside running container
docker exec -it <container-id> bash
# Then inside:
heare-auth refresh
# or
curl -X POST http://localhost:8080/refresh
```

**Direct (SSH into server):**
```bash
# Inside the container
heare-auth refresh
```

### Keys Not Loading

```bash
# Check S3 permissions
aws s3api get-bucket-policy --bucket $S3_BUCKET

# Test manually loading
python3 -c "
from heare_auth.storage import KeyStore
store = KeyStore('$S3_BUCKET', 'keys.json', '$S3_REGION')
count = store.load_from_s3()
print(f'Loaded {count} keys')
"
```

## Security Best Practices

1. **Store Secrets Securely**
   - Never commit secrets to git
   - Use environment variables or secrets managers
   - Rotate secrets regularly

2. **Restrict S3 Access**
   - Use IAM roles with minimal permissions
   - Enable S3 bucket versioning
   - Enable S3 server-side encryption

3. **Use HTTPS**
   - Always use HTTPS in production
   - Configure via reverse proxy (nginx, traefik, etc.)

4. **Monitor Usage**
   - Parse structured logs for unusual patterns
   - Alert on high verification failure rates
   - Track which services use which keys

5. **Key Rotation**
   - Create new key for service
   - Update service to use new key
   - Verify new key works
   - Delete old key

## Performance Notes

- **Verification**: < 10ms (in-memory lookup)
- **Key Creation**: ~200ms (includes S3 write)
- **Refresh**: ~100ms (depends on key count)
- **Memory**: ~1KB per key (~10MB for 10K keys)

## Next Steps

- Set up monitoring and alerting
- Configure HTTPS via reverse proxy
- Set up log aggregation (e.g., CloudWatch, DataDog)
- Document your API key distribution process
- Create runbooks for common operations
