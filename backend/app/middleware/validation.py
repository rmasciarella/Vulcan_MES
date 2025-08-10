"""
Comprehensive input validation middleware for security.

This middleware provides protection against:
- SQL Injection
- XSS (Cross-Site Scripting)
- Command Injection
- Path Traversal
- Invalid Input Formats
"""

import html
import logging
import re
from typing import Any
from urllib.parse import unquote

import bleach
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# SQL Injection patterns
SQL_INJECTION_PATTERNS = [
    r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE|UNION|INTO|LOAD_FILE|OUTFILE)\b)",
    r"(--|#|\/\*|\*\/)",  # SQL comments
    r"(\bOR\b.*=.*)",  # OR conditions
    r"(\bAND\b.*=.*)",  # AND conditions
    r"(\'|\"|;|\\x00|\\n|\\r|\\x1a)",  # Special characters
    r"(\bxp_cmdshell\b|\bsp_executesql\b)",  # SQL Server specific
    r"(\bSLEEP\b|\bBENCHMARK\b|\bWAITFOR\b)",  # Time-based attacks
]

# XSS patterns
XSS_PATTERNS = [
    r"(<script[^>]*>.*?</script>)",  # Script tags
    r"(javascript:|vbscript:|on\w+\s*=)",  # Event handlers and protocols
    r"(<iframe[^>]*>.*?</iframe>)",  # Iframes
    r"(<object[^>]*>.*?</object>)",  # Objects
    r"(<embed[^>]*>)",  # Embeds
    r"(alert\s*\(|confirm\s*\(|prompt\s*\()",  # JavaScript functions
    r"(document\.|window\.|eval\s*\()",  # DOM manipulation
]

# Command injection patterns
COMMAND_INJECTION_PATTERNS = [
    r"([;&|`$])",  # Shell metacharacters
    r"(\|\||&&)",  # Command chaining
    r"(>\s*\/dev\/null)",  # Redirection
    r"(\$\(.*\)|\`.*\`)",  # Command substitution
]

# Path traversal patterns
PATH_TRAVERSAL_PATTERNS = [
    r"(\.\.\/|\.\.\\)",  # Directory traversal
    r"(\/etc\/passwd|\/etc\/shadow)",  # Sensitive files
    r"(C:\\windows\\system32)",  # Windows paths
    r"(%2e%2e%2f|%252e%252e%252f)",  # URL encoded traversal
]

# Allowed HTML tags for sanitization
ALLOWED_TAGS = [
    "p",
    "br",
    "span",
    "div",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "strong",
    "em",
    "u",
    "i",
    "b",
    "a",
    "ul",
    "ol",
    "li",
    "code",
    "pre",
]

ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "target"],
    "code": ["class"],
}


