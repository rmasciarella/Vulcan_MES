"""
Enhanced Security Module

Implements security best practices and fixes for identified vulnerabilities.
This module provides secure implementations for authentication, authorization,
input validation, and data protection.
"""

import html
import re
import secrets
from datetime import datetime, timedelta, timezone
from enum import Enum
from functools import wraps
from typing import Any
from uuid import UUID

import jwt
import pyotp
from cryptography.fernet import Fernet
from passlib.context import CryptContext
from pydantic import EmailStr
from slowapi import Limiter
from slowapi.util import get_remote_address

# Enhanced password hashing with Argon2
pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated="auto",
    argon2__memory_cost=65536,
    argon2__time_cost=3,
    argon2__parallelism=4,
)

# Use RS256 for JWT (asymmetric)
ALGORITHM = "RS256"

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


class Role(str, Enum):
    """User roles for RBAC."""

    OPERATOR = "operator"
    SCHEDULER = "scheduler"
    MANAGER = "manager"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"


class Permission(str, Enum):
    """Granular permissions."""

    # Job permissions
    VIEW_JOBS = "view_jobs"
    CREATE_JOB = "create_job"
    UPDATE_JOB = "update_job"
    DELETE_JOB = "delete_job"
    CHANGE_JOB_STATUS = "change_job_status"
    SCHEDULE_JOB = "schedule_job"

    # Schedule permissions
    VIEW_SCHEDULES = "view_schedules"
    CREATE_SCHEDULE = "create_schedule"
    OPTIMIZE_SCHEDULE = "optimize_schedule"
    MANAGE_SCHEDULE = "manage_schedule"
    DELETE_SCHEDULE = "delete_schedule"
    PUBLISH_SCHEDULES = "publish_schedules"
    EXECUTE_SCHEDULES = "execute_schedules"

    # Resource permissions
    VIEW_OPERATORS = "view_operators"
    MANAGE_OPERATORS = "manage_operators"
    VIEW_MACHINES = "view_machines"
    MANAGE_MACHINES = "manage_machines"
    VIEW_RESOURCES = "view_resources"
    MANAGE_RESOURCES = "manage_resources"

    # System permissions
    VIEW_REPORTS = "view_reports"
    VIEW_SYSTEM_STATUS = "view_system_status"
    ADMIN_PANEL = "admin_panel"

    # Legacy permissions (for backward compatibility)
    CREATE_JOBS = "create_jobs"
    EDIT_JOBS = "edit_jobs"
    DELETE_JOBS = "delete_jobs"
    VIEW_SCHEDULES_LEGACY = "view_schedules"
    CREATE_SCHEDULES = "create_schedules"


