"""
Enhanced Security Module with RS256 JWT Authentication

This module implements secure authentication using RSA keys (RS256 algorithm)
instead of symmetric keys (HS256) for enhanced security in production environments.
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.rsa_keys import rsa_key_manager

logger = logging.getLogger(__name__)

# Enhanced password hashing with Argon2 as primary, bcrypt as fallback
pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated="auto",
    argon2__memory_cost=65536,
    argon2__time_cost=3,
    argon2__parallelism=4,
)

# Use RS256 for enhanced security (asymmetric encryption)
ALGORITHM = "RS256"

# Load RSA keys
try:
    PRIVATE_KEY, PUBLIC_KEY = rsa_key_manager.get_or_create_keys()
    logger.info("RSA keys loaded successfully for JWT authentication")
except Exception as e:
    logger.error(f"Failed to load RSA keys: {e}")
    # Fallback to HS256 if RSA fails (not recommended for production)
    logger.warning("Falling back to HS256 algorithm - NOT SECURE FOR PRODUCTION")
    ALGORITHM = "HS256"
    PRIVATE_KEY = settings.SECRET_KEY
    PUBLIC_KEY = settings.SECRET_KEY


def create_access_token(
    subject: str | Any, expires_delta: timedelta, additional_claims: dict | None = None
) -> str:
    """Create a secure JWT access token using RS256.

    Args:
        subject: The subject of the token (usually user ID)
        expires_delta: Token expiration time
        additional_claims: Additional claims to include in the token

    Returns:
        Encoded JWT token
    """
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "iat": datetime.now(timezone.utc),
        "jti": secrets.token_urlsafe(16),  # JWT ID for tracking/revocation
        "type": "access",
    }

    if additional_claims:
        to_encode.update(additional_claims)

    # Use private key for RS256
    key = PRIVATE_KEY if ALGORITHM == "RS256" else settings.SECRET_KEY
    encoded_jwt = jwt.encode(to_encode, key, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(
    subject: str | Any, expires_delta: timedelta | None = None
) -> str:
    """Create a secure JWT refresh token.

    Args:
        subject: The subject of the token (usually user ID)
        expires_delta: Token expiration time (default 30 days)

    Returns:
        Encoded JWT refresh token
    """
    if expires_delta is None:
        expires_delta = timedelta(days=30)

    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "iat": datetime.now(timezone.utc),
        "jti": secrets.token_urlsafe(16),
        "type": "refresh",
    }

    key = PRIVATE_KEY if ALGORITHM == "RS256" else settings.SECRET_KEY
    encoded_jwt = jwt.encode(to_encode, key, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> dict | None:
    """Verify and decode a JWT token.

    Args:
        token: The JWT token to verify
        token_type: Expected token type ("access" or "refresh")

    Returns:
        Decoded token payload or None if invalid
    """
    try:
        # Try with current public key first
        keys_to_try = []
        if ALGORITHM == "RS256":
            keys_to_try = rsa_key_manager.get_public_keys_for_verification()
        else:
            keys_to_try = [settings.SECRET_KEY]

        for key in keys_to_try:
            try:
                payload = jwt.decode(token, key, algorithms=[ALGORITHM])

                # Verify token type
                if payload.get("type") != token_type:
                    logger.warning(
                        f"Invalid token type: expected {token_type}, got {payload.get('type')}"
                    )
                    return None

                return payload
            except jwt.InvalidTokenError:
                continue  # Try next key

        # No valid key found
        logger.warning("Token verification failed with all available keys")
        return None

    except Exception as e:
        logger.error(f"Token verification error: {e}")
        return None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash.

    Uses Argon2 or bcrypt depending on the hash format.

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password to verify against

    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password using Argon2.

    Args:
        password: Plain text password to hash

    Returns:
        Hashed password
    """
    return pwd_context.hash(password)


def verify_password_strength(password: str) -> dict[str, Any]:
    """Verify password meets security requirements.

    Args:
        password: Password to validate

    Returns:
        Dictionary with validation results
    """
    import re

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
    common_passwords = ["password", "123456", "admin", "letmein", "welcome", "qwerty"]
    if any(common in password.lower() for common in common_passwords):
        issues.append("Password is too common")
        score = max(0, score - 50)

    return {"valid": len(issues) == 0, "score": score, "issues": issues}
