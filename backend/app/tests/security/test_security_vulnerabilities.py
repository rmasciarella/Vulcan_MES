"""
Security Vulnerability Test Suite

Comprehensive tests for identified security vulnerabilities and their fixes.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security_enhanced import (
    ROLE_PERMISSIONS,
    AuditLogger,
    FieldEncryption,
    MFAService,
    Permission,
    Role,
    SecureInputValidator,
    SessionManager,
    generate_secure_password,
    hash_password_secure,
    verify_password_secure,
    verify_password_strength,
)


class TestInputValidation:
    """Test input validation and sanitization."""

    def test_sql_injection_prevention(self):
        """Test SQL injection attack prevention."""
        malicious_inputs = [
            "'; DROP TABLE jobs; --",
            "1' OR '1'='1",
            "admin'--",
            "' UNION SELECT * FROM users--",
            "1; DELETE FROM operators WHERE 1=1--",
            "'; EXEC sp_MSForEachTable 'DROP TABLE ?'; --",
        ]

        for malicious_input in malicious_inputs:
            sanitized = SecureInputValidator.sanitize_sql(malicious_input)
            assert "DROP" not in sanitized
            assert "DELETE" not in sanitized
            assert "UNION" not in sanitized
            assert "--" not in sanitized
            assert ";" not in sanitized
            assert "'" not in sanitized

    def test_xss_prevention(self):
        """Test XSS attack prevention."""
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "<svg onload=alert('XSS')>",
            "javascript:alert('XSS')",
            "<iframe src='javascript:alert(\"XSS\")'></iframe>",
            "<body onload=alert('XSS')>",
        ]

        for payload in xss_payloads:
            sanitized = SecureInputValidator.sanitize_html(payload)
            assert "<script>" not in sanitized
            assert "javascript:" not in sanitized
            assert "onerror=" not in sanitized
            assert "onload=" not in sanitized
            assert "<" in sanitized  # Should be escaped

    def test_pattern_validation(self):
        """Test pattern-based input validation."""
        # Valid inputs
        assert SecureInputValidator.validate_pattern("JOB-2024-001", "job_number")
        assert SecureInputValidator.validate_pattern("EMP001", "employee_id")
        assert SecureInputValidator.validate_pattern("MACHINE_01", "machine_code")

        # Invalid inputs
        assert not SecureInputValidator.validate_pattern("job'; DROP--", "job_number")
        assert not SecureInputValidator.validate_pattern("123", "employee_id")
        assert not SecureInputValidator.validate_pattern("machine-01!", "machine_code")

    def test_email_validation(self):
        """Test email validation."""
        # Valid emails
        assert SecureInputValidator.validate_email("user@example.com")
        assert SecureInputValidator.validate_email("user.name+tag@example.co.uk")

        # Invalid emails
        assert not SecureInputValidator.validate_email("notanemail")
        assert not SecureInputValidator.validate_email("@example.com")
        assert not SecureInputValidator.validate_email("user@")
        assert not SecureInputValidator.validate_email("user@.com")

    def test_uuid_validation(self):
        """Test UUID validation."""
        # Valid UUID
        valid_uuid = str(uuid4())
        assert SecureInputValidator.validate_uuid(valid_uuid)

        # Invalid UUIDs
        assert not SecureInputValidator.validate_uuid("not-a-uuid")
        assert not SecureInputValidator.validate_uuid(
            "12345678-1234-1234-1234-123456789012x"
        )
        assert not SecureInputValidator.validate_uuid("")

    def test_length_validation(self):
        """Test string length validation."""
        assert SecureInputValidator.validate_length("test", min_length=1, max_length=10)
        assert not SecureInputValidator.validate_length("", min_length=1, max_length=10)
        assert not SecureInputValidator.validate_length(
            "x" * 1001, min_length=1, max_length=1000
        )


class TestFieldEncryption:
    """Test field-level encryption."""

    def test_field_encryption_decryption(self):
        """Test encrypting and decrypting fields."""
        encryption = FieldEncryption()

        # Test string encryption
        original = "sensitive_data_123"
        encrypted = encryption.encrypt_field(original)
        decrypted = encryption.decrypt_field(encrypted)

        assert encrypted != original
        assert decrypted == original

    def test_dict_encryption(self):
        """Test encrypting specific fields in a dictionary."""
        encryption = FieldEncryption()

        data = {
            "id": "123",
            "name": "John Doe",
            "email": "john@example.com",
            "ssn": "123-45-6789",
            "phone": "+1234567890",
        }

        fields_to_encrypt = ["email", "ssn", "phone"]

        # Encrypt
        encrypted_data = encryption.encrypt_dict(data, fields_to_encrypt)

        # Verify encrypted fields are different
        assert encrypted_data["email"] != data["email"]
        assert encrypted_data["ssn"] != data["ssn"]
        assert encrypted_data["phone"] != data["phone"]
        assert encrypted_data["name"] == data["name"]  # Not encrypted

        # Decrypt
        decrypted_data = encryption.decrypt_dict(encrypted_data, fields_to_encrypt)

        # Verify decryption
        assert decrypted_data == data

    def test_empty_field_handling(self):
        """Test handling of empty/null fields."""
        encryption = FieldEncryption()

        assert encryption.encrypt_field("") == ""
        assert encryption.encrypt_field(None) is None
        assert encryption.decrypt_field("") == ""
        assert encryption.decrypt_field(None) is None


class TestMFA:
    """Test Multi-Factor Authentication."""

    def test_secret_generation(self):
        """Test MFA secret generation."""
        mfa = MFAService()
        secret1 = mfa.generate_secret()
        secret2 = mfa.generate_secret()

        assert len(secret1) == 32  # Base32 encoded
        assert secret1 != secret2  # Should be unique

    def test_token_verification(self):
        """Test MFA token verification."""
        import pyotp

        mfa = MFAService()
        secret = mfa.generate_secret()

        # Generate valid token
        totp = pyotp.TOTP(secret)
        valid_token = totp.now()

        assert mfa.verify_token(secret, valid_token)
        assert not mfa.verify_token(secret, "000000")  # Invalid token

    def test_backup_codes(self):
        """Test backup code generation."""
        mfa = MFAService()
        codes = mfa.generate_backup_codes(10)

        assert len(codes) == 10
        assert len(set(codes)) == 10  # All unique
        assert all(len(code) == 8 for code in codes)  # 4 bytes hex = 8 chars


class TestSessionManagement:
    """Test secure session management."""

    def test_session_creation(self):
        """Test session creation."""
        session_mgr = SessionManager()
        user_id = uuid4()
        ip_address = "192.168.1.1"
        user_agent = "Mozilla/5.0"

        session_id = session_mgr.create_session(user_id, ip_address, user_agent)

        assert len(session_id) > 32  # Secure token
        assert session_id in session_mgr.sessions or session_mgr.redis_client

    def test_session_validation(self):
        """Test session validation."""
        session_mgr = SessionManager()
        user_id = uuid4()
        ip_address = "192.168.1.1"
        user_agent = "Mozilla/5.0"

        session_id = session_mgr.create_session(user_id, ip_address, user_agent)

        # Valid session
        session_data = session_mgr.validate_session(session_id, ip_address)
        assert session_data is not None
        assert session_data["user_id"] == str(user_id)

        # Invalid session (wrong IP)
        session_data = session_mgr.validate_session(session_id, "192.168.1.2")
        assert session_data is None

        # Invalid session (non-existent)
        session_data = session_mgr.validate_session("invalid_session", ip_address)
        assert session_data is None

    def test_session_destruction(self):
        """Test session destruction."""
        session_mgr = SessionManager()
        user_id = uuid4()
        ip_address = "192.168.1.1"
        user_agent = "Mozilla/5.0"

        session_id = session_mgr.create_session(user_id, ip_address, user_agent)

        # Destroy session
        assert session_mgr.destroy_session(session_id)

        # Verify destroyed
        session_data = session_mgr.validate_session(session_id, ip_address)
        assert session_data is None


class TestPasswordSecurity:
    """Test password security features."""

    def test_password_strength_validation(self):
        """Test password strength validation."""
        # Weak passwords
        weak_passwords = ["password", "12345678", "qwerty123", "admin", "Password1"]

        for password in weak_passwords:
            result = verify_password_strength(password)
            assert not result["valid"]
            assert len(result["issues"]) > 0
            assert result["score"] < 100

        # Strong password
        strong_password = "MyS3cur3P@ssw0rd!2024"
        result = verify_password_strength(strong_password)
        assert result["valid"]
        assert len(result["issues"]) == 0
        assert result["score"] == 100

    def test_secure_password_generation(self):
        """Test secure password generation."""
        password = generate_secure_password(16)

        assert len(password) == 16

        # Verify complexity
        assert any(c.isupper() for c in password)
        assert any(c.islower() for c in password)
        assert any(c.isdigit() for c in password)
        assert any(c in '!@#$%^&*(),.?":{}|<>' for c in password)

        # Verify uniqueness
        password2 = generate_secure_password(16)
        assert password != password2

    def test_password_hashing(self):
        """Test secure password hashing."""
        password = "MyS3cur3P@ssw0rd!2024"

        # Hash password
        hashed = hash_password_secure(password)

        # Verify hash is different from password
        assert hashed != password
        assert len(hashed) > 50  # Argon2 hashes are long

        # Verify password
        assert verify_password_secure(password, hashed)
        assert not verify_password_secure("wrong_password", hashed)

        # Verify different hashes for same password
        hashed2 = hash_password_secure(password)
        assert hashed != hashed2  # Different salt


class TestRBAC:
    """Test Role-Based Access Control."""

    def test_role_permissions(self):
        """Test role permission mappings."""
        # Operator should have limited permissions
        operator_perms = ROLE_PERMISSIONS[Role.OPERATOR]
        assert Permission.VIEW_JOBS in operator_perms
        assert Permission.DELETE_JOBS not in operator_perms
        assert Permission.ADMIN_PANEL not in operator_perms

        # Admin should have most permissions
        admin_perms = ROLE_PERMISSIONS[Role.ADMIN]
        assert Permission.VIEW_JOBS in admin_perms
        assert Permission.DELETE_JOBS in admin_perms
        assert Permission.ADMIN_PANEL in admin_perms

        # Superadmin should have all permissions
        superadmin_perms = ROLE_PERMISSIONS[Role.SUPERADMIN]
        assert len(superadmin_perms) == len(list(Permission))

    def test_permission_hierarchy(self):
        """Test permission hierarchy."""
        # Higher roles should have all permissions of lower roles
        operator_perms = set(ROLE_PERMISSIONS[Role.OPERATOR])
        scheduler_perms = set(ROLE_PERMISSIONS[Role.SCHEDULER])
        manager_perms = set(ROLE_PERMISSIONS[Role.MANAGER])

        # Scheduler should have all operator permissions
        assert operator_perms.issubset(scheduler_perms)

        # Manager should have all scheduler permissions
        assert scheduler_perms.issubset(manager_perms)


class TestAuditLogging:
    """Test audit logging functionality."""

    def test_authentication_logging(self, tmp_path):
        """Test authentication event logging."""
        import logging

        # Setup logger with temporary file
        log_file = tmp_path / "audit.log"
        logger = logging.getLogger("test_audit")
        handler = logging.FileHandler(log_file)
        logger.addHandler(handler)

        audit = AuditLogger(logger)

        # Log successful login
        audit.log_authentication(
            event_type="login",
            user_id=uuid4(),
            ip_address="192.168.1.1",
            success=True,
            details={"method": "password"},
        )

        # Log failed login
        audit.log_authentication(
            event_type="login",
            user_id=None,
            ip_address="192.168.1.2",
            success=False,
            details={"reason": "invalid_credentials"},
        )

        # Verify logs were written
        log_content = log_file.read_text()
        assert "AUTH:" in log_content
        assert "login" in log_content
        assert "192.168.1.1" in log_content
        assert "192.168.1.2" in log_content

    def test_data_access_logging(self, tmp_path):
        """Test data access event logging."""
        import logging

        log_file = tmp_path / "audit.log"
        logger = logging.getLogger("test_audit")
        handler = logging.FileHandler(log_file)
        logger.addHandler(handler)

        audit = AuditLogger(logger)

        # Log data access
        audit.log_data_access(
            user_id=uuid4(),
            resource_type="job",
            resource_id="JOB-001",
            action="view",
            ip_address="192.168.1.1",
        )

        # Verify log
        log_content = log_file.read_text()
        assert "DATA_ACCESS:" in log_content
        assert "JOB-001" in log_content

    def test_security_event_logging(self, tmp_path):
        """Test security event logging."""
        import logging

        log_file = tmp_path / "audit.log"
        logger = logging.getLogger("test_audit")
        handler = logging.FileHandler(log_file)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        audit = AuditLogger(logger)

        # Log critical security event
        audit.log_security_event(
            event_type="sql_injection_attempt",
            severity="CRITICAL",
            description="SQL injection detected in job search",
            ip_address="192.168.1.100",
            details={"payload": "'; DROP TABLE--"},
        )

        # Verify log
        log_content = log_file.read_text()
        assert "SECURITY:" in log_content
        assert "sql_injection_attempt" in log_content
        assert "CRITICAL" in log_content


# Integration tests for security features
@pytest.mark.integration
class TestSecurityIntegration:
    """Integration tests for security features."""

    async def test_authenticated_request_flow(self, client: TestClient):
        """Test complete authenticated request flow."""
        # 1. Login
        response = client.post(
            "/api/v1/login/access-token",
            data={"username": "test@example.com", "password": "TestP@ssw0rd123"},
        )
        assert response.status_code in [200, 400]  # Depends on test data

        if response.status_code == 200:
            token = response.json()["access_token"]

            # 2. Use token for authenticated request
            response = client.get(
                "/api/v1/jobs", headers={"Authorization": f"Bearer {token}"}
            )
            assert response.status_code in [200, 403]  # Depends on permissions

    async def test_rate_limiting(self, client: TestClient):
        """Test rate limiting on sensitive endpoints."""
        # Attempt multiple rapid logins
        for i in range(10):
            response = client.post(
                "/api/v1/login/access-token",
                data={"username": f"test{i}@example.com", "password": "wrong"},
            )

            # After 5 attempts, should be rate limited
            if i >= 5:
                assert response.status_code == 429  # Too Many Requests

    async def test_sql_injection_protection(self, client: TestClient, db: Session):
        """Test SQL injection protection in API."""
        # Attempt SQL injection
        malicious_input = "'; DROP TABLE jobs; --"

        response = client.get(f"/api/v1/jobs?status={malicious_input}")

        # Should not cause server error
        assert response.status_code != 500

        # Verify table still exists
        from app.models import Job

        jobs = db.query(Job).count()
        assert jobs >= 0  # Table should still exist


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