class InputValidator:
    """Core input validation logic."""

    @staticmethod
    def detect_sql_injection(value: str) -> bool:
        """Detect potential SQL injection attempts."""
        if not value:
            return False

        value_upper = value.upper()
        for pattern in SQL_INJECTION_PATTERNS:
            if re.search(pattern, value_upper, re.IGNORECASE):
                logger.warning(
                    f"SQL injection pattern detected: {pattern} in value: {value[:100]}"
                )
                return True
        return False

    @staticmethod
    def detect_xss(value: str) -> bool:
        """Detect potential XSS attempts."""
        if not value:
            return False

        # Decode URL encoding
        decoded_value = unquote(value)

        for pattern in XSS_PATTERNS:
            if re.search(pattern, decoded_value, re.IGNORECASE):
                logger.warning(
                    f"XSS pattern detected: {pattern} in value: {decoded_value[:100]}"
                )
                return True
        return False

    @staticmethod
    def detect_command_injection(value: str) -> bool:
        """Detect potential command injection attempts."""
        if not value:
            return False

        for pattern in COMMAND_INJECTION_PATTERNS:
            if re.search(pattern, value):
                logger.warning(
                    f"Command injection pattern detected: {pattern} in value: {value[:100]}"
                )
                return True
        return False

    @staticmethod
    def detect_path_traversal(value: str) -> bool:
        """Detect potential path traversal attempts."""
        if not value:
            return False

        # Decode URL encoding multiple times
        decoded = value
        for _ in range(3):
            decoded = unquote(decoded)

        for pattern in PATH_TRAVERSAL_PATTERNS:
            if re.search(pattern, decoded, re.IGNORECASE):
                logger.warning(
                    f"Path traversal pattern detected: {pattern} in value: {decoded[:100]}"
                )
                return True
        return False

    @staticmethod
    def sanitize_html(value: str) -> str:
        """Sanitize HTML content to prevent XSS."""
        if not value:
            return value

        # Clean HTML using bleach
        cleaned = bleach.clean(
            value, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, strip=True
        )

        # Additional escaping for safety
        cleaned = html.escape(cleaned)

        return cleaned

    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format."""
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(email_pattern, email))

    @staticmethod
    def validate_phone(phone: str) -> bool:
        """Validate phone number format."""
        # Remove common separators
        cleaned = re.sub(r"[\s\-\(\)\+]", "", phone)
        # Check if it's a valid phone number (10-15 digits)
        return bool(re.match(r"^\d{10,15}$", cleaned))

    @staticmethod
    def validate_url(url: str) -> bool:
        """Validate URL format."""
        url_pattern = r"^https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&\/\/=]*)$"
        return bool(re.match(url_pattern, url))

    @staticmethod
    def validate_alphanumeric(value: str, allow_spaces: bool = False) -> bool:
        """Validate alphanumeric string."""
        if allow_spaces:
            return bool(re.match(r"^[a-zA-Z0-9\s]+$", value))
        return bool(re.match(r"^[a-zA-Z0-9]+$", value))

    @staticmethod
    def validate_integer_range(value: int, min_val: int, max_val: int) -> bool:
        """Validate integer is within range."""
        return min_val <= value <= max_val


class ValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware for validating all incoming requests.
    """

    def __init__(self, app, enable_strict_mode: bool = True):
        super().__init__(app)
        self.validator = InputValidator()
        self.enable_strict_mode = enable_strict_mode

        # Paths that should skip validation
        self.skip_paths = [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            "/metrics",
        ]

    async def dispatch(self, request: Request, call_next):
        """Process each request for validation."""

        # Skip validation for certain paths
        if any(request.url.path.startswith(path) for path in self.skip_paths):
            return await call_next(request)

        try:
            # Validate query parameters
            if request.query_params:
                self._validate_params(dict(request.query_params))

            # Validate path parameters
            if request.path_params:
                self._validate_params(request.path_params)

            # Validate body for POST/PUT/PATCH requests
            if request.method in ["POST", "PUT", "PATCH"]:
                # Read body
                body = await request.body()
                if body:
                    # Store body for later use
                    request.state.body = body

                    # Parse JSON if content-type is application/json
                    content_type = request.headers.get("content-type", "")
                    if "application/json" in content_type:
                        import json

                        try:
                            json_body = json.loads(body)
                            self._validate_json_body(json_body)
                        except json.JSONDecodeError:
                            return JSONResponse(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                content={"detail": "Invalid JSON format"},
                            )

            # Validate headers
            self._validate_headers(dict(request.headers))

        except HTTPException as e:
            logger.error(f"Validation failed for {request.url.path}: {e.detail}")
            return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
        except Exception as e:
            logger.error(f"Unexpected validation error: {e}")
            if self.enable_strict_mode:
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={"detail": "Internal validation error"},
                )

        # Continue with request processing
        response = await call_next(request)
        return response

    def _validate_params(self, params: dict[str, Any]):
        """Validate request parameters."""
        for key, value in params.items():
            if isinstance(value, str):
                # Check for injection attempts
                if self.validator.detect_sql_injection(value):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid parameter: {key}",
                    )

                if self.validator.detect_xss(value):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid parameter: {key}",
                    )

                if self.validator.detect_command_injection(value):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid parameter: {key}",
                    )

                if self.validator.detect_path_traversal(value):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid parameter: {key}",
                    )

    def _validate_json_body(self, body: dict | list, path: str = ""):
        """Recursively validate JSON body."""
        if isinstance(body, dict):
            for key, value in body.items():
                current_path = f"{path}.{key}" if path else key
                if isinstance(value, str):
                    self._validate_string_value(value, current_path)
                elif isinstance(value, dict | list):
                    self._validate_json_body(value, current_path)
        elif isinstance(body, list):
            for index, item in enumerate(body):
                current_path = f"{path}[{index}]"
                if isinstance(item, str):
                    self._validate_string_value(item, current_path)
                elif isinstance(item, dict | list):
                    self._validate_json_body(item, current_path)

    def _validate_string_value(self, value: str, field_name: str):
        """Validate a string value for security issues."""
        if self.validator.detect_sql_injection(value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid input in field: {field_name}",
            )

        if self.validator.detect_xss(value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid input in field: {field_name}",
            )

        if self.validator.detect_command_injection(value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid input in field: {field_name}",
            )

    def _validate_headers(self, headers: dict[str, str]):
        """Validate request headers."""
        # Check for suspicious headers
        suspicious_headers = [
            "x-forwarded-host",
            "x-forwarded-server",
            "x-forwarded-for",
            "x-real-ip",
        ]

        for header in suspicious_headers:
            if header in headers:
                value = headers[header]
                if (
                    self.validator.detect_sql_injection(value)
                    or self.validator.detect_xss(value)
                    or self.validator.detect_command_injection(value)
                ):
                    logger.warning(
                        f"Suspicious header detected: {header}: {value[:100]}"
                    )
                    if self.enable_strict_mode:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid header value",
                        )


# Pydantic models with built-in validation
class SecureStringField(str):
    """Custom string field with security validation."""

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise ValueError("String required")

        validator = InputValidator()
        if (
            validator.detect_sql_injection(v)
            or validator.detect_xss(v)
            or validator.detect_command_injection(v)
        ):
            raise ValueError("Invalid input detected")

        return v


class SecureEmailField(str):
    """Custom email field with validation."""

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise ValueError("String required")

        validator = InputValidator()
        if not validator.validate_email(v):
            raise ValueError("Invalid email format")

        return v.lower()


# Example usage in Pydantic models
class SecureUserInput(BaseModel):
    """Example model with secure fields."""

    username: SecureStringField = Field(..., min_length=3, max_length=50)
    email: SecureEmailField
    bio: str | None = None

    @validator("bio")
    def sanitize_bio(cls, v):
        if v:
            validator = InputValidator()
            return validator.sanitize_html(v)
        return v
