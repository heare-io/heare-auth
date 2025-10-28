# Dokku Setup Status

## ✅ Completed Steps

1. **App Created**: `auth` app created on dokku.heare.io
2. **Domain Configured**: auth.dokku.heare.io added
3. **Stack Updated**: heroku-22 stack configured
4. **Build System**: Procfile-based deployment working
5. **Dependencies Installed**: All Python packages installed successfully
6. **Initial Config Set**:
   - S3_BUCKET=heare-auth-prod
   - S3_KEY=keys.json
   - S3_REGION=us-east-1
   - PORT=8080

## ⏳ Pending Steps

### 1. Set AWS Credentials

The app built successfully but fails to start because AWS credentials are missing.

```bash
ssh dokku@dokku.heare.io config:set auth \
  AWS_ACCESS_KEY_ID=YOUR_ACCESS_KEY \
  AWS_SECRET_ACCESS_KEY=YOUR_SECRET_KEY
```

This will automatically restart the app.

### 2. Create S3 Bucket and Initialize

```bash
# Create bucket
aws s3 mb s3://heare-auth-prod --region us-east-1

# Initialize with empty keys file
echo '{"keys": []}' | aws s3 cp - s3://heare-auth-prod/keys.json

# Verify
aws s3 ls s3://heare-auth-prod/
```

### 3. Enable Let's Encrypt

Once the app is running successfully:

```bash
ssh dokku@dokku.heare.io letsencrypt:enable auth
```

This will:
- Obtain an SSL certificate from Let's Encrypt
- Configure HTTPS automatically
- Set up auto-renewal

### 4. Set up Auto-Renewal (if not automatic)

```bash
ssh dokku@dokku.heare.io letsencrypt:auto-renew auth
```

## Current Status

- **App URL**: http://auth.dokku.heare.io (HTTP only, no HTTPS yet)
- **Deployment**: Build succeeded, container start failed (no AWS creds)
- **Port**: 8080 (internal), mapped to port 80 (HTTP)

## Error Details

The app is failing at startup with:
```
botocore.exceptions.NoCredentialsError: Unable to locate credentials
```

This happens in the `lifespan` function when trying to load keys from S3.

## Next Actions

1. **Set AWS credentials** (required to start)
2. **Create and initialize S3 bucket** (required for operation)
3. **Enable Let's Encrypt** (for HTTPS)
4. **Test the deployment**:
   ```bash
   # Check logs
   ssh dokku@dokku.heare.io logs auth -t
   
   # Test health endpoint
   curl https://auth.dokku.heare.io/health
   ```

## Full Deployment Command Sequence

```bash
# 1. Set AWS credentials
ssh dokku@dokku.heare.io config:set auth \
  AWS_ACCESS_KEY_ID=YOUR_KEY \
  AWS_SECRET_ACCESS_KEY=YOUR_SECRET

# 2. Create S3 bucket (from local machine)
aws s3 mb s3://heare-auth-prod --region us-east-1
echo '{"keys": []}' | aws s3 cp - s3://heare-auth-prod/keys.json

# 3. Wait for app to start, then enable HTTPS
ssh dokku@dokku.heare.io letsencrypt:enable auth

# 4. Verify deployment
curl https://auth.dokku.heare.io/health

# 5. Create first API key
heare-auth create --name "First Key" \
  --metadata '{"env": "production"}'
```

## Configuration Summary

### Environment Variables Set
- `S3_BUCKET`: heare-auth-prod
- `S3_KEY`: keys.json
- `S3_REGION`: us-east-1
- `PORT`: 8080
- `DOKKU_LETSENCRYPT_EMAIL`: admin@heare.io (global)

### Environment Variables Needed
- `AWS_ACCESS_KEY_ID`: ❌ Not set
- `AWS_SECRET_ACCESS_KEY`: ❌ Not set

### Buildpack Configuration
- Stack: `gliderlabs/herokuish:latest-22`
- Buildpack: `https://github.com/heroku/heroku-buildpack-python`
- Python Version: 3.12.7

### Domain Configuration
- Domain: auth.dokku.heare.io
- SSL: ❌ Not enabled yet (pending Let's Encrypt)
- Port Mapping: HTTP:80:5000

## Troubleshooting

### If app still won't start after setting AWS credentials:

```bash
# Check logs
ssh dokku@dokku.heare.io logs auth --tail 100

# Check config
ssh dokku@dokku.heare.io config auth

# Manually trigger rebuild
git commit --allow-empty -m "trigger rebuild"
git push dokku main

# Or restart the app
ssh dokku@dokku.heare.io ps:restart auth
```

### If Let's Encrypt fails:

```bash
# Check letsencrypt logs
ssh dokku@dokku.heare.io letsencrypt:log auth

# Verify domain is accessible
curl -I http://auth.dokku.heare.io

# Try manual renewal
ssh dokku@dokku.heare.io letsencrypt:enable auth --verbose
```

## Success Criteria

- [ ] AWS credentials configured
- [ ] S3 bucket created and initialized
- [ ] App starts successfully
- [ ] Health check returns 200 OK
- [ ] HTTPS enabled via Let's Encrypt
- [ ] Can create API keys via CLI
- [ ] Can verify API keys via API

## Resources

- **Dokku Documentation**: https://dokku.com/docs/
- **Let's Encrypt Plugin**: https://github.com/dokku/dokku-letsencrypt
- **GitHub Repository**: https://github.com/heare-io/heare-auth
- **Domain**: https://auth.dokku.heare.io (once HTTPS enabled)
