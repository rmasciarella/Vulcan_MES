"""
Security Headers Middleware for comprehensive protection.

This middleware implements all recommended OWASP security headers to protect against
common web vulnerabilities including XSS, clickjacking, MIME sniffing, and more.
"""

import logging
import secrets

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.config import settings

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add comprehensive security headers to all responses.

    Implements OWASP recommended security headers:
    - Content Security Policy (CSP)
    - X-Content-Type-Options
    - X-Frame-Options
    - X-XSS-Protection
    - Strict-Transport-Security (HSTS)
    - Referrer-Policy
    - Permissions-Policy
    """

    def __init__(
        self,
        app: ASGIApp,
        enable_hsts: bool = True,
        enable_csp: bool = True,
        csp_report_only: bool = False,
        frame_options: str = "DENY",
        referrer_policy: str = "strict-origin-when-cross-origin",
    ):
        super().__init__(app)
        self.enable_hsts = enable_hsts and settings.ENVIRONMENT != "local"
        self.enable_csp = enable_csp
        self.csp_report_only = csp_report_only
        self.frame_options = frame_options
        self.referrer_policy = referrer_policy

        # CSP directives based on environment
        self.csp_directives = self._build_csp_directives()

    def _build_csp_directives(self) -> dict[str, list[str]]:
        """Build Content Security Policy directives based on environment."""

        # Base CSP directives
        directives = {
            "default-src": ["'self'"],
            "script-src": ["'self'"],
            "style-src": [
                "'self'",
                "'unsafe-inline'",
            ],  # Allow inline styles for Swagger UI
            "img-src": ["'self'", "data:", "https:"],
            "font-src": ["'self'", "data:"],
            "connect-src": ["'self'"],
            "frame-ancestors": ["'none'"],
            "base-uri": ["'self'"],
            "form-action": ["'self'"],
            "object-src": ["'none'"],
            "script-src-attr": ["'none'"],
            "upgrade-insecure-requests": [],
        }

        # Environment-specific adjustments
        if settings.ENVIRONMENT == "local":
            # More permissive for development
            directives["script-src"].extend(["'unsafe-inline'", "'unsafe-eval'"])
            directives["connect-src"].extend(["ws://localhost:*", "http://localhost:*"])
        elif settings.ENVIRONMENT == "staging":
            # Allow specific staging resources
            directives["connect-src"].append(settings.FRONTEND_HOST)
            if settings.SENTRY_DSN:
                directives["connect-src"].append("https://sentry.io")
        elif settings.ENVIRONMENT == "production":
            # Strictest CSP for production
            directives["require-trusted-types-for"] = ["'script'"]
            if settings.SENTRY_DSN:
                directives["connect-src"].append("https://sentry.io")

        # Add allowed CORS origins to connect-src
        for origin in settings.all_cors_origins:
            if origin not in directives["connect-src"]:
                directives["connect-src"].append(origin)

        return directives

    def _generate_csp_header(self, nonce: str | None = None) -> str:
        """Generate CSP header string from directives."""
        csp_parts = []

        for directive, sources in self.csp_directives.items():
            if not sources:
                csp_parts.append(directive)
            else:
                # Add nonce to script-src if provided
                if directive == "script-src" and nonce:
                    sources_with_nonce = sources + [f"'nonce-{nonce}'"]
                    csp_parts.append(f"{directive} {' '.join(sources_with_nonce)}")
                else:
                    csp_parts.append(f"{directive} {' '.join(sources)}")

        return "; ".join(csp_parts)

    def _generate_permissions_policy(self) -> str:
        """Generate Permissions-Policy header."""
        policies = {
            "accelerometer": "()",
            "camera": "()",
            "geolocation": "()",
            "gyroscope": "()",
            "magnetometer": "()",
            "microphone": "()",
            "payment": "()",
            "usb": "()",
            "interest-cohort": "()",  # Disable FLoC
            "battery": "()",
            "display-capture": "()",
            "document-domain": "()",
            "encrypted-media": "()",
            "execution-while-not-rendered": "()",
            "execution-while-out-of-viewport": "()",
            "fullscreen": "(self)",
            "navigation-override": "()",
            "oversized-images": "(none)",
            "picture-in-picture": "()",
            "publickey-credentials-get": "()",
            "sync-xhr": "()",
            "wake-lock": "()",
            "xr-spatial-tracking": "()",
        }

        return ", ".join([f"{key}={value}" for key, value in policies.items()])

    async def dispatch(self, request: Request, call_next):
        """Add security headers to response."""

        # Generate CSP nonce for this request
        nonce = None
        if self.enable_csp and "script-src" in self.csp_directives:
            nonce = secrets.token_urlsafe(16)
            request.state.csp_nonce = nonce

        # Process request
        response = await call_next(request)

        # Add security headers
        self._add_security_headers(response, nonce)

        return response

    def _add_security_headers(self, response: Response, nonce: str | None = None):
        """Add all security headers to response."""

        # Content-Type Options - Prevent MIME sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Frame Options - Prevent clickjacking
        response.headers["X-Frame-Options"] = self.frame_options

        # XSS Protection - Enable browser XSS protection
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer Policy - Control referrer information
        response.headers["Referrer-Policy"] = self.referrer_policy

        # Permissions Policy - Control browser features
        response.headers["Permissions-Policy"] = self._generate_permissions_policy()

        # HSTS - Force HTTPS
        if self.enable_hsts:
            max_age = 31536000  # 1 year
            response.headers["Strict-Transport-Security"] = (
                f"max-age={max_age}; includeSubDomains; preload"
            )

        # Content Security Policy
        if self.enable_csp:
            csp_header = self._generate_csp_header(nonce)
            if self.csp_report_only:
                response.headers["Content-Security-Policy-Report-Only"] = csp_header
            else:
                response.headers["Content-Security-Policy"] = csp_header

        # Additional security headers
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"

        # Cache control for sensitive content
        if response.status_code in [401, 403]:
            response.headers["Cache-Control"] = "no-store, private"

        # Remove potentially dangerous headers
        headers_to_remove = [
            "Server",
            "X-Powered-By",
            "X-AspNet-Version",
            "X-AspNetMvc-Version",
        ]
        for header in headers_to_remove:
            response.headers.pop(header, None)


class CORSSecurityMiddleware(BaseHTTPMiddleware):
    """
    Enhanced CORS middleware with security validations.
    """

    def __init__(
        self,
        app: ASGIApp,
        allowed_origins: list[str] = None,
        allowed_methods: list[str] = None,
        allowed_headers: list[str] = None,
        expose_headers: list[str] = None,
        max_age: int = 3600,
        allow_credentials: bool = True,
    ):
        super().__init__(app)
        self.allowed_origins = allowed_origins or settings.all_cors_origins
        self.allowed_methods = allowed_methods or [
            "GET",
            "POST",
            "PUT",
            "DELETE",
            "OPTIONS",
            "PATCH",
        ]
        self.allowed_headers = allowed_headers or ["*"]
        self.expose_headers = expose_headers or []
        self.max_age = max_age
        self.allow_credentials = allow_credentials

    async def dispatch(self, request: Request, call_next):
        """Handle CORS with security validations."""

        origin = request.headers.get("origin")

        # Handle preflight requests
        if request.method == "OPTIONS":
            response = Response(status_code=204)
            self._add_cors_headers(response, origin)
            return response

        # Process request
        response = await call_next(request)

        # Add CORS headers if origin is allowed
        if origin and self._is_origin_allowed(origin):
            self._add_cors_headers(response, origin)

        return response

    def _is_origin_allowed(self, origin: str) -> bool:
        """Validate if origin is allowed."""
        if "*" in self.allowed_origins:
            return True

        # Normalize origin
        origin = origin.rstrip("/")

        # Check against allowed origins
        for allowed in self.allowed_origins:
            allowed = str(allowed).rstrip("/")
            if origin == allowed:
                return True
            # Support wildcard subdomains
            if allowed.startswith("*."):
                domain = allowed[2:]
                if origin.endswith(domain):
                    return True

        logger.warning(f"CORS request from unauthorized origin: {origin}")
        return False

    def _add_cors_headers(self, response: Response, origin: str):
        """Add CORS headers to response."""
        if self._is_origin_allowed(origin):
            response.headers["Access-Control-Allow-Origin"] = origin

            if self.allow_credentials:
                response.headers["Access-Control-Allow-Credentials"] = "true"

            if self.allowed_methods:
                response.headers["Access-Control-Allow-Methods"] = ", ".join(
                    self.allowed_methods
                )

            if self.allowed_headers:
                if "*" in self.allowed_headers:
                    response.headers["Access-Control-Allow-Headers"] = "*"
                else:
                    response.headers["Access-Control-Allow-Headers"] = ", ".join(
                        self.allowed_headers
                    )

            if self.expose_headers:
                response.headers["Access-Control-Expose-Headers"] = ", ".join(
                    self.expose_headers
                )

            response.headers["Access-Control-Max-Age"] = str(self.max_age)

            # Add Vary header for proper caching
            existing_vary = response.headers.get("Vary", "")
            if existing_vary:
                response.headers["Vary"] = f"{existing_vary}, Origin"
            else:
                response.headers["Vary"] = "Origin"
