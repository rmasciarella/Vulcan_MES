# Security Implementation Guide

## Quick Start

To activate the enhanced security features in your Vulcan Engine API, follow these steps:

### 1. Install Security Dependencies

```bash
cd backend

# Add security dependencies
uv add pyotp qrcode pillow bleach slowapi redis
```

### 2. Database Migration for MFA Fields

Create a new Alembic migration to add MFA fields to the User table:

```bash
# Generate migration
alembic revision --autogenerate -m "Add MFA fields to User model"

# Review the generated migration file, then apply it
alembic upgrade head
```

### 3. Update Main Application

Replace the current `main.py` with the secure version:

```bash
# Backup current main.py
cp app/main.py app/main_original.py

# Use the secure version
cp app/main_secure.py app/main.py
```

Or update your existing `main.py` to include the security middleware:

```python
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.validation import ValidationMiddleware
from app.core.rate_limiter import RateLimitMiddleware

# Add middleware in the correct order (reverse application)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(ValidationMiddleware)
```

### 4. Add MFA Routes

Update `/app/api/main.py` to include MFA routes:

```python
from app.api.routes import mfa

# Add to api_router
api_router.include_router(
    mfa.router,
    prefix="/mfa",
    tags=["mfa"]
)
```

### 5. Configure Redis (for Production)

For distributed rate limiting in production:

```yaml
# docker-compose.yml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}

volumes:
  redis_data:
```

### 6. Environment Configuration

Update your `.env` file:

```env
# Redis Configuration
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=your-secure-redis-password
REDIS_SSL=false

# Security Features
ENVIRONMENT=production
ENABLE_RESPONSE_COMPRESSION=true
COMPRESSION_MINIMUM_SIZE=500
```

### 7. Test Security Features

Run the test suite to verify security implementations:

```bash
# Run security tests
pytest app/tests/security/ -v

# Test rate limiting
curl -X POST http://localhost:8000/api/v1/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test"}' \
  --verbose 2>&1 | grep -i "x-ratelimit"

# Check security headers
curl -I http://localhost:8000/api/v1/users/me | grep -E "X-Content-Type|X-Frame|Strict-Transport"
```

## MFA User Flow

### Setup MFA for a User

1. **Initialize MFA Setup**
```bash
curl -X POST http://localhost:8000/api/v1/mfa/setup \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

Response includes:
- QR code (base64 encoded)
- Secret for manual entry
- Backup codes

2. **Enable MFA**
```bash
curl -X POST http://localhost:8000/api/v1/mfa/enable \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"token":"123456"}'
```

3. **Login with MFA**
```bash
# Step 1: Initial login
curl -X POST http://localhost:8000/api/v1/login/access-token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user@example.com&password=yourpassword"

# Step 2: MFA verification
curl -X POST http://localhost:8000/api/v1/mfa/verify \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"token":"123456"}'
```

## Security Best Practices

### 1. Password Requirements
- Minimum 12 characters
- Must include uppercase, lowercase, numbers, and special characters
- Check against common password lists
- Implement password history

### 2. MFA Enforcement
- Require MFA for all admin accounts
- Enforce MFA for sensitive operations
- Provide grace period for MFA adoption
- Monitor MFA usage metrics

### 3. Rate Limiting Tuning
- Adjust limits based on usage patterns
- Implement geographic-based limits
- Use exponential backoff for repeat offenders
- Monitor and alert on limit violations

### 4. Security Headers Customization
- Adjust CSP directives for your frontend
- Enable HSTS preloading after testing
- Configure report-uri for CSP violations
- Test with securityheaders.com

### 5. Input Validation Rules
- Validate all user inputs
- Sanitize HTML content
- Escape special characters
- Use parameterized queries

## Monitoring & Alerts

### Key Metrics to Track
- Failed authentication attempts
- Rate limit violations
- MFA adoption rate
- Security header compliance
- Input validation failures

### Alert Thresholds
- 5+ failed logins from same IP
- 100+ rate limit hits in 5 minutes
- Unusual MFA verification patterns
- Security header missing on responses

### Logging Configuration
```python
# Enhanced security logging
SECURITY_LOG_CONFIG = {
    "version": 1,
    "handlers": {
        "security": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "logs/security.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 10,
            "formatter": "security"
        }
    },
    "loggers": {
        "app.core.security": {"level": "INFO", "handlers": ["security"]},
        "app.core.mfa": {"level": "INFO", "handlers": ["security"]},
        "app.core.rate_limiter": {"level": "WARNING", "handlers": ["security"]},
        "app.middleware.validation": {"level": "WARNING", "handlers": ["security"]}
    }
}
```

## Troubleshooting

### Common Issues

1. **MFA QR Code Not Generating**
   - Check Pillow installation: `pip show pillow`
   - Verify qrcode package: `pip show qrcode`

2. **Rate Limiting Not Working**
   - Check Redis connection: `redis-cli ping`
   - Verify middleware order in main.py
   - Check Redis configuration in settings

3. **Security Headers Missing**
   - Verify middleware is added to app
   - Check environment setting
   - Review proxy/load balancer configuration

4. **Input Validation Too Strict**
   - Adjust validation patterns in middleware
   - Enable strict_mode only in production
   - Add paths to skip_paths list

## Performance Optimization

### Caching Strategy
```python
# Cache MFA verification results
from functools import lru_cache
from datetime import datetime, timedelta

@lru_cache(maxsize=1000)
def verify_mfa_cached(user_id: str, token: str, timestamp: int) -> bool:
    # Cache for 30 seconds
    return mfa_service.verify_totp(secret, token)
```

### Async Rate Limiting
```python
# Use async Redis client
import aioredis

async def check_rate_limit_async(key: str, limit: int) -> bool:
    redis = await aioredis.create_redis_pool('redis://localhost')
    # Implement async rate check
    await redis.close()
```

## Compliance Checklist

- [ ] Enable MFA for all privileged accounts
- [ ] Configure rate limiting on all endpoints
- [ ] Implement security headers on all responses
- [ ] Validate all user inputs
- [ ] Log all security events
- [ ] Regular security assessments
- [ ] Dependency vulnerability scanning
- [ ] Penetration testing quarterly
- [ ] Security training for developers
- [ ] Incident response plan documented

## Next Steps

1. **Test in Staging**: Deploy to staging environment first
2. **Load Testing**: Verify performance with security features
3. **Security Scan**: Run OWASP ZAP or similar tools
4. **Documentation**: Update API documentation with security requirements
5. **Training**: Educate team on new security features

For questions or issues, contact the security team at security@example.com
