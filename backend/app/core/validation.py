"""
Comprehensive Input Validation Module

This module provides middleware and utilities for validating and sanitizing
all input to the API endpoints to prevent injection attacks and ensure data integrity.
"""

import html
import logging
import re
from datetime import date, datetime
from typing import Any
from uuid import UUID

from fastapi import Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field, root_validator, validator
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class InputSanitizer:
    """Comprehensive input sanitization utilities."""

    # Dangerous patterns that could indicate injection attempts
    SQL_INJECTION_PATTERNS = [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE|UNION|FROM|WHERE|HAVING|ORDER BY|GROUP BY)\b)",
        r"(--|#|/\*|\*/|@@|@|xp_|sp_)",
        r"(\bOR\b\s*\d+\s*=\s*\d+)",  # OR 1=1
        r"(\bAND\b\s*\d+\s*=\s*\d+)",  # AND 1=1
        r"(CHAR\(|CONCAT\(|CHR\()",
        r"(WAITFOR|DELAY|SLEEP)",
        r"(\\x[0-9a-fA-F]{2})",  # Hex encoding
    ]

    XSS_PATTERNS = [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"on\w+\s*=",  # Event handlers like onclick=
        r"<iframe[^>]*>",
        r"<object[^>]*>",
        r"<embed[^>]*>",
        r"<applet[^>]*>",
        r"<meta[^>]*http-equiv",
        r"<link[^>]*href",
        r"eval\s*\(",
        r"expression\s*\(",
    ]

    PATH_TRAVERSAL_PATTERNS = [
        r"\.\./",  # ../
        r"\.\\/",  # ..\
        r"%2e%2e/",  # URL encoded ../
        r"%252e%252e/",  # Double URL encoded
        r"\.\.\\",
        r"/etc/passwd",
        r"C:\\",
        r"file://",
    ]

    COMMAND_INJECTION_PATTERNS = [
        r"[;&|`$]",  # Shell metacharacters
        r"\$\(",  # Command substitution
        r"`.*`",  # Backticks
        r"\\n|\\r",  # Newlines that might break out
    ]

    @classmethod
    def detect_sql_injection(cls, value: str) -> bool:
        """Detect potential SQL injection attempts."""
        if not value:
            return False

        value_upper = value.upper()
        for pattern in cls.SQL_INJECTION_PATTERNS:
            if re.search(pattern, value_upper, re.IGNORECASE):
                logger.warning(f"Potential SQL injection detected: {value[:100]}")
                return True
        return False

    @classmethod
    def detect_xss(cls, value: str) -> bool:
        """Detect potential XSS attempts."""
        if not value:
            return False

        for pattern in cls.XSS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                logger.warning(f"Potential XSS detected: {value[:100]}")
                return True
        return False

    @classmethod
    def detect_path_traversal(cls, value: str) -> bool:
        """Detect potential path traversal attempts."""
        if not value:
            return False

        for pattern in cls.PATH_TRAVERSAL_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                logger.warning(f"Potential path traversal detected: {value[:100]}")
                return True
        return False

    @classmethod
    def detect_command_injection(cls, value: str) -> bool:
        """Detect potential command injection attempts."""
        if not value:
            return False

        for pattern in cls.COMMAND_INJECTION_PATTERNS:
            if re.search(pattern, value):
                logger.warning(f"Potential command injection detected: {value[:100]}")
                return True
        return False

    @classmethod
    def sanitize_html(cls, value: str) -> str:
        """Remove HTML tags and escape special characters."""
        # Remove all HTML tags
        value = re.sub(r"<[^>]+>", "", value)
        # Escape remaining HTML entities
        return html.escape(value)

    @classmethod
    def sanitize_sql_identifier(cls, identifier: str) -> str:
        """Sanitize SQL identifiers (table names, column names)."""
        # Only allow alphanumeric and underscore
        sanitized = re.sub(r"[^a-zA-Z0-9_]", "", identifier)
        # Ensure it doesn't start with a number
        if sanitized and sanitized[0].isdigit():
            sanitized = "_" + sanitized
        return sanitized

    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """Sanitize filename to prevent directory traversal."""
        # Remove path components
        filename = filename.replace("/", "").replace("\\", "")
        # Remove dangerous patterns
        filename = re.sub(r"\.\.+", "", filename)
        # Only allow safe characters
        filename = re.sub(r"[^a-zA-Z0-9._-]", "_", filename)
        return filename

    @classmethod
    def validate_and_sanitize(cls, value: Any, field_type: str = "text") -> Any:
        """Validate and sanitize input based on field type."""
        if value is None:
            return value

        if isinstance(value, str):
            # Check for injection attempts
            if cls.detect_sql_injection(value):
                raise ValueError("Potential SQL injection detected")
            if cls.detect_xss(value):
                raise ValueError("Potential XSS detected")
            if field_type == "path" and cls.detect_path_traversal(value):
                raise ValueError("Potential path traversal detected")
            if field_type == "command" and cls.detect_command_injection(value):
                raise ValueError("Potential command injection detected")

            # Sanitize based on type
            if field_type == "html":
                return cls.sanitize_html(value)
            elif field_type == "filename":
                return cls.sanitize_filename(value)
            elif field_type == "sql_identifier":
                return cls.sanitize_sql_identifier(value)

        return value


