"""
Rate Limiting Module for API Security

This module implements comprehensive rate limiting to prevent brute force attacks,
DoS attacks, and API abuse.
"""

import logging
import time
from collections import defaultdict
from functools import wraps

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


# Custom key functions for rate limiting
def get_user_id_key(request: Request) -> str:
    """Get rate limit key based on authenticated user ID."""
    user = getattr(request.state, "current_user_id", None)
    if user:
        return f"user:{user}"
    return get_remote_address(request)


def get_ip_user_combo_key(request: Request) -> str:
    """Get rate limit key based on IP and user combination."""
    ip = get_remote_address(request)
    user = getattr(request.state, "current_user_id", None)
    if user:
        return f"{ip}:user:{user}"
    return ip


def get_endpoint_key(request: Request) -> str:
    """Get rate limit key based on endpoint and IP."""
    ip = get_remote_address(request)
    path = request.url.path
    return f"{ip}:{path}"


# Create limiter instances with different strategies
general_limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["1000 per hour", "100 per minute"],
    storage_uri="memory://",
)

auth_limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://",
)

api_limiter = Limiter(
    key_func=get_user_id_key,
    storage_uri="memory://",
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for comprehensive rate limiting."""

    def __init__(self, app, **kwargs):
        super().__init__(app)
        self.failed_attempts = defaultdict(list)  # Track failed login attempts
        self.blocked_ips = {}  # Temporarily blocked IPs
        self.request_history = defaultdict(list)  # Track request patterns

        # Configuration
        self.max_failed_attempts = 5
        self.block_duration = 900  # 15 minutes
        self.burst_threshold = 10  # Requests in burst window
        self.burst_window = 1  # 1 second

    async def dispatch(self, request: Request, call_next):
        """Apply rate limiting to incoming requests."""
        client_ip = get_remote_address(request)
        path = request.url.path

        # Check if IP is blocked
        if self._is_blocked(client_ip):
            logger.warning(f"Blocked IP attempted access: {client_ip}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Too many failed attempts. Please try again later.",
                    "retry_after": self._get_retry_after(client_ip),
                },
            )

        # Check for burst attacks
        if self._detect_burst(client_ip):
            logger.warning(f"Burst attack detected from: {client_ip}")
            self._block_ip(client_ip, self.block_duration)
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded. Unusual activity detected."},
            )

        # Track request
        self._track_request(client_ip)

        # Apply different limits based on endpoint
        if path.startswith("/api/v1/login") or path.startswith("/api/v1/password"):
            # Stricter limits for authentication endpoints
            limit = self._get_auth_limit(client_ip)
            if not self._check_rate_limit(client_ip, "auth", limit=limit, window=60):
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Authentication rate limit exceeded"},
                )

        # Process request
        try:
            response = await call_next(request)

            # Track failed authentication attempts
            if path.startswith("/api/v1/login") and response.status_code == 401:
                self._track_failed_attempt(client_ip)

            return response

        except Exception as e:
            logger.error(f"Rate limit middleware error: {e}")
            raise

    def _is_blocked(self, ip: str) -> bool:
        """Check if IP is currently blocked."""
        if ip in self.blocked_ips:
            block_time, duration = self.blocked_ips[ip]
            if time.time() - block_time < duration:
                return True
            else:
                # Unblock if duration has passed
                del self.blocked_ips[ip]
        return False

    def _block_ip(self, ip: str, duration: int):
        """Block an IP for specified duration."""
        self.blocked_ips[ip] = (time.time(), duration)
        logger.info(f"Blocked IP {ip} for {duration} seconds")

    def _get_retry_after(self, ip: str) -> int:
        """Get remaining block time for IP."""
        if ip in self.blocked_ips:
            block_time, duration = self.blocked_ips[ip]
            remaining = duration - (time.time() - block_time)
            return max(0, int(remaining))
        return 0

    def _track_request(self, ip: str):
        """Track request for burst detection."""
        current_time = time.time()
        self.request_history[ip].append(current_time)

        # Clean old entries
        cutoff_time = current_time - self.burst_window
        self.request_history[ip] = [
            t for t in self.request_history[ip] if t > cutoff_time
        ]

    def _detect_burst(self, ip: str) -> bool:
        """Detect burst attacks."""
        requests_in_window = len(self.request_history[ip])
        return requests_in_window > self.burst_threshold

    def _track_failed_attempt(self, ip: str):
        """Track failed authentication attempt."""
        current_time = time.time()
        self.failed_attempts[ip].append(current_time)

        # Clean old attempts (older than 1 hour)
        cutoff_time = current_time - 3600
        self.failed_attempts[ip] = [
            t for t in self.failed_attempts[ip] if t > cutoff_time
        ]

        # Check if threshold exceeded
        if len(self.failed_attempts[ip]) >= self.max_failed_attempts:
            self._block_ip(ip, self.block_duration)
            logger.warning(
                f"IP {ip} blocked after {self.max_failed_attempts} failed attempts"
            )

    def _get_auth_limit(self, ip: str) -> int:
        """Get authentication rate limit based on IP reputation."""
        # Adaptive rate limiting based on failed attempts
        failed_count = len(self.failed_attempts.get(ip, []))

        if failed_count == 0:
            return 10  # 10 attempts per minute for clean IPs
        elif failed_count < 3:
            return 5  # 5 attempts per minute after some failures
        else:
            return 2  # 2 attempts per minute for suspicious IPs

    def _check_rate_limit(self, key: str, bucket: str, limit: int, window: int) -> bool:
        """Check if rate limit is exceeded."""
        # Simple in-memory rate limiting (use Redis for production)
        bucket_key = f"{bucket}:{key}"
        current_time = time.time()

        if not hasattr(self, "_rate_buckets"):
            self._rate_buckets = {}

        if bucket_key not in self._rate_buckets:
            self._rate_buckets[bucket_key] = []

        # Clean old entries
        cutoff_time = current_time - window
        self._rate_buckets[bucket_key] = [
            t for t in self._rate_buckets[bucket_key] if t > cutoff_time
        ]

        # Check limit
        if len(self._rate_buckets[bucket_key]) >= limit:
            return False

        # Add current request
        self._rate_buckets[bucket_key].append(current_time)
        return True


class DistributedRateLimiter:
    """Distributed rate limiter for multi-instance deployments."""

    def __init__(self, redis_client=None):
        """Initialize with Redis client for distributed limiting."""
        self.redis_client = redis_client
        self.local_cache = {}  # Fallback to local cache if Redis unavailable

    def is_allowed(
        self, key: str, limit: int, window: int, cost: int = 1
    ) -> tuple[bool, dict]:
        """Check if request is allowed under rate limit.

        Args:
            key: Unique identifier for rate limit bucket
            limit: Maximum requests allowed in window
            window: Time window in seconds
            cost: Cost of this request (default 1)

        Returns:
            Tuple of (allowed, metadata)
        """
        if self.redis_client:
            return self._check_redis(key, limit, window, cost)
        else:
            return self._check_local(key, limit, window, cost)

    def _check_redis(
        self, key: str, limit: int, window: int, cost: int
    ) -> tuple[bool, dict]:
        """Check rate limit using Redis."""
        try:
            pipe = self.redis_client.pipeline()
            now = time.time()

            # Use sliding window with Redis sorted sets
            window_start = now - window

            # Remove old entries
            pipe.zremrangebyscore(key, 0, window_start)

            # Count current entries
            pipe.zcard(key)

            # Add current request if under limit
            pipe.zadd(key, {f"{now}:{cost}": now})

            # Set expiry
            pipe.expire(key, window + 1)

            results = pipe.execute()
            current_count = results[1]

            allowed = current_count + cost <= limit

            return allowed, {
                "limit": limit,
                "remaining": max(0, limit - current_count - cost),
                "reset": int(now + window),
            }

        except Exception as e:
            logger.error(f"Redis rate limit error: {e}")
            # Fallback to local cache
            return self._check_local(key, limit, window, cost)

    def _check_local(
        self, key: str, limit: int, window: int, cost: int
    ) -> tuple[bool, dict]:
        """Check rate limit using local cache."""
        now = time.time()
        window_start = now - window

        if key not in self.local_cache:
            self.local_cache[key] = []

        # Clean old entries
        self.local_cache[key] = [
            (t, c) for t, c in self.local_cache[key] if t > window_start
        ]

        # Calculate current usage
        current_usage = sum(c for _, c in self.local_cache[key])

        allowed = current_usage + cost <= limit

        if allowed:
            self.local_cache[key].append((now, cost))

        return allowed, {
            "limit": limit,
            "remaining": max(0, limit - current_usage - cost),
            "reset": int(now + window),
        }


# Decorators for rate limiting specific endpoints
def rate_limit(limit: str, key_func=get_remote_address, cost: int = 1):
    """Decorator for rate limiting specific endpoints.

    Args:
        limit: Rate limit string (e.g., "5 per minute", "100 per hour")
        key_func: Function to extract rate limit key from request
        cost: Cost of the request
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            # Parse limit string
            parts = limit.split(" per ")
            count = int(parts[0])

            period_map = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}

            period = parts[1].rstrip("s")  # Remove plural 's'
            window = period_map.get(period, 60)

            # Get rate limit key
            key = key_func(request)

            # Check rate limit
            limiter = DistributedRateLimiter()
            allowed, metadata = limiter.is_allowed(
                f"rate_limit:{func.__name__}:{key}", count, window, cost
            )

            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded",
                    headers={
                        "X-RateLimit-Limit": str(metadata["limit"]),
                        "X-RateLimit-Remaining": str(metadata["remaining"]),
                        "X-RateLimit-Reset": str(metadata["reset"]),
                        "Retry-After": str(metadata["reset"] - int(time.time())),
                    },
                )

            # Add rate limit headers to response
            response = await func(request, *args, **kwargs)
            response.headers["X-RateLimit-Limit"] = str(metadata["limit"])
            response.headers["X-RateLimit-Remaining"] = str(metadata["remaining"])
            response.headers["X-RateLimit-Reset"] = str(metadata["reset"])

            return response

        return wrapper

    return decorator


# Specific rate limiters for different endpoint types
auth_rate_limit = rate_limit("5 per minute", get_remote_address)
api_rate_limit = rate_limit("100 per minute", get_user_id_key)
heavy_operation_limit = rate_limit("10 per hour", get_user_id_key, cost=10)