# Role-Permission mapping
ROLE_PERMISSIONS: dict[Role, list[Permission]] = {
    Role.OPERATOR: [
        Permission.VIEW_JOBS,
        Permission.VIEW_SCHEDULES,
        Permission.VIEW_RESOURCES,
        Permission.VIEW_SYSTEM_STATUS,
    ],
    Role.SCHEDULER: [
        Permission.VIEW_JOBS,
        Permission.CREATE_JOB,
        Permission.UPDATE_JOB,
        Permission.CHANGE_JOB_STATUS,
        Permission.SCHEDULE_JOB,
        Permission.VIEW_SCHEDULES,
        Permission.CREATE_SCHEDULE,
        Permission.OPTIMIZE_SCHEDULE,
        Permission.VIEW_OPERATORS,
        Permission.VIEW_MACHINES,
        Permission.VIEW_RESOURCES,
        Permission.VIEW_SYSTEM_STATUS,
        # Legacy permissions
        Permission.CREATE_JOBS,
        Permission.EDIT_JOBS,
        Permission.CREATE_SCHEDULES,
    ],
    Role.MANAGER: [
        Permission.VIEW_JOBS,
        Permission.CREATE_JOB,
        Permission.UPDATE_JOB,
        Permission.DELETE_JOB,
        Permission.CHANGE_JOB_STATUS,
        Permission.SCHEDULE_JOB,
        Permission.VIEW_SCHEDULES,
        Permission.CREATE_SCHEDULE,
        Permission.OPTIMIZE_SCHEDULE,
        Permission.MANAGE_SCHEDULE,
        Permission.DELETE_SCHEDULE,
        Permission.PUBLISH_SCHEDULES,
        Permission.VIEW_OPERATORS,
        Permission.MANAGE_OPERATORS,
        Permission.VIEW_MACHINES,
        Permission.MANAGE_MACHINES,
        Permission.VIEW_RESOURCES,
        Permission.MANAGE_RESOURCES,
        Permission.VIEW_REPORTS,
        Permission.VIEW_SYSTEM_STATUS,
        # Legacy permissions
        Permission.CREATE_JOBS,
        Permission.EDIT_JOBS,
        Permission.DELETE_JOBS,
        Permission.CREATE_SCHEDULES,
    ],
    Role.ADMIN: [
        # All job permissions
        Permission.VIEW_JOBS,
        Permission.CREATE_JOB,
        Permission.UPDATE_JOB,
        Permission.DELETE_JOB,
        Permission.CHANGE_JOB_STATUS,
        Permission.SCHEDULE_JOB,
        # All schedule permissions
        Permission.VIEW_SCHEDULES,
        Permission.CREATE_SCHEDULE,
        Permission.OPTIMIZE_SCHEDULE,
        Permission.MANAGE_SCHEDULE,
        Permission.DELETE_SCHEDULE,
        Permission.PUBLISH_SCHEDULES,
        Permission.EXECUTE_SCHEDULES,
        # All resource permissions
        Permission.VIEW_OPERATORS,
        Permission.MANAGE_OPERATORS,
        Permission.VIEW_MACHINES,
        Permission.MANAGE_MACHINES,
        Permission.VIEW_RESOURCES,
        Permission.MANAGE_RESOURCES,
        # System permissions
        Permission.VIEW_REPORTS,
        Permission.VIEW_SYSTEM_STATUS,
        Permission.ADMIN_PANEL,
        # Legacy permissions
        Permission.CREATE_JOBS,
        Permission.EDIT_JOBS,
        Permission.DELETE_JOBS,
        Permission.CREATE_SCHEDULES,
    ],
    Role.SUPERADMIN: list(Permission),  # All permissions
}


class SecureInputValidator:
    """Comprehensive input validation and sanitization."""

    # Regex patterns for validation
    PATTERNS = {
        "alphanumeric": r"^[a-zA-Z0-9]+$",
        "alphanumeric_dash": r"^[a-zA-Z0-9\-_]+$",
        "job_number": r"^[A-Z0-9\-]{1,50}$",
        "employee_id": r"^EMP[0-9]{3,10}$",
        "machine_code": r"^[A-Z0-9_]{1,20}$",
        "safe_text": r"^[a-zA-Z0-9\s\-_.,!?()]+$",
        "phone": r"^\+?[1-9]\d{1,14}$",  # E.164 format
        "sql_safe": r"^[^;\'\"\\]*$",  # Basic SQL injection prevention
    }

    @classmethod
    def validate_pattern(cls, value: str, pattern_name: str) -> bool:
        """Validate value against a named pattern."""
        pattern = cls.PATTERNS.get(pattern_name)
        if not pattern:
            raise ValueError(f"Unknown pattern: {pattern_name}")
        return bool(re.match(pattern, value))

    @classmethod
    def sanitize_html(cls, value: str) -> str:
        """Remove HTML tags and escape special characters."""
        # Remove HTML tags
        value = re.sub(r"<[^>]+>", "", value)
        # Escape remaining HTML entities
        return html.escape(value)

    @classmethod
    def sanitize_sql(cls, value: str) -> str:
        """Basic SQL injection prevention."""
        # Remove dangerous SQL characters
        dangerous_chars = [";", "'", '"', "--", "/*", "*/", "xp_", "sp_", "@@", "@"]
        for char in dangerous_chars:
            value = value.replace(char, "")
        return value

    @classmethod
    def validate_email(cls, email: str) -> bool:
        """Comprehensive email validation."""
        # Use pydantic's EmailStr for validation
        try:
            EmailStr.validate(email)
            # Additional DNS validation could be added here
            return True
        except Exception:
            return False

    @classmethod
    def validate_uuid(cls, uuid_str: str) -> bool:
        """Validate UUID format."""
        try:
            UUID(uuid_str)
            return True
        except ValueError:
            return False

    @classmethod
    def validate_length(
        cls, value: str, min_length: int = 1, max_length: int = 1000
    ) -> bool:
        """Validate string length."""
        return min_length <= len(value) <= max_length


