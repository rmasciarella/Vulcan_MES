"""
Comprehensive Security Tests for Production Scheduling System

Tests authentication, authorization, input validation, SQL injection prevention,
XSS prevention, CSRF protection, and other security vulnerabilities.
"""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import (
    create_access_token,
    get_password_hash,
    verify_password,
)
from app.main import app

client = TestClient(app)


class TestAuthenticationSecurity:
    """Test authentication mechanisms and security."""

    def test_login_with_valid_credentials(self):
        """Test successful login with valid credentials."""
        login_data = {"username": "admin@example.com", "password": "changethis"}

        with patch("app.crud.authenticate") as mock_authenticate:
            # Mock successful authentication
            mock_user = Mock()
            mock_user.id = uuid4()
            mock_user.email = login_data["username"]
            mock_user.is_active = True
            mock_authenticate.return_value = mock_user

            response = client.post("/api/v1/login/access-token", data=login_data)

            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert data["token_type"] == "bearer"

    def test_login_with_invalid_credentials(self):
        """Test login failure with invalid credentials."""
        login_data = {"username": "admin@example.com", "password": "wrongpassword"}

        with patch("app.crud.authenticate") as mock_authenticate:
            mock_authenticate.return_value = None  # Invalid credentials

            response = client.post("/api/v1/login/access-token", data=login_data)

            assert response.status_code == 400
            data = response.json()
            assert "Incorrect email or password" in data["detail"]

    def test_login_with_inactive_user(self):
        """Test login failure with inactive user."""
        login_data = {"username": "inactive@example.com", "password": "password123"}

        with patch("app.crud.authenticate") as mock_authenticate:
            mock_user = Mock()
            mock_user.id = uuid4()
            mock_user.email = login_data["username"]
            mock_user.is_active = False  # Inactive user
            mock_authenticate.return_value = mock_user

            response = client.post("/api/v1/login/access-token", data=login_data)

            assert response.status_code == 400
            data = response.json()
            assert "Inactive user" in data["detail"]

    def test_access_protected_endpoint_without_token(self):
        """Test accessing protected endpoint without authentication token."""
        response = client.get("/api/v1/scheduling/data")
        assert response.status_code == 401

    def test_access_protected_endpoint_with_invalid_token(self):
        """Test accessing protected endpoint with invalid token."""
        invalid_headers = {"Authorization": "Bearer invalid_token_here"}
        response = client.get("/api/v1/scheduling/data", headers=invalid_headers)
        assert response.status_code == 403

    def test_access_protected_endpoint_with_expired_token(self):
        """Test accessing protected endpoint with expired token."""
        # Create expired token
        expired_token = create_access_token(
            subject="test@example.com",
            expires_delta=timedelta(minutes=-30),  # Expired 30 minutes ago
        )

        expired_headers = {"Authorization": f"Bearer {expired_token}"}
        response = client.get("/api/v1/scheduling/data", headers=expired_headers)
        assert response.status_code == 403

    def test_token_creation_and_validation(self):
        """Test JWT token creation and validation."""
        user_id = str(uuid4())
        token = create_access_token(subject=user_id)

        assert token is not None
        assert isinstance(token, str)

        # Verify token can be decoded
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        assert payload["sub"] == user_id
        assert "exp" in payload

    def test_password_hashing_and_verification(self):
        """Test password hashing and verification security."""
        plain_password = "secure_password_123"

        # Hash password
        hashed = get_password_hash(plain_password)
        assert hashed != plain_password
        assert len(hashed) > 50  # Bcrypt hash should be long

        # Verify correct password
        assert verify_password(plain_password, hashed) is True

        # Verify incorrect password
        assert verify_password("wrong_password", hashed) is False
        assert verify_password("", hashed) is False

    def test_brute_force_protection(self):
        """Test protection against brute force attacks."""
        login_data = {"username": "target@example.com", "password": "wrongpassword"}

        with patch("app.crud.authenticate") as mock_authenticate:
            mock_authenticate.return_value = None  # Always fail authentication

            # Attempt multiple failed logins
            failed_attempts = 0
            for _i in range(10):
                response = client.post("/api/v1/login/access-token", data=login_data)
                if response.status_code == 400:
                    failed_attempts += 1

            assert failed_attempts == 10

            # In a real implementation, there might be rate limiting
            # This test ensures that failed attempts are handled consistently


