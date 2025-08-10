# Security Implementation Documentation

## Overview

This document describes the comprehensive security implementation for the Vulcan Engine production scheduling system. All critical vulnerabilities have been addressed with industry-standard security practices.

## Table of Contents

1. [Authentication & Authorization](#authentication--authorization)
2. [Input Validation](#input-validation)
3. [Rate Limiting](#rate-limiting)
4. [Field-Level Encryption](#field-level-encryption)
5. [Role-Based Access Control (RBAC)](#role-based-access-control-rbac)
6. [Audit Logging](#audit-logging)
7. [Security Headers](#security-headers)
8. [Security Checklist](#security-checklist)

## Authentication & Authorization

### RS256 JWT Implementation

The system now uses **RS256 (RSA with SHA-256)** asymmetric encryption for JWT tokens instead of the less secure HS256 symmetric algorithm.

**Key Features:**
- 4096-bit RSA keys for maximum security
- Automatic key generation and management
- Support for key rotation without service interruption
- Separate access and refresh tokens with different lifetimes

**Configuration:**
```python
# app/core/security.py
ALGORITHM = "RS256"  # Asymmetric encryption
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 30
```

**RSA Key Management:**
```python
# app/core/rsa_keys.py
- Keys stored in app/core/keys/ directory
- Private key: jwt_private.pem (0600 permissions)
- Public key: jwt_public.pem (0644 permissions)
- Old public key retained for rotation: jwt_public_old.pem
```

### Password Security

- **Primary Algorithm:** Argon2id (winner of Password Hashing Competition)
- **Fallback:** bcrypt for compatibility
- **Requirements:**
  - Minimum 12 characters
  - Uppercase and lowercase letters
  - Numbers and special characters
  - No common passwords
  - Password strength scoring

## Input Validation

### Comprehensive Validation Middleware

Location: `app/core/validation.py`

**Protection Against:**
- SQL Injection
- Cross-Site Scripting (XSS)
- Path Traversal
- Command Injection
- XML External Entity (XXE)
- Server-Side Request Forgery (SSRF)

**Validation Patterns:**
```python
# Example patterns
JOB_NUMBER: r"^[A-Z0-9\-]{1,50}$"
EMPLOYEE_ID: r"^EMP[0-9]{3,10}$"
MACHINE_CODE: r"^[A-Z0-9_]{1,20}$"
```

**Request Size Limits:**
- JSON: 1 MB
- Form data: 256 KB
- File uploads: 10 MB

### Pydantic Models with Security

All API endpoints use Pydantic models with built-in validation:

```python
class BaseSecureModel(BaseModel):
    class Config:
        extra = "forbid"  # Prevent parameter pollution
        validate_assignment = True
```

## Rate Limiting

### Adaptive Rate Limiting

Location: `app/core/rate_limiter.py`

**Features:**
- IP-based and user-based limits
- Adaptive limits based on behavior
- Burst attack detection
- Automatic IP blocking for suspicious activity

**Limits:**

| Endpoint Type | Clean IP | After Failures | Blocked Duration |
|--------------|----------|----------------|------------------|
| Authentication | 10/min | 2/min | 15 minutes |
| API (General) | 100/min | 50/min | 5 minutes |
| Heavy Operations | 10/hour | 5/hour | 1 hour |

**Headers:**
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640001234
Retry-After: 300
```

## Field-Level Encryption

### AES-256 Encryption for Sensitive Data

Location: `app/core/encryption.py`

**Encrypted Fields:**

**Operator Data:**
- Social Security Number (SSN)
- Phone numbers
- Home addresses
- Salary information
- Banking details

**Job Data:**
- Customer details
- Special instructions
- Cost/pricing data
- Proprietary information

**Implementation:**
```python
# Encryption context for key derivation
CONTEXTS = {
    "operator_pii": "Personal Identifiable Information",
    "job_sensitive": "Sensitive business data",
    "api_response": "Data in transit"
}
```

**Key Management:**
- Master key stored in environment variable: `FIELD_ENCRYPTION_KEY`
- Context-specific key derivation using PBKDF2
- Automatic encryption/decryption with SQLAlchemy events

## Role-Based Access Control (RBAC)

### Roles and Permissions

Location: `app/core/security_enhanced.py`

**Roles Hierarchy:**

1. **OPERATOR**
   - View jobs
   - View schedules

2. **SCHEDULER**
   - All OPERATOR permissions
   - Create/edit jobs
   - View operators and machines
   - Create schedules

3. **MANAGER**
   - All SCHEDULER permissions
   - Delete jobs
   - Manage operators
   - Publish schedules
   - View reports

4. **ADMIN**
   - All MANAGER permissions
   - Manage machines
   - Execute schedules
   - Access admin panel

5. **SUPERADMIN**
   - All permissions
   - System configuration
   - User management

### Using RBAC in Endpoints

```python
from app.api.deps import require_role, require_permission

@router.post("/jobs", dependencies=[Depends(require_permission("create_jobs"))])
async def create_job(...):
    pass

@router.delete("/jobs/{id}", dependencies=[Depends(require_role(["admin", "superadmin"]))])
async def delete_job(...):
    pass
```

## Audit Logging

### Comprehensive Security Event Logging

Location: `app/core/security_enhanced.py`

**Logged Events:**

1. **Authentication Events**
   - Login attempts (success/failure)
   - Token generation/refresh
   - Password changes
   - Account lockouts

2. **Data Access Events**
   - CRUD operations on sensitive data
   - Report generation
   - Data exports

3. **Security Events**
   - Failed authorization attempts
   - Input validation failures
   - Rate limit violations
   - Suspicious activity detection

**Log Format:**
```json
{
  "timestamp": "2024-01-15T10:30:45Z",
  "event_type": "login_success",
  "user_id": "user123",
  "ip_address": "192.168.1.1",
  "correlation_id": "abc-123-def",
  "details": {
    "method": "password",
    "mfa": true
  }
}
```

**Storage:** `security_audit.log` with rotation and retention policies

## Security Headers

### Comprehensive Security Headers

**Implemented Headers:**

```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), microphone=(), camera=()
Strict-Transport-Security: max-age=31536000; includeSubDomains (HTTPS only)
Content-Security-Policy: default-src 'self'; script-src 'self' 'nonce-{random}'; ...
```

## Security Checklist

### Deployment Checklist

- [ ] **Environment Variables Set:**
  - [ ] `FIELD_ENCRYPTION_KEY` - Base64 encoded 32-byte key
  - [ ] `SECRET_KEY` - Random 32+ character string
  - [ ] `DATABASE_URL` - With SSL enabled
  - [ ] `ENVIRONMENT` - Set to "production"

- [ ] **RSA Keys Generated:**
  - [ ] Run `python -c "from app.core.rsa_keys import rsa_key_manager; rsa_key_manager.generate_keys()"`
  - [ ] Backup keys securely
  - [ ] Set appropriate file permissions

- [ ] **Database Security:**
  - [ ] SSL/TLS enabled for connections
  - [ ] Encrypted at rest
  - [ ] Regular backups with encryption
  - [ ] Principle of least privilege for DB users

- [ ] **Network Security:**
  - [ ] HTTPS only (redirect HTTP)
  - [ ] TLS 1.2+ only
  - [ ] Strong cipher suites
  - [ ] HSTS enabled

- [ ] **Monitoring:**
  - [ ] Security event alerts configured
  - [ ] Rate limit monitoring
  - [ ] Failed authentication tracking
  - [ ] Audit log analysis

### API Security Best Practices

1. **Never trust client input** - Validate everything
2. **Use parameterized queries** - Prevent SQL injection
3. **Implement defense in depth** - Multiple security layers
4. **Fail securely** - Don't leak information in errors
5. **Log security events** - Maintain audit trail
6. **Regular security updates** - Keep dependencies current
7. **Security testing** - Regular penetration testing

## Testing Security

### Running Security Tests

```bash
# Run comprehensive security test suite
pytest app/tests/security/test_security_comprehensive.py -v

# Run specific security tests
pytest app/tests/security/test_security_comprehensive.py::TestRS256Authentication -v
pytest app/tests/security/test_security_comprehensive.py::TestInputValidation -v
pytest app/tests/security/test_security_comprehensive.py::TestRateLimiting -v
pytest app/tests/security/test_security_comprehensive.py::TestFieldEncryption -v
pytest app/tests/security/test_security_comprehensive.py::TestRBAC -v
pytest app/tests/security/test_security_comprehensive.py::TestAuditLogging -v
```

### Security Vulnerability Scanning

```bash
# Install security scanning tools
pip install bandit safety

# Run static analysis
bandit -r app/

# Check dependencies for vulnerabilities
safety check

# Run OWASP dependency check
# Requires OWASP Dependency Check installation
dependency-check --scan . --format HTML --out security-report.html
```

## Incident Response

### Security Incident Procedure

1. **Detection:** Monitor audit logs and alerts
2. **Containment:** Block affected IPs/users
3. **Investigation:** Analyze logs and patterns
4. **Remediation:** Apply fixes and patches
5. **Recovery:** Restore normal operations
6. **Post-Mortem:** Document and improve

### Emergency Contacts

- Security Team: security@example.com
- On-Call: +1-555-SECURITY
- Incident Response: incident@example.com

## Compliance

### Standards and Regulations

- **OWASP Top 10:** All vulnerabilities addressed
- **PCI DSS:** Encryption and access controls for payment data
- **GDPR:** Data protection and privacy controls
- **SOC 2:** Security controls and audit trails
- **ISO 27001:** Information security management

## Updates and Maintenance

### Security Maintenance Schedule

- **Daily:** Review security alerts and logs
- **Weekly:** Update dependencies with security patches
- **Monthly:** Security metrics review
- **Quarterly:** Security audit and penetration testing
- **Annually:** Complete security assessment

### Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2024-01-15 | Initial security implementation |
| 1.1.0 | 2024-01-15 | RS256 JWT, Input validation, Rate limiting |
| 1.2.0 | 2024-01-15 | Field encryption, RBAC, Audit logging |

## Contact

For security concerns or vulnerability reports, please contact:
- Email: security@example.com
- PGP Key: [Available on request]

**Responsible Disclosure:** We appreciate security researchers who report vulnerabilities responsibly. Please allow 90 days for patches before public disclosure.
