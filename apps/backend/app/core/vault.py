"""
HashiCorp Vault integration for dynamic secrets management.

This module provides secure secret management using HashiCorp Vault,
including database credential rotation, API key management, and
encrypted configuration storage.
"""

import logging
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import wraps
from typing import Any

import hvac
from hvac.exceptions import InvalidRequest, VaultError
from requests.exceptions import ConnectionError, RequestException

logger = logging.getLogger(__name__)


@dataclass
class VaultConfig:
    """Vault configuration parameters."""

    url: str = "http://localhost:8200"
    token: str | None = None
    auth_method: str = "token"  # token, userpass, aws, kubernetes, etc.
    mount_point: str = "secret"
    database_mount: str = "database"
    transit_mount: str = "transit"
    namespace: str | None = None
    verify_ssl: bool = True
    timeout: int = 30


@dataclass
class DatabaseCredentials:
    """Database credentials from Vault."""

    username: str
    password: str
    lease_id: str
    lease_duration: int
    renewable: bool
    created_at: datetime
    expires_at: datetime


@dataclass
class SecretMetadata:
    """Metadata for cached secrets."""

    path: str
    version: int
    created_time: datetime
    deletion_time: datetime | None
    destroyed: bool
    ttl: int | None


class VaultClientError(Exception):
    """Base exception for Vault client errors."""

    pass


class VaultConnectionError(VaultClientError):
    """Exception for Vault connection issues."""

    pass


class VaultAuthenticationError(VaultClientError):
    """Exception for Vault authentication failures."""

    pass


class VaultSecretNotFoundError(VaultClientError):
    """Exception for missing secrets."""

    pass