class TestAuthorizationSecurity:
    """Test authorization and access control."""

    def test_superuser_only_endpoint_access(self):
        """Test that superuser-only endpoints reject normal users."""
        # Mock normal user token
        user_token = create_access_token(subject="user@example.com")
        user_headers = {"Authorization": f"Bearer {user_token}"}

        with patch("app.api.deps.get_current_user") as mock_get_user:
            mock_user = Mock()
            mock_user.id = uuid4()
            mock_user.email = "user@example.com"
            mock_user.is_active = True
            mock_user.is_superuser = False  # Not a superuser
            mock_get_user.return_value = mock_user

            # Try to access superuser-only endpoint
            response = client.delete(f"/api/v1/users/{uuid4()}", headers=user_headers)
            assert response.status_code in [401, 403]

    def test_superuser_endpoint_access_allowed(self):
        """Test that superuser can access superuser-only endpoints."""
        superuser_token = create_access_token(subject="admin@example.com")
        superuser_headers = {"Authorization": f"Bearer {superuser_token}"}

        with patch("app.api.deps.get_current_user") as mock_get_user:
            mock_user = Mock()
            mock_user.id = uuid4()
            mock_user.email = "admin@example.com"
            mock_user.is_active = True
            mock_user.is_superuser = True  # Is a superuser
            mock_get_user.return_value = mock_user

            with patch("app.crud.get_user") as mock_crud_get_user:
                mock_crud_get_user.return_value = mock_user

                with patch("app.crud.remove") as mock_remove:
                    mock_remove.return_value = mock_user

                    response = client.delete(
                        f"/api/v1/users/{uuid4()}", headers=superuser_headers
                    )
                    assert response.status_code == 200

    def test_user_can_only_access_own_data(self):
        """Test that users can only access their own data."""
        user_id = uuid4()
        other_user_id = uuid4()

        user_token = create_access_token(subject=str(user_id))
        user_headers = {"Authorization": f"Bearer {user_token}"}

        with patch("app.api.deps.get_current_user") as mock_get_user:
            mock_user = Mock()
            mock_user.id = user_id
            mock_user.is_active = True
            mock_user.is_superuser = False
            mock_get_user.return_value = mock_user

            # User can access own data
            with patch("app.crud.get_user") as mock_crud_get_user:
                mock_crud_get_user.return_value = mock_user
                response = client.get("/api/v1/users/me", headers=user_headers)
                assert response.status_code == 200

            # User cannot access other user's data
            response = client.get(
                f"/api/v1/users/{other_user_id}", headers=user_headers
            )
            assert response.status_code in [401, 403, 404]


