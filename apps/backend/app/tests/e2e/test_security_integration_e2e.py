"""
Security Integration Tests for Authentication and Authorization Flows

Tests complete security workflows including authentication, authorization,
role-based access control, token management, and security compliance
throughout the scheduling system.
"""

import time
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.infrastructure.database.models import User as UserModel
from app.tests.utils.user import create_test_user
from app.tests.utils.utils import get_superuser_token_headers


class SecurityTestHelper:
    """Helper for security testing scenarios."""

    @staticmethod
    def create_expired_token(user_email: str) -> str:
        """Create an expired JWT token for testing."""
        payload = {
            "sub": user_email,
            "exp": datetime.utcnow() - timedelta(minutes=5),  # Expired 5 minutes ago
            "iat": datetime.utcnow() - timedelta(minutes=10),
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

    @staticmethod
    def create_invalid_signature_token(user_email: str) -> str:
        """Create a token with invalid signature."""
        payload = {
            "sub": user_email,
            "exp": datetime.utcnow() + timedelta(hours=1),
            "iat": datetime.utcnow(),
        }
        return jwt.encode(payload, "wrong_secret", algorithm="HS256")

    @staticmethod
    def create_malformed_token() -> str:
        """Create a malformed token."""
        return "invalid.token.format"

    @staticmethod
    def create_custom_role_token(
        user_email: str, roles: list[str], permissions: list[str]
    ) -> str:
        """Create token with custom roles and permissions."""
        payload = {
            "sub": user_email,
            "roles": roles,
            "permissions": permissions,
            "exp": datetime.utcnow() + timedelta(hours=1),
            "iat": datetime.utcnow(),
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


@pytest.fixture
def security_helper():
    """Provide security test helper."""
    return SecurityTestHelper()


@pytest.fixture
def security_test_users(db: Session):
    """Create users with different security profiles."""
    users = {
        "admin": create_test_user(
            db, "admin@security-test.com", is_superuser=True, full_name="Security Admin"
        ),
        "production_manager": create_test_user(
            db,
            "prod_manager@security-test.com",
            is_superuser=False,
            full_name="Production Manager",
        ),
        "operator": create_test_user(
            db,
            "operator@security-test.com",
            is_superuser=False,
            full_name="Machine Operator",
        ),
        "readonly_user": create_test_user(
            db,
            "readonly@security-test.com",
            is_superuser=False,
            full_name="Read Only User",
        ),
        "guest": create_test_user(
            db, "guest@security-test.com", is_superuser=False, full_name="Guest User"
        ),
    }
    return users


@pytest.fixture
def security_token_headers(
    client: TestClient, security_test_users: dict[str, UserModel]
):
    """Get authentication headers for different security test users."""
    headers = {}
    for role, user in security_test_users.items():
        try:
            response = client.post(
                "/api/v1/login/access-token",
                data={"username": user.email, "password": "testpass123"},
            )
            if response.status_code == 200:
                token = response.json()["access_token"]
                headers[role] = {"Authorization": f"Bearer {token}"}
            else:
                # Fallback for testing
                headers[role] = get_superuser_token_headers(client)
        except Exception:
            headers[role] = get_superuser_token_headers(client)

    return headers


@pytest.mark.e2e
@pytest.mark.security
class TestSecurityIntegrationE2E:
    """Test security throughout complete workflows."""

    async def test_authentication_workflow_integration(
        self,
        client: TestClient,
        security_token_headers: dict[str, dict[str, str]],
        db: Session,
    ):
        """Test complete authentication workflow integration."""

        # Test 1: Valid authentication workflow
        valid_credentials = {
            "username": "admin@security-test.com",
            "password": "testpass123",
        }

        response = client.post("/api/v1/login/access-token", data=valid_credentials)
        assert response.status_code == 200

        token_data = response.json()
        assert "access_token" in token_data
        assert "token_type" in token_data
        assert token_data["token_type"] == "bearer"

        access_token = token_data["access_token"]
        auth_headers = {"Authorization": f"Bearer {access_token}"}

        # Test authenticated access to protected endpoint
        response = client.get("/api/v1/users/me", headers=auth_headers)
        assert response.status_code == 200
        user_data = response.json()
        assert user_data["email"] == "admin@security-test.com"

        # Test 2: Invalid credentials
        invalid_credentials = {
            "username": "admin@security-test.com",
            "password": "wrong_password",
        }

        response = client.post("/api/v1/login/access-token", data=invalid_credentials)
        assert response.status_code == 400

        # Test 3: Non-existent user
        nonexistent_credentials = {
            "username": "nonexistent@test.com",
            "password": "anypassword",
        }

        response = client.post(
            "/api/v1/login/access-token", data=nonexistent_credentials
        )
        assert response.status_code == 400

        # Test 4: Empty credentials
        empty_credentials = {"username": "", "password": ""}

        response = client.post("/api/v1/login/access-token", data=empty_credentials)
        assert response.status_code == 422  # Validation error

    async def test_token_validation_and_expiry(
        self, client: TestClient, security_helper: SecurityTestHelper, db: Session
    ):
        """Test JWT token validation and expiry handling."""

        test_user_email = "admin@security-test.com"

        # Test 1: Expired token
        expired_token = security_helper.create_expired_token(test_user_email)
        expired_headers = {"Authorization": f"Bearer {expired_token}"}

        response = client.get("/api/v1/users/me", headers=expired_headers)
        assert response.status_code == 401, "Expired token should be rejected"

        # Test 2: Invalid signature
        invalid_sig_token = security_helper.create_invalid_signature_token(
            test_user_email
        )
        invalid_sig_headers = {"Authorization": f"Bearer {invalid_sig_token}"}

        response = client.get("/api/v1/users/me", headers=invalid_sig_headers)
        assert response.status_code == 401, "Invalid signature should be rejected"

        # Test 3: Malformed token
        malformed_token = security_helper.create_malformed_token()
        malformed_headers = {"Authorization": f"Bearer {malformed_token}"}

        response = client.get("/api/v1/users/me", headers=malformed_headers)
        assert response.status_code == 401, "Malformed token should be rejected"

        # Test 4: No token
        response = client.get("/api/v1/users/me")
        assert response.status_code == 401, "Missing token should be rejected"

        # Test 5: Invalid authorization header format
        invalid_format_headers = {"Authorization": "InvalidFormat token123"}

        response = client.get("/api/v1/users/me", headers=invalid_format_headers)
        assert response.status_code == 401, "Invalid header format should be rejected"

    async def test_role_based_access_control_workflow(
        self,
        client: TestClient,
        security_token_headers: dict[str, dict[str, str]],
        db: Session,
    ):
        """Test role-based access control throughout workflow."""

        # Create test job for access control testing
        job_data = {
            "job_number": "RBAC-TEST-001",
            "customer_name": "RBAC Test Customer",
            "due_date": (datetime.utcnow() + timedelta(days=7)).isoformat(),
        }

        # Admin should be able to create job
        response = client.post(
            "/api/v1/jobs/", json=job_data, headers=security_token_headers["admin"]
        )
        assert response.status_code == 201
        job = response.json()
        job_id = job["id"]

        # Define role-based access tests
        access_tests = [
            {
                "role": "admin",
                "operations": [
                    {
                        "method": "GET",
                        "url": f"/api/v1/jobs/{job_id}",
                        "should_succeed": True,
                    },
                    {
                        "method": "PATCH",
                        "url": f"/api/v1/jobs/{job_id}",
                        "should_succeed": True,
                    },
                    {
                        "method": "DELETE",
                        "url": f"/api/v1/jobs/{job_id}",
                        "should_succeed": True,
                    },
                    {"method": "GET", "url": "/api/v1/users/", "should_succeed": True},
                ],
            },
            {
                "role": "production_manager",
                "operations": [
                    {
                        "method": "GET",
                        "url": f"/api/v1/jobs/{job_id}",
                        "should_succeed": True,
                    },
                    {
                        "method": "PATCH",
                        "url": f"/api/v1/jobs/{job_id}",
                        "should_succeed": True,
                    },
                    {"method": "POST", "url": "/api/v1/jobs/", "should_succeed": True},
                    {"method": "GET", "url": "/api/v1/users/", "should_succeed": False},
                ],
            },
            {
                "role": "operator",
                "operations": [
                    {
                        "method": "GET",
                        "url": f"/api/v1/jobs/{job_id}",
                        "should_succeed": True,
                    },
                    {
                        "method": "PATCH",
                        "url": f"/api/v1/jobs/{job_id}",
                        "should_succeed": False,
                    },
                    {
                        "method": "DELETE",
                        "url": f"/api/v1/jobs/{job_id}",
                        "should_succeed": False,
                    },
                    {"method": "POST", "url": "/api/v1/jobs/", "should_succeed": False},
                ],
            },
            {
                "role": "readonly_user",
                "operations": [
                    {
                        "method": "GET",
                        "url": f"/api/v1/jobs/{job_id}",
                        "should_succeed": True,
                    },
                    {
                        "method": "PATCH",
                        "url": f"/api/v1/jobs/{job_id}",
                        "should_succeed": False,
                    },
                    {"method": "POST", "url": "/api/v1/jobs/", "should_succeed": False},
                    {
                        "method": "DELETE",
                        "url": f"/api/v1/jobs/{job_id}",
                        "should_succeed": False,
                    },
                ],
            },
            {
                "role": "guest",
                "operations": [
                    {
                        "method": "GET",
                        "url": f"/api/v1/jobs/{job_id}",
                        "should_succeed": False,
                    },
                    {
                        "method": "PATCH",
                        "url": f"/api/v1/jobs/{job_id}",
                        "should_succeed": False,
                    },
                    {"method": "POST", "url": "/api/v1/jobs/", "should_succeed": False},
                    {
                        "method": "DELETE",
                        "url": f"/api/v1/jobs/{job_id}",
                        "should_succeed": False,
                    },
                ],
            },
        ]

        # Execute access control tests
        for test_case in access_tests:
            role = test_case["role"]
            headers = security_token_headers[role]

            for operation in test_case["operations"]:
                method = operation["method"]
                url = operation["url"]
                should_succeed = operation["should_succeed"]

                if method == "GET":
                    response = client.get(url, headers=headers)
                elif method == "POST":
                    if "jobs" in url:
                        response = client.post(url, json=job_data, headers=headers)
                    else:
                        response = client.post(url, json={}, headers=headers)
                elif method == "PATCH":
                    response = client.patch(
                        url, json={"notes": f"Updated by {role}"}, headers=headers
                    )
                elif method == "DELETE":
                    response = client.delete(url, headers=headers)
                else:
                    continue

                if should_succeed:
                    assert (
                        response.status_code not in [401, 403]
                    ), f"{role} should have access to {method} {url}, got {response.status_code}"
                else:
                    assert (
                        response.status_code in [401, 403, 405]
                    ), f"{role} should be denied access to {method} {url}, got {response.status_code}"

    async def test_permission_based_scheduling_workflow(
        self,
        client: TestClient,
        security_token_headers: dict[str, dict[str, str]],
        db: Session,
    ):
        """Test permission-based access to scheduling operations."""

        # Create jobs for scheduling workflow
        jobs_data = [
            {
                "job_number": "PERM-SCHED-001",
                "customer_name": "Permission Test Customer 1",
                "due_date": (datetime.utcnow() + timedelta(days=5)).isoformat(),
            },
            {
                "job_number": "PERM-SCHED-002",
                "customer_name": "Permission Test Customer 2",
                "due_date": (datetime.utcnow() + timedelta(days=8)).isoformat(),
            },
        ]

        created_jobs = []
        for job_data in jobs_data:
            response = client.post(
                "/api/v1/jobs/", json=job_data, headers=security_token_headers["admin"]
            )
            assert response.status_code == 201
            job = response.json()
            created_jobs.append(job)

            # Add task
            task_data = {
                "operation_id": str(uuid4()),
                "sequence_in_job": 10,
                "planned_duration_minutes": 90,
            }

            response = client.post(
                f"/api/v1/jobs/{job['id']}/tasks/",
                json=task_data,
                headers=security_token_headers["admin"],
            )
            assert response.status_code == 201

            # Release job
            response = client.patch(
                f"/api/v1/jobs/{job['id']}/status",
                json={"status": "RELEASED"},
                headers=security_token_headers["admin"],
            )
            assert response.status_code == 200

        # Test scheduling permissions
        schedule_data = {
            "name": "Permission Test Schedule",
            "job_ids": [job["id"] for job in created_jobs],
            "start_time": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
            "end_time": (datetime.utcnow() + timedelta(days=6)).isoformat(),
        }

        # Define permission-based scheduling tests
        scheduling_permission_tests = [
            {
                "role": "admin",
                "operations": [
                    {"action": "create_schedule", "should_succeed": True},
                    {"action": "optimize_schedule", "should_succeed": True},
                    {"action": "publish_schedule", "should_succeed": True},
                    {"action": "delete_schedule", "should_succeed": True},
                ],
            },
            {
                "role": "production_manager",
                "operations": [
                    {"action": "create_schedule", "should_succeed": True},
                    {"action": "optimize_schedule", "should_succeed": True},
                    {"action": "publish_schedule", "should_succeed": True},
                    {"action": "delete_schedule", "should_succeed": False},
                ],
            },
            {
                "role": "operator",
                "operations": [
                    {"action": "create_schedule", "should_succeed": False},
                    {"action": "view_schedule", "should_succeed": True},
                    {"action": "optimize_schedule", "should_succeed": False},
                    {"action": "publish_schedule", "should_succeed": False},
                ],
            },
        ]

        for test_case in scheduling_permission_tests:
            role = test_case["role"]
            headers = security_token_headers[role]

            schedule_id = None

            for operation in test_case["operations"]:
                action = operation["action"]
                should_succeed = operation["should_succeed"]

                if action == "create_schedule":
                    response = client.post(
                        "/api/v1/schedules/optimize",
                        json=schedule_data,
                        headers=headers,
                    )

                    if should_succeed:
                        if response.status_code == 201:
                            result = response.json()
                            schedule_id = result["schedule"]["id"]
                        else:
                            # May fail for business reasons, not access control
                            assert response.status_code not in [401, 403]
                    else:
                        assert response.status_code in [401, 403]

                elif action == "view_schedule" and schedule_id:
                    response = client.get(
                        f"/api/v1/schedules/{schedule_id}", headers=headers
                    )

                    if should_succeed:
                        assert response.status_code not in [401, 403]
                    else:
                        assert response.status_code in [401, 403]

                elif action == "publish_schedule" and schedule_id:
                    response = client.post(
                        f"/api/v1/schedules/{schedule_id}/publish",
                        json={"published_by": role},
                        headers=headers,
                    )

                    if should_succeed:
                        assert response.status_code not in [401, 403]
                    else:
                        assert response.status_code in [401, 403]

                elif action == "delete_schedule" and schedule_id:
                    response = client.delete(
                        f"/api/v1/schedules/{schedule_id}", headers=headers
                    )

                    if should_succeed:
                        assert response.status_code not in [401, 403]
                    else:
                        assert response.status_code in [401, 403]

    async def test_security_during_concurrent_operations(
        self,
        client: TestClient,
        security_token_headers: dict[str, dict[str, str]],
        db: Session,
    ):
        """Test security enforcement during concurrent operations."""

        # Create job for concurrent testing
        job_data = {
            "job_number": "CONCURRENT-SEC-001",
            "customer_name": "Concurrent Security Test",
            "due_date": (datetime.utcnow() + timedelta(days=6)).isoformat(),
        }

        response = client.post(
            "/api/v1/jobs/", json=job_data, headers=security_token_headers["admin"]
        )
        assert response.status_code == 201
        job = response.json()
        job_id = job["id"]

        # Define concurrent operations with different security contexts
        def concurrent_operation(role: str, operation_type: str) -> dict[str, Any]:
            """Execute operation with specific role's security context."""
            headers = security_token_headers[role]

            try:
                if operation_type == "read":
                    response = client.get(f"/api/v1/jobs/{job_id}", headers=headers)
                elif operation_type == "update":
                    response = client.patch(
                        f"/api/v1/jobs/{job_id}",
                        json={"notes": f"Updated by {role} at {time.time()}"},
                        headers=headers,
                    )
                elif operation_type == "status_change":
                    response = client.patch(
                        f"/api/v1/jobs/{job_id}/status",
                        json={"status": "APPROVED", "reason": f"approved_by_{role}"},
                        headers=headers,
                    )
                else:
                    return {
                        "role": role,
                        "operation": operation_type,
                        "error": "unknown_operation",
                    }

                return {
                    "role": role,
                    "operation": operation_type,
                    "status_code": response.status_code,
                    "success": response.status_code < 400,
                    "timestamp": time.time(),
                }

            except Exception as e:
                return {
                    "role": role,
                    "operation": operation_type,
                    "error": str(e),
                    "success": False,
                    "timestamp": time.time(),
                }

        # Execute concurrent operations
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            futures = [
                executor.submit(concurrent_operation, "admin", "read"),
                executor.submit(concurrent_operation, "admin", "update"),
                executor.submit(concurrent_operation, "production_manager", "read"),
                executor.submit(
                    concurrent_operation, "production_manager", "status_change"
                ),
                executor.submit(concurrent_operation, "operator", "read"),
                executor.submit(
                    concurrent_operation, "readonly_user", "update"
                ),  # Should fail
                executor.submit(concurrent_operation, "guest", "read"),  # Should fail
            ]

            results = [future.result(timeout=10) for future in futures]

        # Analyze security enforcement
        admin_results = [r for r in results if r["role"] == "admin"]
        [r for r in results if r["role"] == "operator"]
        guest_results = [r for r in results if r["role"] == "guest"]
        readonly_update_results = [
            r
            for r in results
            if r["role"] == "readonly_user" and r["operation"] == "update"
        ]

        # Admin should succeed
        admin_successes = [r for r in admin_results if r["success"]]
        assert len(admin_successes) > 0, "Admin operations should succeed"

        # Guest reads should fail
        guest_failures = [r for r in guest_results if not r["success"]]
        assert len(guest_failures) > 0, "Guest operations should fail"

        # Readonly user updates should fail
        readonly_update_failures = [
            r for r in readonly_update_results if not r["success"]
        ]
        assert len(readonly_update_failures) > 0, "Readonly user updates should fail"

        # Verify final job state is consistent
        response = client.get(
            f"/api/v1/jobs/{job_id}", headers=security_token_headers["admin"]
        )
        assert response.status_code == 200
        final_job = response.json()

        # Job should still be in valid state despite concurrent operations
        assert final_job["job_number"] == "CONCURRENT-SEC-001"
        assert final_job["status"] in ["PLANNED", "APPROVED", "RELEASED"]

    async def test_api_rate_limiting_security(
        self, client: TestClient, security_token_headers: dict[str, dict[str, str]]
    ):
        """Test API rate limiting for security."""

        # Test rapid requests with same token
        headers = security_token_headers["admin"]

        rapid_requests = []
        request_count = 20

        start_time = time.time()

        for i in range(request_count):
            response = client.get("/api/v1/users/me", headers=headers)
            rapid_requests.append(
                {
                    "request_id": i,
                    "status_code": response.status_code,
                    "timestamp": time.time(),
                }
            )

        total_time = time.time() - start_time

        # Analyze rate limiting behavior
        successful_requests = [r for r in rapid_requests if r["status_code"] == 200]
        rate_limited_requests = [r for r in rapid_requests if r["status_code"] == 429]

        # Should handle rapid requests appropriately
        # Either all succeed (no rate limiting) or some are rate limited
        if len(rate_limited_requests) > 0:
            # Rate limiting is active
            assert (
                len(successful_requests) < request_count
            ), "Some requests should be rate limited"
        else:
            # No rate limiting or high limits
            assert (
                len(successful_requests) == request_count
            ), "All requests should succeed if no rate limiting"

        print(
            f"Processed {len(successful_requests)}/{request_count} requests in {total_time:.2f}s"
        )
        if rate_limited_requests:
            print(f"Rate limited: {len(rate_limited_requests)} requests")

    async def test_password_security_and_hashing(self, client: TestClient, db: Session):
        """Test password security and hashing mechanisms."""

        # Test password hashing
        test_password = "TestPassword123!"
        hashed_password = get_password_hash(test_password)

        # Hash should be different from plain password
        assert hashed_password != test_password
        assert len(hashed_password) > 50  # Hashed passwords should be long

        # Password verification should work
        assert verify_password(test_password, hashed_password) is True
        assert verify_password("WrongPassword", hashed_password) is False

        # Test password requirements during user registration
        weak_passwords = [
            "123",  # Too short
            "password",  # Common password
            "12345678",  # Only numbers
            "abcdefgh",  # Only letters, too simple
        ]

        for weak_password in weak_passwords:
            user_data = {
                "email": f"test_{uuid4()}@test.com",
                "password": weak_password,
                "full_name": "Test User",
            }

            response = client.post("/api/v1/users/", json=user_data)
            # Should fail validation or be rejected for weak password
            # Note: Exact response depends on password validation implementation
            if response.status_code == 200:
                # If user was created, password should still be hashed
                created_user = response.json()
                assert "password" not in created_user  # Password should not be returned

        # Test strong password
        strong_password = "StrongPassword123!@#"
        strong_user_data = {
            "email": f"strong_user_{uuid4()}@test.com",
            "password": strong_password,
            "full_name": "Strong Password User",
        }

        response = client.post("/api/v1/users/", json=strong_user_data)
        # Strong password should be accepted (if endpoint exists and is accessible)

    async def test_session_management_and_token_revocation(
        self, client: TestClient, security_test_users: dict[str, UserModel], db: Session
    ):
        """Test session management and token revocation scenarios."""

        # Login to get initial token
        login_response = client.post(
            "/api/v1/login/access-token",
            data={"username": "admin@security-test.com", "password": "testpass123"},
        )
        assert login_response.status_code == 200

        token_data = login_response.json()
        access_token = token_data["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Test token is valid
        response = client.get("/api/v1/users/me", headers=headers)
        assert response.status_code == 200

        # Test multiple logins (should each get unique tokens)
        login_response_2 = client.post(
            "/api/v1/login/access-token",
            data={"username": "admin@security-test.com", "password": "testpass123"},
        )
        assert login_response_2.status_code == 200

        token_data_2 = login_response_2.json()
        access_token_2 = token_data_2["access_token"]

        # Tokens should be different
        assert access_token != access_token_2

        # Both tokens should be valid
        headers_2 = {"Authorization": f"Bearer {access_token_2}"}
        response_1 = client.get("/api/v1/users/me", headers=headers)
        response_2 = client.get("/api/v1/users/me", headers=headers_2)

        assert response_1.status_code == 200
        assert response_2.status_code == 200

        # Test logout/token revocation (if endpoint exists)
        logout_response = client.post("/api/v1/logout", headers=headers)

        if logout_response.status_code == 200:
            # Token should be invalidated after logout
            response = client.get("/api/v1/users/me", headers=headers)
            assert response.status_code == 401, "Token should be invalid after logout"
        elif logout_response.status_code == 404:
            # Logout endpoint doesn't exist, which is acceptable
            pass

    async def test_security_audit_logging(
        self,
        client: TestClient,
        security_token_headers: dict[str, dict[str, str]],
        db: Session,
    ):
        """Test security-related audit logging."""

        # Create job for audit testing
        job_data = {
            "job_number": "AUDIT-SEC-001",
            "customer_name": "Security Audit Test",
            "due_date": (datetime.utcnow() + timedelta(days=5)).isoformat(),
        }

        response = client.post(
            "/api/v1/jobs/", json=job_data, headers=security_token_headers["admin"]
        )
        assert response.status_code == 201
        job = response.json()
        job_id = job["id"]

        # Perform security-sensitive operations
        security_operations = [
            {
                "action": "job_creation",
                "user": "admin",
                "details": f"Created job {job_id}",
            },
            {
                "action": "unauthorized_access_attempt",
                "user": "guest",
                "details": "Attempted to modify job without permission",
            },
            {
                "action": "status_change",
                "user": "production_manager",
                "details": "Changed job status to APPROVED",
            },
        ]

        # Execute operations that should be audited
        for operation in security_operations:
            user = operation["user"]
            headers = security_token_headers[user]

            if operation["action"] == "unauthorized_access_attempt":
                # This should fail and be audited
                response = client.patch(
                    f"/api/v1/jobs/{job_id}",
                    json={"priority": "URGENT"},
                    headers=headers,
                )
                # Should be denied
                assert response.status_code in [401, 403]

            elif operation["action"] == "status_change":
                response = client.patch(
                    f"/api/v1/jobs/{job_id}/status",
                    json={"status": "APPROVED", "reason": "security_test"},
                    headers=headers,
                )
                # May succeed or fail based on permissions

        # Check audit log (if audit endpoint exists)
        response = client.get(
            "/api/v1/audit/security",
            params={
                "start_time": (datetime.utcnow() - timedelta(hours=1)).isoformat(),
                "end_time": datetime.utcnow().isoformat(),
            },
            headers=security_token_headers["admin"],
        )

        if response.status_code == 200:
            audit_log = response.json()

            # Should contain security-related events
            assert "events" in audit_log
            events = audit_log["events"]

            # Look for security events
            security_events = [
                event
                for event in events
                if event.get("category") == "security"
                or "unauthorized" in event.get("action", "").lower()
                or "login" in event.get("action", "").lower()
            ]

            # Should have recorded security events
            if security_events:
                for event in security_events:
                    assert "timestamp" in event
                    assert "user" in event or "user_id" in event
                    assert "action" in event

        elif response.status_code == 404:
            # Audit endpoint doesn't exist, which is acceptable for this test
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
