#!/bin/bash
set -e

echo "Testing heare-auth end-to-end..."

# Check if CLI is available
if ! command -v heare-auth &> /dev/null; then
    echo "Error: heare-auth CLI not found"
    exit 1
fi

echo "✓ CLI available"

# Test help commands
heare-auth --help > /dev/null
heare-auth create --help > /dev/null
heare-auth list --help > /dev/null
heare-auth delete --help > /dev/null

echo "✓ Help commands work"

# Test key generation
python3 -c "
from heare_auth.cli import generate_key_pair
key_id, secret = generate_key_pair()
assert key_id.startswith('key_')
assert secret.startswith('sec_')
assert key_id != secret
print('✓ Key generation works')
"

# Test models
python3 -c "
from heare_auth.models import VerifyRequest, VerifyResponse
req = VerifyRequest(api_key='sec_test123')
assert req.api_key == 'sec_test123'
print('✓ Models work')
"

# Test storage (without S3)
python3 -c "
from heare_auth.storage import KeyStore
store = KeyStore('test-bucket', 'keys.json')
store.keys_by_secret = {'sec_test': {'id': 'key_test', 'name': 'Test'}}
assert store.get_by_secret('sec_test') is not None
print('✓ Storage works')
"

echo ""
echo "All tests passed! ✓"
echo ""
echo "To run the full system, you need to:"
echo "1. Set S3_BUCKET, AWS credentials in environment"
echo "2. Run: uvicorn heare_auth.main:app --reload"
echo "3. Create keys with: heare-auth create --name 'Test'"