class VaultClient:
    """
    Enhanced HashiCorp Vault client with caching and auto-renewal.

    Features:
    - Token auto-renewal
    - Secret caching with TTL
    - Database credential rotation
    - Transit encryption/decryption
    - Health monitoring and connection pooling
    """

    def __init__(self, config: VaultConfig | None = None):
        self.config = config or self._load_config()
        self._client: hvac.Client | None = None
        self._secret_cache: dict[str, dict[str, Any]] = {}
        self._cache_metadata: dict[str, SecretMetadata] = {}
        self._db_credentials: DatabaseCredentials | None = None
        self._renewal_thread: threading.Thread | None = None
        self._stop_renewal = threading.Event()
        self._lock = threading.RLock()
        self._last_health_check = datetime.utcnow()
        self._health_check_interval = timedelta(minutes=5)

    def _load_config(self) -> VaultConfig:
        """Load Vault configuration from environment variables."""
        return VaultConfig(
            url=os.getenv("VAULT_ADDR", "http://localhost:8200"),
            token=os.getenv("VAULT_TOKEN"),
            auth_method=os.getenv("VAULT_AUTH_METHOD", "token"),
            mount_point=os.getenv("VAULT_MOUNT_POINT", "secret"),
            database_mount=os.getenv("VAULT_DATABASE_MOUNT", "database"),
            transit_mount=os.getenv("VAULT_TRANSIT_MOUNT", "transit"),
            namespace=os.getenv("VAULT_NAMESPACE"),
            verify_ssl=os.getenv("VAULT_SKIP_VERIFY", "false").lower() != "true",
            timeout=int(os.getenv("VAULT_TIMEOUT", "30")),
        )

    def initialize(self) -> None:
        """Initialize the Vault client and authenticate."""
        try:
            self._client = hvac.Client(
                url=self.config.url,
                token=self.config.token,
                namespace=self.config.namespace,
                verify=self.config.verify_ssl,
                timeout=self.config.timeout,
            )

            # Authenticate using configured method
            if self.config.auth_method == "token":
                if not self.config.token:
                    raise VaultAuthenticationError(
                        "Token required for token authentication"
                    )
                # Token is already set in client

            elif self.config.auth_method == "userpass":
                username = os.getenv("VAULT_USERNAME")
                password = os.getenv("VAULT_PASSWORD")
                if not username or not password:
                    raise VaultAuthenticationError(
                        "Username and password required for userpass auth"
                    )

                response = self._client.auth.userpass.login(
                    username=username, password=password
                )
                self._client.token = response["auth"]["client_token"]

            elif self.config.auth_method == "aws":
                # AWS IAM authentication
                response = self._client.auth.aws.iam_login()
                self._client.token = response["auth"]["client_token"]

            else:
                raise VaultAuthenticationError(
                    f"Unsupported auth method: {self.config.auth_method}"
                )

            # Verify authentication
            if not self._client.is_authenticated():
                raise VaultAuthenticationError("Failed to authenticate with Vault")

            # Start token renewal thread
            self._start_renewal_thread()

            logger.info("Vault client initialized successfully")

        except (RequestException, ConnectionError) as e:
            raise VaultConnectionError(f"Failed to connect to Vault: {e}")
        except VaultError as e:
            raise VaultAuthenticationError(f"Vault authentication failed: {e}")

    def _start_renewal_thread(self):
        """Start background thread for token renewal."""
        if self._renewal_thread and self._renewal_thread.is_alive():
            return

        self._stop_renewal.clear()
        self._renewal_thread = threading.Thread(
            target=self._renewal_worker, daemon=True, name="vault-renewal"
        )
        self._renewal_thread.start()
        logger.debug("Token renewal thread started")

    def _renewal_worker(self):
        """Background worker for token and lease renewal."""
        while not self._stop_renewal.wait(60):  # Check every minute
            try:
                # Renew token if needed
                self._renew_token_if_needed()

                # Renew database credentials if needed
                self._renew_db_credentials_if_needed()

                # Perform health check
                self._health_check_if_needed()

            except Exception as e:
                logger.error(f"Error in renewal worker: {e}")

    def _renew_token_if_needed(self):
        """Renew token if it's close to expiration."""
        if not self._client:
            return

        try:
            # Get token info
            token_info = self._client.auth.token.lookup_self()

            if token_info["data"].get("renewable", False):
                ttl = token_info["data"].get("ttl", 0)

                # Renew if TTL is less than 10 minutes
                if ttl < 600:
                    self._client.auth.token.renew_self()
                    logger.debug("Token renewed successfully")

        except VaultError as e:
            logger.warning(f"Token renewal failed: {e}")

    def _renew_db_credentials_if_needed(self):
        """Renew database credentials if they're close to expiration."""
        if not self._db_credentials:
            return

        # Check if credentials expire within 5 minutes
        if self._db_credentials.expires_at - datetime.utcnow() < timedelta(minutes=5):
            try:
                new_creds = self.get_database_credentials()
                if new_creds:
                    self._db_credentials = new_creds
                    logger.info("Database credentials renewed")
            except Exception as e:
                logger.error(f"Failed to renew database credentials: {e}")

    def _health_check_if_needed(self):
        """Perform health check if interval has passed."""
        now = datetime.utcnow()
        if now - self._last_health_check > self._health_check_interval:
            try:
                self.health_check()
                self._last_health_check = now
            except Exception as e:
                logger.warning(f"Health check failed: {e}")

    def health_check(self) -> dict[str, Any]:
        """Check Vault server health."""
        if not self._client:
            raise VaultConnectionError("Client not initialized")

        try:
            health = self._client.sys.read_health_status()
            sealed = health.get("sealed", True)
            standby = health.get("standby", True)

            if sealed:
                raise VaultConnectionError("Vault is sealed")

            return {
                "healthy": True,
                "sealed": sealed,
                "standby": standby,
                "server_time_utc": health.get("server_time_utc"),
                "version": health.get("version"),
            }

        except RequestException as e:
            raise VaultConnectionError(f"Health check failed: {e}")

    def get_secret(
        self, path: str, mount_point: str | None = None, use_cache: bool = True
    ) -> dict[str, Any] | None:
        """
        Retrieve a secret from Vault.

        Args:
            path: Secret path
            mount_point: Mount point (defaults to configured mount)
            use_cache: Whether to use cached version

        Returns:
            Secret data or None if not found
        """
        if not self._client:
            raise VaultConnectionError("Client not initialized")

        mount = mount_point or self.config.mount_point
        full_path = f"{mount}/{path}"

        # Check cache first
        if use_cache and full_path in self._secret_cache:
            metadata = self._cache_metadata.get(full_path)
            if metadata and not self._is_cache_expired(metadata):
                logger.debug(f"Returning cached secret for {full_path}")
                return self._secret_cache[full_path]

        try:
            # Try KV v2 first, then KV v1
            try:
                response = self._client.secrets.kv.v2.read_secret_version(
                    path=path, mount_point=mount
                )
                secret_data = response["data"]["data"]
                metadata = response["data"]["metadata"]
            except (InvalidRequest, KeyError):
                # Fallback to KV v1
                response = self._client.secrets.kv.v1.read_secret(
                    path=path, mount_point=mount
                )
                secret_data = response["data"]
                metadata = None

            # Cache the secret
            if use_cache:
                self._cache_secret(full_path, secret_data, metadata)

            logger.debug(f"Retrieved secret from {full_path}")
            return secret_data

        except InvalidRequest as e:
            if "permission denied" in str(e).lower():
                raise VaultAuthenticationError(f"Access denied to secret {full_path}")
            raise VaultSecretNotFoundError(f"Secret not found: {full_path}")
        except VaultError as e:
            logger.error(f"Failed to retrieve secret {full_path}: {e}")
            raise VaultClientError(f"Failed to retrieve secret: {e}")

    def set_secret(
        self, path: str, data: dict[str, Any], mount_point: str | None = None
    ) -> None:
        """
        Store a secret in Vault.

        Args:
            path: Secret path
            data: Secret data
            mount_point: Mount point (defaults to configured mount)
        """
        if not self._client:
            raise VaultConnectionError("Client not initialized")

        mount = mount_point or self.config.mount_point
        full_path = f"{mount}/{path}"

        try:
            # Try KV v2 first, then KV v1
            try:
                self._client.secrets.kv.v2.create_or_update_secret(
                    path=path, secret=data, mount_point=mount
                )
            except InvalidRequest:
                # Fallback to KV v1
                self._client.secrets.kv.v1.create_or_update_secret(
                    path=path, secret=data, mount_point=mount
                )

            # Update cache
            self._cache_secret(full_path, data)
            logger.debug(f"Stored secret at {full_path}")

        except VaultError as e:
            logger.error(f"Failed to store secret {full_path}: {e}")
            raise VaultClientError(f"Failed to store secret: {e}")

    def get_database_credentials(
        self, role_name: str = "readonly"
    ) -> DatabaseCredentials | None:
        """
        Get dynamic database credentials.

        Args:
            role_name: Database role name

        Returns:
            Database credentials with lease information
        """
        if not self._client:
            raise VaultConnectionError("Client not initialized")

        try:
            response = self._client.secrets.database.generate_credentials(
                name=role_name, mount_point=self.config.database_mount
            )

            data = response["data"]
            lease_info = response

            credentials = DatabaseCredentials(
                username=data["username"],
                password=data["password"],
                lease_id=lease_info["lease_id"],
                lease_duration=lease_info["lease_duration"],
                renewable=lease_info["renewable"],
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow()
                + timedelta(seconds=lease_info["lease_duration"]),
            )

            self._db_credentials = credentials
            logger.info(f"Generated database credentials for role {role_name}")
            return credentials

        except VaultError as e:
            logger.error(f"Failed to generate database credentials: {e}")
            raise VaultClientError(f"Failed to generate database credentials: {e}")

    def encrypt(self, plaintext: str, key_name: str = "app-key") -> str:
        """
        Encrypt data using Vault Transit engine.

        Args:
            plaintext: Data to encrypt
            key_name: Transit key name

        Returns:
            Encrypted ciphertext
        """
        if not self._client:
            raise VaultConnectionError("Client not initialized")

        try:
            response = self._client.secrets.transit.encrypt_data(
                name=key_name,
                plaintext=plaintext,
                mount_point=self.config.transit_mount,
            )

            return response["data"]["ciphertext"]

        except VaultError as e:
            logger.error(f"Failed to encrypt data: {e}")
            raise VaultClientError(f"Encryption failed: {e}")

    def decrypt(self, ciphertext: str, key_name: str = "app-key") -> str:
        """
        Decrypt data using Vault Transit engine.

        Args:
            ciphertext: Encrypted data
            key_name: Transit key name

        Returns:
            Decrypted plaintext
        """
        if not self._client:
            raise VaultConnectionError("Client not initialized")

        try:
            response = self._client.secrets.transit.decrypt_data(
                name=key_name,
                ciphertext=ciphertext,
                mount_point=self.config.transit_mount,
            )

            return response["data"]["plaintext"]

        except VaultError as e:
            logger.error(f"Failed to decrypt data: {e}")
            raise VaultClientError(f"Decryption failed: {e}")

    def _cache_secret(
        self, path: str, data: dict[str, Any], metadata: dict[str, Any] | None = None
    ):
        """Cache secret with metadata."""
        with self._lock:
            self._secret_cache[path] = data.copy()

            # Store metadata for cache expiration
            ttl = None
            if metadata:
                ttl = metadata.get("ttl")

            self._cache_metadata[path] = SecretMetadata(
                path=path,
                version=metadata.get("version", 1) if metadata else 1,
                created_time=datetime.utcnow(),
                deletion_time=None,
                destroyed=False,
                ttl=ttl,
            )

    def _is_cache_expired(self, metadata: SecretMetadata) -> bool:
        """Check if cached secret has expired."""
        if metadata.ttl:
            expiry_time = metadata.created_time + timedelta(seconds=metadata.ttl)
            return datetime.utcnow() > expiry_time

        # Default cache expiry: 5 minutes
        default_expiry = metadata.created_time + timedelta(minutes=5)
        return datetime.utcnow() > default_expiry

    def clear_cache(self, path: str | None = None):
        """Clear secret cache."""
        with self._lock:
            if path:
                self._secret_cache.pop(path, None)
                self._cache_metadata.pop(path, None)
                logger.debug(f"Cleared cache for {path}")
            else:
                self._secret_cache.clear()
                self._cache_metadata.clear()
                logger.debug("Cleared all cached secrets")

    def close(self):
        """Clean up resources and stop renewal thread."""
        logger.info("Closing Vault client")
        self._stop_renewal.set()

        if self._renewal_thread and self._renewal_thread.is_alive():
            self._renewal_thread.join(timeout=5)

        self.clear_cache()
        self._client = None


# Global Vault client instance
_vault_client: VaultClient | None = None


def get_vault_client() -> VaultClient:
    """Get the global Vault client instance."""
    global _vault_client
    if _vault_client is None:
        _vault_client = VaultClient()
        _vault_client.initialize()
    return _vault_client


def vault_secret(path: str, mount_point: str | None = None, cache: bool = True):
    """
    Decorator for injecting Vault secrets into function parameters.

    Usage:
        @vault_secret("database/config", cache=True)
        def get_db_connection(secret):
            return create_connection(
                host=secret["host"],
                user=secret["username"],
                password=secret["password"]
            )
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            client = get_vault_client()
            secret = client.get_secret(path, mount_point, use_cache=cache)

            if not secret:
                raise VaultSecretNotFoundError(f"Secret not found: {path}")

            return func(secret, *args, **kwargs)

        return wrapper

    return decorator
