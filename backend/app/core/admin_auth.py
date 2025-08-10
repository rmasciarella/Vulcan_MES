"""
Admin authentication and rate limiting helpers.

- require_admin: FastAPI dependency to ensure caller is an admin. Uses Supabase-backed auth already configured in deps.get_current_user and checks superuser flag or scheduling admin role.
- destructive_rate_limit: lightweight rate limiter for destructive ops, using existing DistributedRateLimiter with a stricter bucket.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Callable

from fastapi import Depends, HTTPException, Request, status

from app.api.deps import CurrentUser
from app.core.rate_limiter import DistributedRateLimiter, get_user_id_key

try:
    # Optional: richer RBAC, if available
    from app.core.rbac import SchedulingRole
except Exception:  # pragma: no cover - optional import
    SchedulingRole = None  # type: ignore


def require_admin(current_user: CurrentUser) -> CurrentUser:
    """Ensure the current user is an administrator.

    Accept either:
    - is_superuser (built-in flag), or
    - role == SchedulingRole.SCHEDULING_ADMIN (if RBAC module is present)
    """
    is_admin = getattr(current_user, "is_superuser", False)
    if not is_admin and SchedulingRole is not None:
        role_value = getattr(current_user, "role", None)
        try:
            # role may already be an enum or a raw value
            if role_value is not None and (
                role_value == SchedulingRole.SCHEDULING_ADMIN
                or getattr(role_value, "value", None) == getattr(SchedulingRole.SCHEDULING_ADMIN, "value", None)
            ):
                is_admin = True
        except Exception:
            is_admin = False

    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


def destructive_rate_limit(limit: int = 50, window_seconds: int = int(timedelta(hours=1).total_seconds())) -> Callable:
    """Return a dependency that rate limits destructive admin operations per user.

    Defaults: 50 destructive ops per hour per user.
    Uses in-memory DistributedRateLimiter; swap to Redis by wiring a client in rate_limiter.DistributedRateLimiter.
    """

    limiter = DistributedRateLimiter()

    async def _dep(request: Request) -> None:
        key_base = get_user_id_key(request)
        key = f"admin:destructive:{key_base}"
        allowed, meta = limiter.is_allowed(key, limit=limit, window=window_seconds, cost=1)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Admin destructive operation rate limit exceeded",
                headers={
                    "X-RateLimit-Limit": str(meta.get("limit", limit)),
                    "X-RateLimit-Remaining": str(meta.get("remaining", 0)),
                    "X-RateLimit-Reset": str(meta.get("reset", 0)),
                },
            )

    return _dep

