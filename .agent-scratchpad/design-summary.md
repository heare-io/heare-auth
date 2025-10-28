# Design Summary - Heare Auth

## Key Changes from Original Requirements

### ID Generation (using heare-ids)
- **Key ID** (`key_*`): For logging, reference, and display
- **Secret** (`sec_*`): For actual authentication
- Both generated using `heare-ids` library with base62 encoding
- Format: `prefix_<generation><timestamp><entropy>`

### Data Model Update
```json
{
  "id": "key_A1h2xcejqtf2nbrexx3vqjhp41",      // For logging/reference
  "secret": "sec_A1h2xdfjqtf2nbrexx3vqjhp42",  // For authentication
  "name": "Production Service",
  "created_at": "2024-01-20T10:30:00Z",
  "metadata": {}
}
```

### Structured Logging (via structlog)
- JSON output for easy parsing
- All verification attempts logged
- **Secrets NEVER logged** - only key IDs
- Failed attempts log only prefix (`sec_`)
- User-Agent tracked for each request

### Log Events

**Success:**
```json
{
  "event": "verification_success",
  "key_id": "key_...",
  "key_name": "Service Name",
  "user_agent": "MyService/1.0",
  "level": "info"
}
```

**Failure:**
```json
{
  "event": "verification_failed",
  "secret_prefix": "sec_",
  "user_agent": "UnknownClient/1.0",
  "level": "warning"
}
```

## Benefits

1. **Separate ID and Secret**: Can reference keys in logs without exposing secrets
2. **User-Agent Tracking**: Know which services are using each key
3. **Structured Logs**: Easy to parse, query, and analyze
4. **Stripe-like IDs**: Professional, time-ordered, parseable identifiers

## Implementation Notes

- CLI creates both ID and secret using `ids.new('key')` and `ids.new('sec')`
- API lookup by secret, return key_id in response
- Storage has two indices: `keys_by_secret` and `keys_by_id`
- Logging configured in main.py with JSON renderer
- User-Agent extracted from request headers

## Dependencies Added

- `heare-ids>=0.1.0` - For ID generation
- `structlog>=24.1.0` - For structured logging
