"""
Dual authentication system supporting both FastAPI JWT and Supabase Auth.
This allows gradual migration and flexibility in authentication methods.
"""

from typing import Optional, Union, Annotated
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.core.db import get_db
from app.core.supabase import supabase
from app import crud, models


class AuthMode(BaseModel):
    """Authentication mode configuration."""
    mode: str  # "jwt", "supabase", or "dual"
    jwt_enabled: bool = True
    supabase_enabled: bool = False


class DualAuthBearer(HTTPBearer):
    """Custom bearer authentication that supports both JWT and Supabase tokens."""
    
    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error)
    
    async def __call__(self, request: Request) -> Optional[HTTPAuthorizationCredentials]:
        credentials = await super().__call__(request)
        if credentials:
            # Store the auth scheme for later use
            request.state.auth_scheme = credentials.scheme
            request.state.auth_token = credentials.credentials
        return credentials


# Create the dual auth scheme
dual_auth_scheme = DualAuthBearer()


async def verify_token(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(dual_auth_scheme)],
    db: Session = Depends(get_db),
) -> models.User:
    """
    Verify authentication token from either FastAPI JWT or Supabase.
    Returns the authenticated user from the local database.
    """
    token = credentials.credentials
    
    # Try FastAPI JWT first (if enabled)
    if settings.USE_SUPABASE_AUTH is False or settings.SUPABASE_URL is None:
        return await verify_jwt_token(token, db)
    
    # Try Supabase token
    supabase_user = await verify_supabase_token(token)
    if supabase_user:
        # Sync/get user from local DB
        local_user = await supabase.sync_user_to_local_db(supabase_user, db)
        return local_user
    
    # If both fail, try JWT as fallback
    try:
        return await verify_jwt_token(token, db)
    except HTTPException:
        # Both authentication methods failed
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def verify_jwt_token(token: str, db: Session) -> models.User:
    """Verify a FastAPI-issued JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate JWT credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = crud.user.get(db, id=int(user_id))
    if user is None:
        raise credentials_exception
    
    if not crud.user.is_active(user):
        raise HTTPException(status_code=400, detail="Inactive user")
    
    return user


async def verify_supabase_token(token: str) -> Optional[dict]:
    """Verify a Supabase-issued JWT token."""
    if not settings.SUPABASE_URL:
        return None
    
    try:
        # Verify token with Supabase
        user_data = await supabase.verify_jwt_token(token)
        if user_data and user_data.get("user"):
            return user_data["user"]
    except Exception as e:
        print(f"Supabase token verification failed: {e}")
    
    return None


def get_current_user(
    user: Annotated[models.User, Depends(verify_token)]
) -> models.User:
    """Get the current authenticated user."""
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


def get_current_active_superuser(
    current_user: Annotated[models.User, Depends(get_current_user)],
) -> models.User:
    """Get the current authenticated superuser."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user


class TokenData(BaseModel):
    """Token data model for dual auth."""
    access_token: str
    token_type: str = "bearer"
    expires_in: Optional[int] = None
    refresh_token: Optional[str] = None
    provider: str = "jwt"  # "jwt" or "supabase"


async def create_dual_auth_token(
    user: models.User,
    use_supabase: bool = False,
    db: Session = None,
) -> TokenData:
    """
    Create an authentication token using either FastAPI JWT or Supabase.
    """
    if use_supabase and settings.SUPABASE_URL:
        # For Supabase auth, we would typically use Supabase's auth flow
        # This is a placeholder - actual implementation would use Supabase SDK
        return TokenData(
            access_token="supabase_token_placeholder",
            token_type="bearer",
            provider="supabase",
        )
    else:
        # Create FastAPI JWT token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = security.create_access_token(
            user.id, expires_delta=access_token_expires
        )
        return TokenData(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            provider="jwt",
        )


# Export dependencies for use in routes
CurrentUser = Annotated[models.User, Depends(get_current_user)]
CurrentSuperuser = Annotated[models.User, Depends(get_current_active_superuser)]