class FieldEncryption:
    """Field-level encryption for sensitive data."""

    def __init__(self, master_key: bytes | None = None):
        """Initialize with master key or generate one."""
        if master_key:
            self.master_key = master_key
        else:
            self.master_key = Fernet.generate_key()
        self.cipher = Fernet(self.master_key)

    def encrypt_field(self, value: str) -> str:
        """Encrypt a field value."""
        if not value:
            return value
        encrypted = self.cipher.encrypt(value.encode())
        return encrypted.decode()

    def decrypt_field(self, encrypted_value: str) -> str:
        """Decrypt a field value."""
        if not encrypted_value:
            return encrypted_value
        decrypted = self.cipher.decrypt(encrypted_value.encode())
        return decrypted.decode()

    def encrypt_dict(
        self, data: dict[str, Any], fields_to_encrypt: list[str]
    ) -> dict[str, Any]:
        """Encrypt specific fields in a dictionary."""
        encrypted_data = data.copy()
        for field in fields_to_encrypt:
            if field in encrypted_data and encrypted_data[field]:
                encrypted_data[field] = self.encrypt_field(str(encrypted_data[field]))
        return encrypted_data

    def decrypt_dict(
        self, data: dict[str, Any], fields_to_decrypt: list[str]
    ) -> dict[str, Any]:
        """Decrypt specific fields in a dictionary."""
        decrypted_data = data.copy()
        for field in fields_to_decrypt:
            if field in decrypted_data and decrypted_data[field]:
                decrypted_data[field] = self.decrypt_field(decrypted_data[field])
        return decrypted_data


class MFAService:
    """Multi-Factor Authentication service."""

    def __init__(self, issuer_name: str = "Production Scheduler"):
        self.issuer_name = issuer_name

    def generate_secret(self) -> str:
        """Generate a new MFA secret."""
        return pyotp.random_base32()

    def generate_provisioning_uri(self, secret: str, user_email: str) -> str:
        """Generate QR code provisioning URI."""
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(name=user_email, issuer_name=self.issuer_name)

    def verify_token(self, secret: str, token: str, valid_window: int = 1) -> bool:
        """Verify MFA token."""
        totp = pyotp.TOTP(secret)
        return totp.verify(token, valid_window=valid_window)

    def generate_backup_codes(self, count: int = 10) -> list[str]:
        """Generate backup codes for account recovery."""
        return [secrets.token_hex(4) for _ in range(count)]


class SessionManager:
    """Secure session management."""

    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self.sessions: dict[str, dict] = {}  # In-memory fallback

    def create_session(
        self,
        user_id: UUID,
        ip_address: str,
        user_agent: str,
        ttl_seconds: int = 1800,  # 30 minutes default
    ) -> str:
        """Create a new session."""
        session_id = secrets.token_urlsafe(32)
        session_data = {
            "user_id": str(user_id),
            "ip_address": ip_address,
            "user_agent": user_agent,
            "created_at": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat(),
        }

        if self.redis_client:
            self.redis_client.setex(
                f"session:{session_id}", ttl_seconds, json.dumps(session_data)
            )
        else:
            self.sessions[session_id] = session_data

        return session_id

    def validate_session(self, session_id: str, ip_address: str) -> dict | None:
        """Validate and return session data."""
        if self.redis_client:
            session_data = self.redis_client.get(f"session:{session_id}")
            if session_data:
                session_data = json.loads(session_data)
        else:
            session_data = self.sessions.get(session_id)

        if not session_data:
            return None

        # Validate IP address hasn't changed (optional security measure)
        if session_data.get("ip_address") != ip_address:
            # Log potential session hijacking attempt
            return None

        # Update last activity
        session_data["last_activity"] = datetime.utcnow().isoformat()

        return session_data

    def destroy_session(self, session_id: str) -> bool:
        """Destroy a session."""
        if self.redis_client:
            return bool(self.redis_client.delete(f"session:{session_id}"))
        else:
            return bool(self.sessions.pop(session_id, None))