class ValidationMiddleware(BaseHTTPMiddleware):
    """Middleware for comprehensive input validation."""

    CONTENT_TYPE_LIMITS = {
        "application/json": 1024 * 1024,  # 1 MB for JSON
        "application/x-www-form-urlencoded": 256 * 1024,  # 256 KB for forms
        "multipart/form-data": 10 * 1024 * 1024,  # 10 MB for file uploads
    }

    async def dispatch(self, request: Request, call_next):
        """Validate incoming requests."""
        try:
            # Check content length
            content_length = request.headers.get("content-length")
            if content_length:
                content_length = int(content_length)
                content_type = request.headers.get("content-type", "").split(";")[0]
                max_size = self.CONTENT_TYPE_LIMITS.get(
                    content_type,
                    100 * 1024,  # Default 100 KB
                )

                if content_length > max_size:
                    logger.warning(
                        f"Request body too large: {content_length} bytes "
                        f"(max: {max_size} bytes) for {content_type}"
                    )
                    return JSONResponse(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        content={"detail": "Request body too large"},
                    )

            # Validate headers
            suspicious_headers = self._check_suspicious_headers(request.headers)
            if suspicious_headers:
                logger.warning(f"Suspicious headers detected: {suspicious_headers}")
                # Log but don't block - some headers might be legitimate

            # Process request
            response = await call_next(request)

            # Add security headers to response
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

            return response

        except Exception as e:
            logger.error(f"Validation middleware error: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error"},
            )

    def _check_suspicious_headers(self, headers: dict) -> list[str]:
        """Check for suspicious headers that might indicate attacks."""
        suspicious = []

        # Check for SQL injection in headers
        for name, value in headers.items():
            if InputSanitizer.detect_sql_injection(value):
                suspicious.append(f"{name}: potential SQL injection")
            if InputSanitizer.detect_xss(value):
                suspicious.append(f"{name}: potential XSS")

        # Check for header smuggling
        if "\n" in str(headers) or "\r" in str(headers):
            suspicious.append("Potential header smuggling")

        return suspicious


# Pydantic models with built-in validation
class SecureStringField(str):
    """A string field with built-in security validation."""

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v: Any) -> str:
        if not isinstance(v, str):
            raise TypeError("String required")

        # Check for injection attempts
        if InputSanitizer.detect_sql_injection(v):
            raise ValueError("Invalid input: potential SQL injection")
        if InputSanitizer.detect_xss(v):
            raise ValueError("Invalid input: potential XSS")

        return v


class SecureEmailField(EmailStr):
    """Email field with additional security validation."""

    @classmethod
    def validate(cls, v: str) -> str:
        # First use Pydantic's email validation
        email = super().validate(v)

        # Additional security checks
        if len(email) > 254:  # RFC 5321
            raise ValueError("Email too long")

        # Check for injection attempts in email
        if InputSanitizer.detect_sql_injection(email):
            raise ValueError("Invalid email: potential injection")

        return email


class BaseSecureModel(BaseModel):
    """Base model with security validation for all fields."""

    class Config:
        # Forbid extra fields to prevent parameter pollution
        extra = "forbid"
        # Validate on assignment
        validate_assignment = True
        # Use enum values
        use_enum_values = True

    @root_validator(pre=True)
    def validate_no_injection(cls, values):
        """Check all string fields for injection attempts."""
        for field_name, value in values.items():
            if isinstance(value, str):
                # Skip validation for specific safe fields if needed
                safe_fields = []  # Add field names that don't need validation

                if field_name not in safe_fields:
                    try:
                        InputSanitizer.validate_and_sanitize(value)
                    except ValueError as e:
                        raise ValueError(f"Field '{field_name}': {str(e)}")

        return values


# Validation schemas for common entities
class JobValidation(BaseSecureModel):
    """Validation schema for Job entities."""

    job_number: str = Field(..., regex=r"^[A-Z0-9\-]{1,50}$", description="Job number")
    description: str = Field(..., max_length=500)
    priority: int = Field(..., ge=1, le=10)
    duration_hours: float = Field(..., gt=0, le=1000)
    due_date: datetime | None = None

    @validator("job_number")
    def validate_job_number(cls, v):
        if not v or len(v) > 50:
            raise ValueError("Invalid job number format")
        return v.upper()


class OperatorValidation(BaseSecureModel):
    """Validation schema for Operator entities."""

    employee_id: str = Field(..., regex=r"^EMP[0-9]{3,10}$")
    name: str = Field(..., max_length=100)
    email: SecureEmailField
    skills: list[str] = Field(..., max_items=20)

    @validator("skills")
    def validate_skills(cls, v):
        for skill in v:
            if not re.match(r"^[A-Za-z0-9\s\-_]{1,50}$", skill):
                raise ValueError(f"Invalid skill name: {skill}")
        return v


class MachineValidation(BaseSecureModel):
    """Validation schema for Machine entities."""

    machine_code: str = Field(..., regex=r"^[A-Z0-9_]{1,20}$")
    name: str = Field(..., max_length=100)
    capacity: float = Field(..., gt=0, le=10000)
    status: str = Field(..., regex=r"^(AVAILABLE|MAINTENANCE|BROKEN)$")


def validate_uuid(uuid_string: str) -> bool:
    """Validate UUID format."""
    try:
        UUID(uuid_string)
        return True
    except ValueError:
        return False


def validate_date_range(start_date: date, end_date: date) -> bool:
    """Validate date range is valid."""
    if start_date > end_date:
        raise ValueError("Start date must be before end date")

    # Check for reasonable date range (e.g., not more than 5 years)
    delta = end_date - start_date
    if delta.days > 1825:  # 5 years
        raise ValueError("Date range too large (max 5 years)")

    return True


def validate_pagination(skip: int = 0, limit: int = 100) -> tuple[int, int]:
    """Validate and sanitize pagination parameters."""
    # Ensure non-negative
    skip = max(0, skip)

    # Ensure reasonable limits
    limit = max(1, min(limit, 1000))  # Between 1 and 1000

    # Prevent excessive skipping
    if skip > 100000:
        raise ValueError("Skip value too large")

    return skip, limit
