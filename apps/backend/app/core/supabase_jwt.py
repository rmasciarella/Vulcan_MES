import time
import logging
from typing import Any, Dict, Optional

import jwt
import requests
from jwt import InvalidTokenError

from app.core.config import settings

logger = logging.getLogger(__name__)


class _JWKSCache:
    """Simple in-memory JWKS cache keyed by 'kid'."""

    def __init__(self, jwks_url: str, ttl_seconds: int) -> None:
        self._jwks_url = jwks_url
        self._ttl = ttl_seconds
        self._kid_to_key: dict[str, Any] = {}
        self._fetched_at: float = 0.0

    def _refresh(self) -> None:
        resp = requests.get(self._jwks_url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        keys = data.get("keys", [])
        self._kid_to_key = {}
        for k in keys:
            kid = k.get("kid")
            if not kid:
                continue
            try:
                jwk = jwt.algorithms.RSAAlgorithm.from_jwk(k)
            except Exception as e:
                logger.warning("Failed to parse JWK kid=%s: %s", kid, e)
                continue
            self._kid_to_key[kid] = jwk
        self._fetched_at = time.time()
        logger.debug("JWKS cache refreshed; %d keys loaded", len(self._kid_to_key))

    def get_key_for_token(self, token: str) -> Any:
        try:
            unverified_header = jwt.get_unverified_header(token)
        except Exception as e:
            raise InvalidTokenError(f"Invalid JWT header: {e}") from e

        kid = unverified_header.get("kid")
        if not kid:
            # Some providers may omit kid; fallback to first key after refresh
            logger.debug("JWT missing kid; falling back to first JWKS key")
        now = time.time()
        if (now - self._fetched_at) > self._ttl or not self._kid_to_key:
            self._refresh()

        if kid:
            key = self._kid_to_key.get(kid)
            if key is None:
                # Refresh once more in case of rotation
                self._refresh()
                key = self._kid_to_key.get(kid)
            if key is None:
                raise InvalidTokenError("No matching JWK for token kid")
            return key

        # No kid — return any available key
        if not self._kid_to_key:
            raise InvalidTokenError("No JWKs available to verify token")
        return next(iter(self._kid_to_key.values()))


_jwks_cache: Optional[_JWKSCache] = None


def _get_cache() -> _JWKSCache:
    global _jwks_cache
    jwks_url = settings.SUPABASE_JWKS_URL
    if not jwks_url:
        raise RuntimeError("SUPABASE_JWKS_URL is not configured")
    if _jwks_cache is None:
        _jwks_cache = _JWKSCache(jwks_url=jwks_url, ttl_seconds=settings.SUPABASE_JWKS_CACHE_SECONDS)
    return _jwks_cache


def verify_token(token: str, audience: Optional[str] = None, issuer: Optional[str] = None) -> Dict[str, Any]:
    """Verify a Supabase JWT using JWKS.

    - Fetches and caches JWKS
    - Verifies RS256 signature, expiry, not-before
    - Optionally verifies audience and issuer if provided
    Returns the decoded payload dict.
    """
    key = _get_cache().get_key_for_token(token)

    options = {"verify_aud": audience is not None}
    try:
        payload = jwt.decode(
            token,
            key=key,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer,
            options=options,
        )
        return payload
    except InvalidTokenError:
        raise
    except Exception as e:
        # Normalize to InvalidTokenError for callers
        raise InvalidTokenError(str(e)) from e
