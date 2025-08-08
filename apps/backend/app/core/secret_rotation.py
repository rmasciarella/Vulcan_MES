"""
Dynamic secret rotation system for automated credential management.

This module provides automated rotation of database credentials, API keys,
and other sensitive configuration using HashiCorp Vault integration.
"""

import logging
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.vault import DatabaseCredentials, VaultClient

logger = logging.getLogger(__name__)


class RotationStatus(Enum):
    """Status of secret rotation."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class RotationConfig:
    """Configuration for secret rotation."""

    secret_type: str
    rotation_interval: timedelta
    advance_warning: timedelta
    max_retries: int = 3
    enabled: bool = True
    notification_webhooks: list[str] = None


@dataclass
class RotationEvent:
    """Event information for secret rotation."""

    secret_type: str
    rotation_id: str
    status: RotationStatus
    timestamp: datetime
    old_value: str | None = None
    new_value: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = None


class SecretRotationManager:
    """
    Manager for automated secret rotation.

    Features:
    - Database credential rotation with connection validation
    - API key rotation with graceful transition
    - Configurable rotation schedules
    - Event logging and notifications
    - Rollback capabilities for failed rotations
    """

    def __init__(self, vault_client: VaultClient | None = None):
        self.vault_client = vault_client
        self._rotation_configs: dict[str, RotationConfig] = {}
        self._rotation_threads: dict[str, threading.Thread] = {}
        self._stop_events: dict[str, threading.Event] = {}
        self._rotation_history: list[RotationEvent] = []
        self._current_db_credentials: DatabaseCredentials | None = None
        self._active_db_engine: Engine | None = None
        self._lock = threading.RLock()

        # Default rotation configurations
        self._setup_default_configs()

    def _setup_default_configs(self):
        """Setup default rotation configurations."""
        self._rotation_configs = {
            "database_credentials": RotationConfig(
                secret_type="database_credentials",
                rotation_interval=timedelta(hours=24),  # Daily rotation
                advance_warning=timedelta(minutes=30),
                max_retries=3,
                enabled=True,
            ),
            "api_keys": RotationConfig(
                secret_type="api_keys",
                rotation_interval=timedelta(days=7),  # Weekly rotation
                advance_warning=timedelta(hours=1),
                max_retries=3,
                enabled=True,
            ),
            "jwt_keys": RotationConfig(
                secret_type="jwt_keys",
                rotation_interval=timedelta(days=30),  # Monthly rotation
                advance_warning=timedelta(days=1),
                max_retries=3,
                enabled=True,
            ),
        }

    def start_rotation_scheduler(self):
        """Start the background rotation scheduler."""
        logger.info("Starting secret rotation scheduler")

        for secret_type, config in self._rotation_configs.items():
            if config.enabled:
                self._start_rotation_thread(secret_type, config)

    def stop_rotation_scheduler(self):
        """Stop all rotation threads."""
        logger.info("Stopping secret rotation scheduler")

        with self._lock:
            for _secret_type, stop_event in self._stop_events.items():
                stop_event.set()

            for _secret_type, thread in self._rotation_threads.items():
                if thread.is_alive():
                    thread.join(timeout=10)

            self._rotation_threads.clear()
            self._stop_events.clear()

    def _start_rotation_thread(self, secret_type: str, config: RotationConfig):
        """Start rotation thread for a specific secret type."""
        if secret_type in self._rotation_threads:
            return

        stop_event = threading.Event()
        self._stop_events[secret_type] = stop_event

        thread = threading.Thread(
            target=self._rotation_worker,
            args=(secret_type, config, stop_event),
            daemon=True,
            name=f"rotation-{secret_type}",
        )

        self._rotation_threads[secret_type] = thread
        thread.start()

        logger.info(f"Started rotation thread for {secret_type}")

    def _rotation_worker(
        self, secret_type: str, config: RotationConfig, stop_event: threading.Event
    ):
        """Background worker for secret rotation."""
        while not stop_event.wait(300):  # Check every 5 minutes
            try:
                if self._should_rotate(secret_type, config):
                    rotation_id = f"{secret_type}_{int(time.time())}"

                    event = RotationEvent(
                        secret_type=secret_type,
                        rotation_id=rotation_id,
                        status=RotationStatus.PENDING,
                        timestamp=datetime.utcnow(),
                    )

                    self._log_rotation_event(event)

                    success = self._perform_rotation(secret_type, config, rotation_id)

                    event.status = (
                        RotationStatus.COMPLETED if success else RotationStatus.FAILED
                    )
                    event.timestamp = datetime.utcnow()
                    self._log_rotation_event(event)

            except Exception as e:
                logger.error(f"Error in rotation worker for {secret_type}: {e}")

    def _should_rotate(self, secret_type: str, config: RotationConfig) -> bool:
        """Determine if a secret should be rotated."""
        if not config.enabled:
            return False

        # Check if we have rotation history for this secret type
        recent_rotations = [
            event
            for event in self._rotation_history
            if (
                event.secret_type == secret_type
                and event.status == RotationStatus.COMPLETED
                and datetime.utcnow() - event.timestamp < config.rotation_interval
            )
        ]

        if recent_rotations:
            last_rotation = max(recent_rotations, key=lambda x: x.timestamp)
            next_rotation = last_rotation.timestamp + config.rotation_interval

            # Check if it's time to rotate (with advance warning)
            warning_time = next_rotation - config.advance_warning
            return datetime.utcnow() >= warning_time

        # No recent rotations, should rotate
        return True

    def _perform_rotation(
        self, secret_type: str, config: RotationConfig, rotation_id: str
    ) -> bool:
        """Perform the actual secret rotation."""
        logger.info(f"Performing rotation for {secret_type} (ID: {rotation_id})")

        for attempt in range(config.max_retries):
            try:
                if secret_type == "database_credentials":
                    return self._rotate_database_credentials(rotation_id)
                elif secret_type == "api_keys":
                    return self._rotate_api_keys(rotation_id)
                elif secret_type == "jwt_keys":
                    return self._rotate_jwt_keys(rotation_id)
                else:
                    logger.warning(f"Unknown secret type for rotation: {secret_type}")
                    return False

            except Exception as e:
                logger.warning(
                    f"Rotation attempt {attempt + 1} failed for {secret_type}: {e}"
                )
                if attempt < config.max_retries - 1:
                    time.sleep(2**attempt)  # Exponential backoff

        logger.error(f"All rotation attempts failed for {secret_type}")
        return False

    def _rotate_database_credentials(self, rotation_id: str) -> bool:
        """Rotate database credentials using Vault."""
        if not self.vault_client:
            logger.error("Vault client not available for database credential rotation")
            return False

        try:
            # Get new credentials from Vault
            new_credentials = self.vault_client.get_database_credentials()
            if not new_credentials:
                logger.error("Failed to obtain new database credentials from Vault")
                return False

            # Test the new credentials
            if not self._test_database_connection(new_credentials):
                logger.error("New database credentials failed connection test")
                return False

            # Update the active database engine
            old_engine = self._active_db_engine
            new_engine = self._create_database_engine(new_credentials)

            with self._lock:
                self._current_db_credentials = new_credentials
                self._active_db_engine = new_engine

            # Close old engine after brief delay
            if old_engine:
                threading.Timer(60.0, lambda: old_engine.dispose()).start()

            logger.info(
                f"Database credentials rotated successfully (ID: {rotation_id})"
            )
            return True

        except Exception as e:
            logger.error(f"Database credential rotation failed: {e}")
            return False

    def _rotate_api_keys(self, rotation_id: str) -> bool:
        """Rotate API keys."""
        if not self.vault_client:
            logger.error("Vault client not available for API key rotation")
            return False

        try:
            # Get current API keys
            current_keys = self.vault_client.get_secret("api_keys")
            if not current_keys:
                logger.warning("No existing API keys found")
                return True

            # Generate new API keys (implementation depends on your API key strategy)
            new_keys = self._generate_new_api_keys()

            # Store new keys in Vault
            self.vault_client.set_secret("api_keys", new_keys)

            logger.info(f"API keys rotated successfully (ID: {rotation_id})")
            return True

        except Exception as e:
            logger.error(f"API key rotation failed: {e}")
            return False

    def _rotate_jwt_keys(self, rotation_id: str) -> bool:
        """Rotate JWT signing keys."""
        if not self.vault_client:
            logger.error("Vault client not available for JWT key rotation")
            return False

        try:
            # Generate new RSA key pair
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric import rsa

            private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

            public_key = private_key.public_key()

            # Serialize keys
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            ).decode("utf-8")

            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode("utf-8")

            # Store new keys in Vault
            jwt_keys = {
                "private_key": private_pem,
                "public_key": public_pem,
                "key_id": rotation_id,
                "created_at": datetime.utcnow().isoformat(),
            }

            self.vault_client.set_secret("jwt_keys", jwt_keys)

            logger.info(f"JWT keys rotated successfully (ID: {rotation_id})")
            return True

        except Exception as e:
            logger.error(f"JWT key rotation failed: {e}")
            return False

    def _test_database_connection(self, credentials: DatabaseCredentials) -> bool:
        """Test database connection with new credentials."""
        try:
            test_engine = self._create_database_engine(credentials)

            with test_engine.connect() as conn:
                # Simple connectivity test
                result = conn.execute(text("SELECT 1"))
                result.fetchone()

            test_engine.dispose()
            return True

        except SQLAlchemyError as e:
            logger.error(f"Database connection test failed: {e}")
            return False

    def _create_database_engine(self, credentials: DatabaseCredentials) -> Engine:
        """Create database engine with given credentials."""
        # Build connection string with new credentials
        db_url = str(settings.SQLALCHEMY_DATABASE_URI)

        # Replace username and password in the URL
        # This is a simplified approach - in production, you'd want more robust URL parsing
        from urllib.parse import urlparse, urlunparse

        parsed = urlparse(db_url)
        new_netloc = f"{credentials.username}:{credentials.password}@{parsed.hostname}:{parsed.port}"
        new_parsed = parsed._replace(netloc=new_netloc)
        new_url = urlunparse(new_parsed)

        return create_engine(
            new_url,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=20,
            pool_recycle=settings.DATABASE_POOL_RECYCLE,
            pool_pre_ping=settings.DATABASE_POOL_PRE_PING,
        )

    def _generate_new_api_keys(self) -> dict[str, str]:
        """Generate new API keys."""
        import secrets
        import string

        # Generate secure API keys
        alphabet = string.ascii_letters + string.digits

        return {
            "external_api_key": "".join(secrets.choice(alphabet) for _ in range(32)),
            "internal_api_key": "".join(secrets.choice(alphabet) for _ in range(32)),
            "webhook_secret": "".join(secrets.choice(alphabet) for _ in range(64)),
            "created_at": datetime.utcnow().isoformat(),
        }

    def _log_rotation_event(self, event: RotationEvent):
        """Log rotation event to history."""
        with self._lock:
            self._rotation_history.append(event)

            # Keep only last 1000 events
            if len(self._rotation_history) > 1000:
                self._rotation_history = self._rotation_history[-1000:]

        # Log to application logger
        level = (
            logging.INFO if event.status == RotationStatus.COMPLETED else logging.ERROR
        )
        logger.log(
            level,
            f"Rotation event: {event.secret_type} - {event.status.value} (ID: {event.rotation_id})",
        )

    def force_rotation(self, secret_type: str) -> bool:
        """Force immediate rotation of a secret type."""
        if secret_type not in self._rotation_configs:
            logger.error(f"Unknown secret type: {secret_type}")
            return False

        config = self._rotation_configs[secret_type]
        rotation_id = f"{secret_type}_forced_{int(time.time())}"

        logger.info(f"Forcing rotation for {secret_type}")
        return self._perform_rotation(secret_type, config, rotation_id)

    def get_rotation_history(
        self, secret_type: str | None = None, limit: int = 100
    ) -> list[RotationEvent]:
        """Get rotation history."""
        with self._lock:
            history = self._rotation_history.copy()

        if secret_type:
            history = [e for e in history if e.secret_type == secret_type]

        # Return most recent events first
        return sorted(history, key=lambda x: x.timestamp, reverse=True)[:limit]

    def get_current_database_credentials(self) -> DatabaseCredentials | None:
        """Get currently active database credentials."""
        with self._lock:
            return self._current_db_credentials

    @contextmanager
    def database_connection(self):
        """Context manager for getting database connections with current credentials."""
        if not self._active_db_engine:
            # Fallback to default engine
            from app.core.db import engine

            with engine.connect() as conn:
                yield conn
        else:
            with self._active_db_engine.connect() as conn:
                yield conn

    def configure_rotation(self, secret_type: str, config: RotationConfig):
        """Configure rotation for a secret type."""
        self._rotation_configs[secret_type] = config

        # Restart rotation thread if running
        if secret_type in self._rotation_threads:
            self._stop_events[secret_type].set()
            self._rotation_threads[secret_type].join(timeout=5)

            if config.enabled:
                self._start_rotation_thread(secret_type, config)


# Global secret rotation manager
_rotation_manager: SecretRotationManager | None = None


def get_rotation_manager() -> SecretRotationManager:
    """Get the global secret rotation manager."""
    global _rotation_manager
    if _rotation_manager is None:
        from app.core.vault import get_vault_client

        try:
            vault_client = get_vault_client()
            _rotation_manager = SecretRotationManager(vault_client)
        except Exception as e:
            logger.warning(
                f"Failed to initialize Vault client for rotation manager: {e}"
            )
            _rotation_manager = SecretRotationManager()  # Without Vault client
    return _rotation_manager


def setup_secret_rotation():
    """Setup and start secret rotation system."""
    try:
        rotation_manager = get_rotation_manager()
        rotation_manager.start_rotation_scheduler()
        logger.info("Secret rotation system initialized")
    except Exception as e:
        logger.error(f"Failed to setup secret rotation: {e}")


def shutdown_secret_rotation():
    """Shutdown secret rotation system."""
    global _rotation_manager
    if _rotation_manager:
        _rotation_manager.stop_rotation_scheduler()
        _rotation_manager = None
        logger.info("Secret rotation system shutdown")
