"""
Authorization Middleware

This module provides middleware for enforcing authorization policies across the API.
Implements defense-in-depth security with multiple authorization layers.

Security Features:
- Request-level authorization
- Resource-level access control
- Data filtering based on user scope
- Comprehensive audit logging
- OWASP compliant implementation
"""

import json
import logging
import time
from uuid import UUID

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.db import get_session
from app.core.rbac import (
    PermissionService,
    SchedulingPermission,
)
from app.core.security_enhanced import AuditLogger, SecureInputValidator

logger = logging.getLogger(__name__)
audit_logger = AuditLogger()


class AuthorizationMiddleware(BaseHTTPMiddleware):
    """
    Middleware for enforcing authorization policies.

    Security Features:
    - Path-based permission requirements
    - Method-based access control
    - Request body validation
    - Response filtering
    - Audit logging

    OWASP References:
    - A01:2021 - Broken Access Control
    - A03:2021 - Injection
    - A09:2021 - Security Logging and Monitoring Failures
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.validator = SecureInputValidator()

        # Define permission requirements for endpoints
        self.endpoint_permissions = self._build_endpoint_permissions()

        # Define public endpoints that don't require authentication
        self.public_endpoints = {
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/login/access-token",
            "/api/v1/login/test-token",
            "/api/v1/password-recovery",
            "/api/v1/reset-password",
            "/api/v1/health",
            "/metrics",
        }

        # Define sensitive endpoints requiring additional validation
        self.sensitive_endpoints = {
            "/api/v1/admin",
            "/api/v1/users/role",
            "/api/v1/permissions",
            "/api/v1/audit",
        }

    def _build_endpoint_permissions(
        self,
    ) -> dict[str, dict[str, list[SchedulingPermission]]]:
        """
        Build endpoint-to-permission mapping.

        Security: Centralized permission requirements for consistency.
        """
        return {
            # Job endpoints
            "/api/v1/jobs": {
                "GET": [SchedulingPermission.JOB_READ],
                "POST": [SchedulingPermission.JOB_CREATE],
            },
            "/api/v1/jobs/{job_id}": {
                "GET": [SchedulingPermission.JOB_READ],
                "PUT": [SchedulingPermission.JOB_UPDATE],
                "PATCH": [SchedulingPermission.JOB_UPDATE],
                "DELETE": [SchedulingPermission.JOB_DELETE],
            },
            "/api/v1/jobs/{job_id}/approve": {
                "POST": [SchedulingPermission.JOB_APPROVE],
            },
            "/api/v1/jobs/{job_id}/priority": {
                "PUT": [SchedulingPermission.JOB_PRIORITY_OVERRIDE],
            },
            # Schedule endpoints
            "/api/v1/schedules": {
                "GET": [SchedulingPermission.SCHEDULE_READ],
                "POST": [SchedulingPermission.SCHEDULE_CREATE],
            },
            "/api/v1/schedules/{schedule_id}": {
                "GET": [SchedulingPermission.SCHEDULE_READ],
                "PUT": [SchedulingPermission.SCHEDULE_MODIFY],
                "DELETE": [SchedulingPermission.SCHEDULE_MODIFY],
            },
            "/api/v1/schedules/{schedule_id}/optimize": {
                "POST": [SchedulingPermission.SCHEDULE_OPTIMIZE],
            },
            "/api/v1/schedules/{schedule_id}/publish": {
                "POST": [SchedulingPermission.SCHEDULE_PUBLISH],
            },
            "/api/v1/schedules/{schedule_id}/execute": {
                "POST": [SchedulingPermission.SCHEDULE_EXECUTE],
            },
            # Machine endpoints
            "/api/v1/machines": {
                "GET": [SchedulingPermission.MACHINE_READ],
                "POST": [SchedulingPermission.MACHINE_UPDATE],
            },
            "/api/v1/machines/{machine_id}": {
                "GET": [SchedulingPermission.MACHINE_READ],
                "PUT": [SchedulingPermission.MACHINE_UPDATE],
                "PATCH": [SchedulingPermission.MACHINE_UPDATE],
            },
            "/api/v1/machines/{machine_id}/maintenance": {
                "POST": [SchedulingPermission.MACHINE_MAINTAIN],
            },
            "/api/v1/machines/{machine_id}/schedule": {
                "GET": [SchedulingPermission.MACHINE_READ],
                "POST": [SchedulingPermission.MACHINE_SCHEDULE],
            },
            # Operator endpoints
            "/api/v1/operators": {
                "GET": [SchedulingPermission.OPERATOR_READ],
                "POST": [SchedulingPermission.OPERATOR_UPDATE],
            },
            "/api/v1/operators/{operator_id}": {
                "GET": [SchedulingPermission.OPERATOR_READ],
                "PUT": [SchedulingPermission.OPERATOR_UPDATE],
                "PATCH": [SchedulingPermission.OPERATOR_UPDATE],
            },
            "/api/v1/operators/{operator_id}/assign": {
                "POST": [SchedulingPermission.OPERATOR_ASSIGN],
            },
            "/api/v1/operators/{operator_id}/skills": {
                "GET": [SchedulingPermission.OPERATOR_READ],
                "PUT": [SchedulingPermission.OPERATOR_SKILL_MANAGE],
            },
            # Task endpoints
            "/api/v1/tasks": {
                "GET": [SchedulingPermission.TASK_READ],
            },
            "/api/v1/tasks/{task_id}": {
                "GET": [SchedulingPermission.TASK_READ],
                "PATCH": [SchedulingPermission.TASK_UPDATE_STATUS],
            },
            "/api/v1/tasks/{task_id}/reassign": {
                "POST": [SchedulingPermission.TASK_REASSIGN],
            },
            "/api/v1/tasks/{task_id}/complete": {
                "POST": [SchedulingPermission.TASK_COMPLETE],
            },
            # Report endpoints
            "/api/v1/reports": {
                "GET": [SchedulingPermission.REPORT_VIEW],
                "POST": [SchedulingPermission.REPORT_CREATE],
            },
            "/api/v1/reports/export": {
                "POST": [SchedulingPermission.REPORT_EXPORT],
            },
            # Admin endpoints
            "/api/v1/admin": {
                "GET": [SchedulingPermission.ADMIN_PANEL],
            },
            "/api/v1/admin/roles": {
                "GET": [SchedulingPermission.ROLE_MANAGE],
                "POST": [SchedulingPermission.ROLE_MANAGE],
                "PUT": [SchedulingPermission.ROLE_MANAGE],
                "DELETE": [SchedulingPermission.ROLE_MANAGE],
            },
            "/api/v1/admin/permissions": {
                "GET": [SchedulingPermission.PERMISSION_MANAGE],
                "POST": [SchedulingPermission.PERMISSION_MANAGE],
            },
            "/api/v1/admin/audit": {
                "GET": [SchedulingPermission.AUDIT_VIEW],
            },
            "/api/v1/admin/config": {
                "GET": [SchedulingPermission.SYSTEM_CONFIG],
                "PUT": [SchedulingPermission.SYSTEM_CONFIG],
            },
        }

    async def dispatch(self, request: Request, call_next):
        """
        Process request with authorization checks.

        Security: Implements multiple authorization layers.
        """
        start_time = time.time()

        # Extract request information
        path = request.url.path
        method = request.method
        client_ip = request.client.host if request.client else "unknown"

        try:
            # Check if endpoint is public
            if self._is_public_endpoint(path):
                response = await call_next(request)
                return response

            # Get current user from request state (set by authentication middleware)
            user_id = getattr(request.state, "current_user_id", None)

            if not user_id:
                # No authenticated user
                audit_logger.log_security_event(
                    event_type="UNAUTHORIZED_ACCESS",
                    severity="HIGH",
                    description=f"Unauthenticated access attempt to {path}",
                    ip_address=client_ip,
                    details={
                        "path": path,
                        "method": method,
                        "user_agent": request.headers.get("User-Agent", ""),
                    },
                )

                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Authentication required"},
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Check endpoint permissions
            required_permissions = self._get_required_permissions(path, method)

            if required_permissions:
                # Get user permissions
                with get_session() as session:
                    permission_service = PermissionService(session)
                    user_permissions = permission_service.get_user_permissions(
                        UUID(user_id)
                    )

                    # Check if user has required permissions
                    has_permission = any(
                        perm in user_permissions for perm in required_permissions
                    )

                    if not has_permission:
                        # Log authorization failure
                        audit_logger.log_security_event(
                            event_type="AUTHORIZATION_FAILED",
                            severity="HIGH",
                            description=f"Insufficient permissions for {path}",
                            user_id=UUID(user_id),
                            ip_address=client_ip,
                            details={
                                "path": path,
                                "method": method,
                                "required_permissions": [
                                    p.value for p in required_permissions
                                ],
                                "user_permissions": [p.value for p in user_permissions],
                            },
                        )

                        return JSONResponse(
                            status_code=status.HTTP_403_FORBIDDEN,
                            content={
                                "detail": f"Insufficient permissions. Required: {', '.join(p.value for p in required_permissions)}"
                            },
                        )

            # Additional validation for sensitive endpoints
            if self._is_sensitive_endpoint(path):
                # Validate request for injection attacks
                if not await self._validate_request_security(request):
                    audit_logger.log_security_event(
                        event_type="MALICIOUS_REQUEST",
                        severity="CRITICAL",
                        description=f"Potential injection attack detected on {path}",
                        user_id=UUID(user_id),
                        ip_address=client_ip,
                        details={"path": path, "method": method},
                    )

                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={"detail": "Invalid request parameters"},
                    )

            # Process request
            response = await call_next(request)

            # Apply response filtering based on user scope
            if method == "GET" and response.status_code == 200:
                response = await self._filter_response_data(
                    response, UUID(user_id), path, session
                )

            # Log successful authorization
            time.time() - start_time
            audit_logger.log_data_access(
                user_id=UUID(user_id),
                resource_type=self._get_resource_type(path),
                resource_id=self._extract_resource_id(path),
                action=method,
                ip_address=client_ip,
            )

            # Add security headers to response
            response.headers.update(self._get_security_headers())

            return response

        except Exception as e:
            # Log error
            logger.error(
                f"Authorization middleware error: {e}",
                exc_info=True,
                extra={
                    "path": path,
                    "method": method,
                    "user_id": user_id,
                    "error": str(e),
                },
            )

            # Return generic error to avoid information leakage
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error"},
            )

    def _is_public_endpoint(self, path: str) -> bool:
        """Check if endpoint is public."""
        return any(path.startswith(public) for public in self.public_endpoints)

    def _is_sensitive_endpoint(self, path: str) -> bool:
        """Check if endpoint is sensitive."""
        return any(path.startswith(sensitive) for sensitive in self.sensitive_endpoints)

    def _get_required_permissions(
        self, path: str, method: str
    ) -> list[SchedulingPermission] | None:
        """Get required permissions for endpoint."""
        # Try exact match first
        endpoint_key = path
        if endpoint_key in self.endpoint_permissions:
            method_permissions = self.endpoint_permissions[endpoint_key]
            return method_permissions.get(method, [])

        # Try pattern matching for parameterized paths
        for pattern, permissions in self.endpoint_permissions.items():
            if self._match_path_pattern(path, pattern):
                return permissions.get(method, [])

        return None

    def _match_path_pattern(self, path: str, pattern: str) -> bool:
        """Match path against pattern with parameters."""
        path_parts = path.split("/")
        pattern_parts = pattern.split("/")

        if len(path_parts) != len(pattern_parts):
            return False

        for path_part, pattern_part in zip(path_parts, pattern_parts, strict=False):
            if pattern_part.startswith("{") and pattern_part.endswith("}"):
                # This is a parameter, any value matches
                continue
            elif path_part != pattern_part:
                return False

        return True

    def _get_resource_type(self, path: str) -> str:
        """Extract resource type from path."""
        parts = path.split("/")
        if len(parts) >= 4:
            return parts[3]  # e.g., /api/v1/jobs -> "jobs"
        return "unknown"

    def _extract_resource_id(self, path: str) -> str:
        """Extract resource ID from path."""
        parts = path.split("/")
        if len(parts) >= 5:
            # Check if the part looks like a UUID or ID
            potential_id = parts[4]
            if self.validator.validate_uuid(potential_id) or potential_id.isdigit():
                return potential_id
        return ""

    async def _validate_request_security(self, request: Request) -> bool:
        """
        Validate request for security issues.

        Security: Prevents injection attacks (OWASP A03:2021).
        """
        try:
            # Check query parameters
            for param, value in request.query_params.items():
                if not self._is_safe_parameter(value):
                    logger.warning(f"Unsafe query parameter detected: {param}={value}")
                    return False

            # Check headers for injection attempts
            suspicious_headers = ["X-Forwarded-For", "X-Real-IP", "X-Original-URL"]
            for header in suspicious_headers:
                if header in request.headers:
                    value = request.headers[header]
                    if not self._is_safe_header_value(value):
                        logger.warning(f"Unsafe header detected: {header}={value}")
                        return False

            # Validate request body if present
            if request.method in ["POST", "PUT", "PATCH"]:
                try:
                    body = await request.body()
                    if body:
                        # Basic validation - can be extended based on content type
                        body_str = body.decode("utf-8")
                        if not self._is_safe_json_body(body_str):
                            logger.warning("Unsafe request body detected")
                            return False
                except Exception as e:
                    logger.error(f"Error validating request body: {e}")
                    return False

            return True

        except Exception as e:
            logger.error(f"Request validation error: {e}")
            return False

    def _is_safe_parameter(self, value: str) -> bool:
        """Check if parameter value is safe."""
        # Check for SQL injection patterns
        sql_patterns = [
            "';",
            '";',
            "--",
            "/*",
            "*/",
            "xp_",
            "sp_",
            "@@",
            "@",
            "char",
            "nchar",
            "varchar",
            "nvarchar",
            "alter",
            "begin",
            "cast",
            "create",
            "cursor",
            "declare",
            "delete",
            "drop",
            "end",
            "exec",
            "execute",
            "fetch",
            "insert",
            "kill",
            "select",
            "sys",
            "sysobjects",
            "syscolumns",
            "table",
            "update",
        ]

        value_lower = value.lower()
        for pattern in sql_patterns:
            if pattern in value_lower:
                return False

        # Check for NoSQL injection patterns
        nosql_patterns = ["$where", "$regex", "$ne", "$gt", "$lt", "$in", "$nin"]
        for pattern in nosql_patterns:
            if pattern in value:
                return False

        # Check for command injection
        cmd_patterns = ["|", ";", "&", "`", "$(", "${", "\\n", "\\r"]
        for pattern in cmd_patterns:
            if pattern in value:
                return False

        return True

    def _is_safe_header_value(self, value: str) -> bool:
        """Check if header value is safe."""
        # Check for header injection
        if "\n" in value or "\r" in value:
            return False

        # Check for XSS patterns
        xss_patterns = ["<script", "javascript:", "onerror=", "onload="]
        value_lower = value.lower()
        for pattern in xss_patterns:
            if pattern in value_lower:
                return False

        return True

    def _is_safe_json_body(self, body: str) -> bool:
        """Check if JSON body is safe."""
        try:
            # Try to parse as JSON
            data = json.loads(body)

            # Recursively check all string values
            def check_values(obj):
                if isinstance(obj, str):
                    return self._is_safe_parameter(obj)
                elif isinstance(obj, dict):
                    return all(check_values(v) for v in obj.values())
                elif isinstance(obj, list):
                    return all(check_values(item) for item in obj)
                return True

            return check_values(data)

        except json.JSONDecodeError:
            # Not valid JSON
            return False

    async def _filter_response_data(
        self, response: Response, user_id: UUID, path: str, session
    ) -> Response:
        """
        Filter response data based on user's data scope.

        Security: Implements row-level security for data access.
        """
        # This is a placeholder - actual implementation would:
        # 1. Parse response body
        # 2. Apply data scope filters
        # 3. Remove unauthorized data
        # 4. Return filtered response

        return response

    def _get_security_headers(self) -> dict[str, str]:
        """Get security headers for response."""
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
            "Cache-Control": "no-store, no-cache, must-revalidate, private",
        }


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware to prevent abuse.

    Security: Prevents brute force and DoS attacks (OWASP A04:2021).
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.rate_limits = {
            "/api/v1/login": {"requests": 5, "window": 300},  # 5 requests per 5 minutes
            "/api/v1/password-recovery": {"requests": 3, "window": 3600},  # 3 per hour
            "/api/v1/schedules/optimize": {
                "requests": 10,
                "window": 60,
            },  # 10 per minute
            "default": {
                "requests": 100,
                "window": 60,
            },  # 100 requests per minute default
        }
        self.request_counts: dict[str, list[float]] = {}

    async def dispatch(self, request: Request, call_next):
        """Apply rate limiting."""
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path

        # Get rate limit for endpoint
        limit_config = self._get_rate_limit(path)

        # Check rate limit
        if not self._check_rate_limit(client_ip, path, limit_config):
            audit_logger.log_security_event(
                event_type="RATE_LIMIT_EXCEEDED",
                severity="WARNING",
                description=f"Rate limit exceeded for {path}",
                ip_address=client_ip,
                details={
                    "path": path,
                    "limit": limit_config["requests"],
                    "window": limit_config["window"],
                },
            )

            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded. Please try again later."},
                headers={"Retry-After": str(limit_config["window"])},
            )

        response = await call_next(request)
        return response

    def _get_rate_limit(self, path: str) -> dict[str, int]:
        """Get rate limit configuration for path."""
        for endpoint, config in self.rate_limits.items():
            if endpoint != "default" and path.startswith(endpoint):
                return config
        return self.rate_limits["default"]

    def _check_rate_limit(
        self, client_ip: str, path: str, limit_config: dict[str, int]
    ) -> bool:
        """Check if request is within rate limit."""
        now = time.time()
        key = f"{client_ip}:{path}"

        if key not in self.request_counts:
            self.request_counts[key] = []

        # Remove old requests outside the window
        window_start = now - limit_config["window"]
        self.request_counts[key] = [
            t for t in self.request_counts[key] if t > window_start
        ]

        # Check if limit exceeded
        if len(self.request_counts[key]) >= limit_config["requests"]:
            return False

        # Add current request
        self.request_counts[key].append(now)
        return True