class AuditLogger:
    """Comprehensive audit logging."""

    def __init__(self, logger=None):
        self.logger = logger or self._setup_default_logger()

    def _setup_default_logger(self):
        import logging

        logger = logging.getLogger("security_audit")
        logger.setLevel(logging.INFO)
        handler = logging.FileHandler("security_audit.log")
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    def log_authentication(
        self,
        event_type: str,
        user_id: UUID | None,
        ip_address: str,
        success: bool,
        details: dict | None = None,
    ):
        """Log authentication events."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "user_id": str(user_id) if user_id else None,
            "ip_address": ip_address,
            "success": success,
            "details": details or {},
        }
        self.logger.info(f"AUTH: {json.dumps(log_entry)}")

    def log_data_access(
        self,
        user_id: UUID,
        resource_type: str,
        resource_id: str,
        action: str,
        ip_address: str,
    ):
        """Log data access events."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": str(user_id),
            "resource_type": resource_type,
            "resource_id": resource_id,
            "action": action,
            "ip_address": ip_address,
        }
        self.logger.info(f"DATA_ACCESS: {json.dumps(log_entry)}")

    def log_security_event(
        self,
        event_type: str,
        severity: str,
        description: str,
        ip_address: str | None = None,
        user_id: UUID | None = None,
        details: dict | None = None,
    ):
        """Log security events."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "severity": severity,
            "description": description,
            "ip_address": ip_address,
            "user_id": str(user_id) if user_id else None,
            "details": details or {},
        }

        if severity in ["CRITICAL", "HIGH"]:
            self.logger.error(f"SECURITY: {json.dumps(log_entry)}")
        else:
            self.logger.warning(f"SECURITY: {json.dumps(log_entry)}")


def create_secure_token(
    subject: str | UUID,
    expires_delta: timedelta,
    private_key: str,
    additional_claims: dict | None = None,
) -> str:
    """Create a secure JWT token with RS256."""
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "iat": datetime.now(timezone.utc),
        "jti": secrets.token_urlsafe(16),  # JWT ID for tracking
    }

    if additional_claims:
        to_encode.update(additional_claims)

    encoded_jwt = jwt.encode(to_encode, private_key, algorithm=ALGORITHM)
    return encoded_jwt


def verify_secure_token(
    token: str, public_key: str, verify_exp: bool = True
) -> dict | None:
    """Verify and decode a secure JWT token."""
    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=[ALGORITHM],
            options={"verify_exp": verify_exp},
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def verify_password_strength(password: str) -> dict[str, Any]:
    """Verify password meets security requirements."""
    issues = []
    score = 0

    # Length check
    if len(password) < 12:
        issues.append("Password must be at least 12 characters long")
    else:
        score += 25

    # Complexity checks
    if not re.search(r"[A-Z]", password):
        issues.append("Password must contain uppercase letters")
    else:
        score += 25

    if not re.search(r"[a-z]", password):
        issues.append("Password must contain lowercase letters")
    else:
        score += 25

    if not re.search(r"\d", password):
        issues.append("Password must contain numbers")
    else:
        score += 15

    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        issues.append("Password must contain special characters")
    else:
        score += 10

    # Common password check (basic)
    common_passwords = ["password", "123456", "admin", "letmein", "welcome"]
    if any(common in password.lower() for common in common_passwords):
        issues.append("Password is too common")
        score = max(0, score - 50)

    return {"valid": len(issues) == 0, "score": score, "issues": issues}


def generate_secure_password(length: int = 16) -> str:
    """Generate a cryptographically secure password."""
    import string

    # Ensure all character types are included
    lowercase = secrets.choice(string.ascii_lowercase)
    uppercase = secrets.choice(string.ascii_uppercase)
    digit = secrets.choice(string.digits)
    special = secrets.choice('!@#$%^&*(),.?":{}|<>')

    # Fill the rest randomly
    all_chars = string.ascii_letters + string.digits + '!@#$%^&*(),.?":{}|<>'
    remaining = "".join(secrets.choice(all_chars) for _ in range(length - 4))

    # Combine and shuffle
    password_list = list(lowercase + uppercase + digit + special + remaining)
    secrets.SystemRandom().shuffle(password_list)

    return "".join(password_list)


def hash_password_secure(password: str) -> str:
    """Hash password using Argon2."""
    return pwd_context.hash(password)


def verify_password_secure(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash."""
    return pwd_context.verify(plain_password, hashed_password)


def require_permission(permission: Permission):
    """Decorator to check permissions."""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get current user from context (implementation depends on framework)
            current_user = kwargs.get("current_user")
            if not current_user:
                raise PermissionError("Authentication required")

            user_role = current_user.get("role")
            if not user_role:
                raise PermissionError("User role not defined")

            allowed_permissions = ROLE_PERMISSIONS.get(Role(user_role), [])
            if permission not in allowed_permissions:
                raise PermissionError(f"Permission denied: {permission} required")

            return await func(*args, **kwargs)

        return wrapper

    return decorator


# Security headers configuration
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}


import json  # Add at the top of the file if not already imported
