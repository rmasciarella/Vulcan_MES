"""
API Dependencies with Enhanced Security

This module provides dependency injection for FastAPI routes with RS256 JWT authentication,
input validation, and RBAC support.
"""

import logging
from collections.abc import Generator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import Session

from app.core import security
from app.core.config import settings
from app.core.supabase_jwt import verify_token as verify_supabase_jwt
from app.core.db import engine
from app.core.rsa_keys import rsa_key_manager
from app.models import TokenPayload, User

logger = logging.getLogger(__name__)

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


def get_current_user(session: SessionDep, token: TokenDep, request: Request) -> User:
    """Get current authenticated user from JWT token.

    Uses RS256 algorithm for enhanced security.
    Supports key rotation by trying multiple public keys.
    """
    try:
        if settings.USE_SUPABASE_AUTH:
            # Verify with Supabase JWKS
            try:
                payload = verify_supabase_jwt(token)
            except InvalidTokenError as e:
                logger.warning(f"Supabase token validation failed: {e}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Could not validate credentials",
                )
        else:
            # Get public keys for verification (supports key rotation)
            keys_to_try = []
            if security.ALGORITHM == "RS256":
                keys_to_try = rsa_key_manager.get_public_keys_for_verification()
            else:
                keys_to_try = [settings.SECRET_KEY]

            payload = None
            for key in keys_to_try:
                try:
                    payload = jwt.decode(token, key, algorithms=[security.ALGORITHM])
                    break  # Successfully decoded
                except InvalidTokenError:
                    continue  # Try next key

            if not payload:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Could not validate credentials",
                )

        # Verify token type if present; Supabase tokens may not use our custom 'type'
        token_type = payload.get("type")
        if token_type is not None and token_type != "access":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid token type",
            )

        token_data = TokenPayload(**payload)

    except (InvalidTokenError, ValidationError) as e:
        logger.warning(f"Token validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )

    user = session.get(User, token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    # Store user info in request state for audit logging
    request.state.current_user_id = user.id
    request.state.current_user_email = user.email

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user


# RBAC Dependencies
def require_role(allowed_roles: list[str]):
    """Dependency to check if user has required role.

    Args:
        allowed_roles: List of roles that are allowed to access the endpoint
    """

    def role_checker(current_user: CurrentUser) -> User:
        # Check if user has a role attribute (needs to be added to User model)
        user_role = getattr(current_user, "role", None)
        if not user_role or user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User role '{user_role}' not authorized. Required roles: {allowed_roles}",
            )
        return current_user

    return role_checker


def require_permission(required_permission: str):
    """Dependency to check if user has required permission.

    Args:
        required_permission: Permission required to access the endpoint
    """
    from app.core.security_enhanced import ROLE_PERMISSIONS, Permission, Role

    def permission_checker(current_user: CurrentUser) -> User:
        user_role = getattr(current_user, "role", None)
        if not user_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="User role not defined"
            )

        try:
            role_enum = Role(user_role)
            allowed_permissions = ROLE_PERMISSIONS.get(role_enum, [])

            if Permission(required_permission) not in allowed_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission '{required_permission}' not granted for role '{user_role}'",
                )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid role or permission",
            )

        return current_user

    return permission_checker