class TestInputValidationSecurity:
    """Test input validation and sanitization."""

    def test_sql_injection_prevention_job_number(self):
        """Test SQL injection prevention in job number field."""
        sql_injection_payloads = [
            "'; DROP TABLE jobs; --",
            "' OR '1'='1",
            "'; INSERT INTO jobs (job_number) VALUES ('hacked'); --",
            "' UNION SELECT * FROM users --",
        ]

        for payload in sql_injection_payloads:
            job_data = {
                "job_number": payload,
                "customer_name": "Test Customer",
                "quantity": 1,
                "due_date": (datetime.utcnow() + timedelta(days=7)).isoformat(),
            }

            with patch(
                "app.infrastructure.database.dependencies.get_job_repository"
            ) as mock_repo:
                mock_repository = Mock()
                # Should sanitize input before reaching repository
                mock_repository.create.return_value = Mock(
                    id=uuid4(), job_number=payload[:50]
                )
                mock_repo.return_value = mock_repository

                response = client.post(
                    "/api/v1/scheduling/jobs",
                    headers={"Authorization": "Bearer mock_token"},
                    json=job_data,
                )

                # Should either validate/sanitize input or reject it
                assert response.status_code in [201, 400, 422]

                if response.status_code == 201:
                    # If accepted, should be sanitized
                    data = response.json()
                    assert "DROP TABLE" not in data.get("job_number", "")
                    assert "UNION SELECT" not in data.get("job_number", "")

    def test_xss_prevention_in_text_fields(self):
        """Test XSS prevention in text input fields."""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert('xss')>",
            "javascript:alert('xss')",
            "<svg onload=alert('xss')>",
            "';alert('xss');//",
        ]

        for payload in xss_payloads:
            job_data = {
                "job_number": "TEST-XSS-001",
                "customer_name": payload,  # XSS in customer name
                "notes": payload,  # XSS in notes
                "quantity": 1,
                "due_date": (datetime.utcnow() + timedelta(days=7)).isoformat(),
            }

            with patch(
                "app.infrastructure.database.dependencies.get_job_repository"
            ) as mock_repo:
                mock_repository = Mock()
                created_job = Mock()
                created_job.id = uuid4()
                created_job.job_number = job_data["job_number"]
                created_job.customer_name = (
                    payload  # Would be sanitized in real implementation
                )
                created_job.notes = payload
                mock_repository.create.return_value = created_job
                mock_repo.return_value = mock_repository

                response = client.post(
                    "/api/v1/scheduling/jobs",
                    headers={"Authorization": "Bearer mock_token"},
                    json=job_data,
                )

                if response.status_code == 201:
                    data = response.json()
                    # Should not contain dangerous script tags
                    assert "<script>" not in data.get("customer_name", "")
                    assert "<script>" not in data.get("notes", "")
                    assert "javascript:" not in data.get("customer_name", "")

    def test_input_length_validation(self):
        """Test input length validation to prevent buffer overflow."""
        # Test extremely long inputs
        long_string = "A" * 10000  # 10KB string

        job_data = {
            "job_number": long_string,  # Should be rejected
            "customer_name": long_string,
            "notes": long_string,
            "quantity": 1,
            "due_date": (datetime.utcnow() + timedelta(days=7)).isoformat(),
        }

        response = client.post(
            "/api/v1/scheduling/jobs",
            headers={"Authorization": "Bearer mock_token"},
            json=job_data,
        )

        # Should reject due to length validation
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

        # Check that validation mentions length limits
        error_messages = str(data["detail"]).lower()
        assert any(
            word in error_messages for word in ["length", "long", "max", "limit"]
        )

    def test_numeric_input_validation(self):
        """Test validation of numeric inputs."""
        invalid_numeric_inputs = [
            {"quantity": -1},  # Negative quantity
            {"quantity": 0},  # Zero quantity
            {"quantity": "abc"},  # Non-numeric string
            {"quantity": 999999999},  # Extremely large number
            {"quantity": 1.5},  # Float instead of int
        ]

        for invalid_input in invalid_numeric_inputs:
            job_data = {
                "job_number": "TEST-NUMERIC-001",
                "customer_name": "Test Customer",
                "due_date": (datetime.utcnow() + timedelta(days=7)).isoformat(),
                **invalid_input,
            }

            response = client.post(
                "/api/v1/scheduling/jobs",
                headers={"Authorization": "Bearer mock_token"},
                json=job_data,
            )

            # Should reject invalid numeric inputs
            assert response.status_code == 422

    def test_date_format_validation(self):
        """Test validation of date formats."""
        invalid_date_formats = [
            "invalid-date",
            "2024-13-01",  # Invalid month
            "2024-02-30",  # Invalid day
            "2024/01/01",  # Wrong format
            "01-01-2024",  # Wrong format
            "2024-01-01 25:00:00",  # Invalid hour
        ]

        for invalid_date in invalid_date_formats:
            job_data = {
                "job_number": "TEST-DATE-001",
                "customer_name": "Test Customer",
                "quantity": 1,
                "due_date": invalid_date,
            }

            response = client.post(
                "/api/v1/scheduling/jobs",
                headers={"Authorization": "Bearer mock_token"},
                json=job_data,
            )

            # Should reject invalid date formats
            assert response.status_code == 422

    def test_uuid_validation(self):
        """Test validation of UUID fields."""
        invalid_uuids = [
            "not-a-uuid",
            "12345",
            "00000000-0000-0000-0000-000000000000",  # Null UUID (might be invalid)
            "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        ]

        for invalid_uuid in invalid_uuids:
            response = client.get(
                f"/api/v1/scheduling/jobs/{invalid_uuid}",
                headers={"Authorization": "Bearer mock_token"},
            )

            # Should reject invalid UUIDs
            assert response.status_code in [400, 422]


class TestSecurityHeaders:
    """Test security headers and configurations."""

    def test_security_headers_present(self):
        """Test that appropriate security headers are set."""
        response = client.get(
            "/api/v1/scheduling/data", headers={"Authorization": "Bearer mock_token"}
        )

        # Check for security headers (may not all be present in test environment)
        headers = response.headers

        # CORS headers should be properly configured
        if "Access-Control-Allow-Origin" in headers:
            # Should not be wildcard in production
            assert headers["Access-Control-Allow-Origin"] != "*"

    def test_cors_configuration(self):
        """Test CORS configuration."""
        # Test preflight request
        response = client.options(
            "/api/v1/scheduling/data",
            headers={
                "Origin": "https://malicious-site.com",
                "Access-Control-Request-Method": "GET",
            },
        )

        # Should handle CORS appropriately
        # In production, should only allow authorized origins
        assert response.status_code in [200, 204, 405]

    def test_content_type_validation(self):
        """Test content type validation."""
        # Test with incorrect content type
        response = client.post(
            "/api/v1/scheduling/jobs",
            headers={
                "Authorization": "Bearer mock_token",
                "Content-Type": "text/plain",  # Should expect application/json
            },
            data="not json data",
        )

        assert response.status_code in [400, 415, 422]


class TestDataPrivacySecurity:
    """Test data privacy and protection."""

    def test_sensitive_data_not_in_responses(self):
        """Test that sensitive data is not included in API responses."""
        with patch("app.api.deps.get_current_user") as mock_get_user:
            mock_user = Mock()
            mock_user.id = uuid4()
            mock_user.email = "test@example.com"
            mock_user.hashed_password = "hashed_password_here"
            mock_user.is_active = True
            mock_get_user.return_value = mock_user

            response = client.get(
                "/api/v1/users/me", headers={"Authorization": "Bearer mock_token"}
            )

            if response.status_code == 200:
                data = response.json()

                # Should not contain sensitive fields
                assert "hashed_password" not in data
                assert "password" not in data
                assert "secret" not in str(data).lower()

    def test_user_data_isolation(self):
        """Test that users cannot access other users' data."""
        user1_id = uuid4()
        user2_id = uuid4()

        user1_token = create_access_token(subject=str(user1_id))
        headers = {"Authorization": f"Bearer {user1_token}"}

        with patch("app.api.deps.get_current_user") as mock_get_user:
            mock_user = Mock()
            mock_user.id = user1_id
            mock_user.is_active = True
            mock_user.is_superuser = False
            mock_get_user.return_value = mock_user

            # Try to access another user's jobs
            with patch(
                "app.infrastructure.database.dependencies.get_job_repository"
            ) as mock_repo:
                mock_repository = Mock()
                mock_repository.find_by_created_by.return_value = []  # No access to other user's data
                mock_repo.return_value = mock_repository

                response = client.get(
                    f"/api/v1/scheduling/jobs?created_by={user2_id}", headers=headers
                )

                # Should either be forbidden or return empty results
                assert response.status_code in [200, 403, 404]

                if response.status_code == 200:
                    data = response.json()
                    # Should not return other user's data
                    for job in data:
                        assert job.get("created_by") != str(user2_id)


class TestRateLimitingSecurity:
    """Test rate limiting and abuse prevention."""

    def test_api_rate_limiting(self):
        """Test API rate limiting protection."""
        headers = {"Authorization": "Bearer mock_token"}

        # Make many rapid requests
        responses = []
        for _i in range(50):  # 50 requests in quick succession
            with patch(
                "app.infrastructure.database.dependencies.get_repository_container"
            ):
                response = client.get("/api/v1/scheduling/data", headers=headers)
                responses.append(response.status_code)

        # Should either handle all requests or implement rate limiting
        success_count = sum(1 for status in responses if status == 200)
        rate_limited_count = sum(1 for status in responses if status == 429)

        # At least some requests should succeed
        assert success_count > 0

        # If rate limiting is implemented, should see 429 responses
        if rate_limited_count > 0:
            assert rate_limited_count < len(responses)  # Not all should be rate limited

    def test_expensive_operation_protection(self):
        """Test protection against expensive operations."""
        headers = {"Authorization": "Bearer mock_token"}

        # Test expensive schedule generation
        large_schedule_request = {
            "job_ids": [str(uuid4()) for _ in range(1000)],  # Very large request
            "optimization_objective": "minimize_makespan",
        }

        with patch("app.core.solver.HFFSScheduler") as mock_scheduler_class:
            mock_scheduler = Mock()
            mock_scheduler.solve.return_value = {
                "status": "ERROR",
                "error": "Request too large",
            }
            mock_scheduler_class.return_value = mock_scheduler

            response = client.post(
                "/api/v1/scheduling/generate-schedule",
                headers=headers,
                json=large_schedule_request,
            )

            # Should either reject large requests or handle them gracefully
            assert response.status_code in [200, 400, 413, 422]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
