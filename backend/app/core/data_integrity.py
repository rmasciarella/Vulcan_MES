"""
Data integrity system configuration and initialization.

This module provides centralized configuration and initialization
for all data integrity features including Unit of Work, Vault integration,
secret rotation, and transaction management.
"""

import logging
import os
from contextlib import asynccontextmanager, contextmanager
from typing import Any

from fastapi import FastAPI

from app.core.secret_rotation import (
    RotationConfig,
    SecretRotationManager,
    get_rotation_manager,
)
from app.core.unit_of_work import (
    EnhancedUnitOfWork,
    configure_unit_of_work,
    get_unit_of_work_manager,
)
from app.core.vault import VaultClient, VaultClientError, VaultConfig, get_vault_client

logger = logging.getLogger(__name__)


class DataIntegrityConfig:
    """Configuration for data integrity system."""

    def __init__(self):
        # Vault configuration
        self.vault_enabled = os.getenv("VAULT_ENABLED", "false").lower() == "true"
        self.vault_addr = os.getenv("VAULT_ADDR", "http://localhost:8200")
        self.vault_token = os.getenv("VAULT_TOKEN")
        self.vault_auth_method = os.getenv("VAULT_AUTH_METHOD", "token")

        # Secret rotation configuration
        self.rotation_enabled = (
            os.getenv("SECRET_ROTATION_ENABLED", "false").lower() == "true"
        )
        self.db_credential_rotation_hours = int(
            os.getenv("DB_CREDENTIAL_ROTATION_HOURS", "24")
        )
        self.api_key_rotation_days = int(os.getenv("API_KEY_ROTATION_DAYS", "7"))
        self.jwt_key_rotation_days = int(os.getenv("JWT_KEY_ROTATION_DAYS", "30"))

        # Transaction configuration
        self.default_transaction_timeout = int(
            os.getenv("DEFAULT_TRANSACTION_TIMEOUT", "300")
        )
        self.default_retry_attempts = int(os.getenv("DEFAULT_RETRY_ATTEMPTS", "3"))
        self.metrics_enabled = (
            os.getenv("TRANSACTION_METRICS_ENABLED", "true").lower() == "true"
        )

        # Health check configuration
        self.health_check_enabled = (
            os.getenv("DATA_INTEGRITY_HEALTH_CHECK", "true").lower() == "true"
        )
        self.health_check_interval = int(
            os.getenv("HEALTH_CHECK_INTERVAL", "300")
        )  # 5 minutes


class DataIntegritySystem:
    """
    Central system for managing data integrity features.

    Coordinates Unit of Work, Vault, and Secret Rotation systems.
    """

    def __init__(self, config: DataIntegrityConfig | None = None):
        self.config = config or DataIntegrityConfig()
        self._vault_client: VaultClient | None = None
        self._rotation_manager: SecretRotationManager | None = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the data integrity system."""
        if self._initialized:
            logger.warning("Data integrity system already initialized")
            return

        logger.info("Initializing data integrity system")

        try:
            # Initialize Vault client if enabled
            if self.config.vault_enabled:
                await self._initialize_vault()
            else:
                logger.info("Vault integration disabled")

            # Initialize secret rotation if enabled
            if self.config.rotation_enabled:
                await self._initialize_secret_rotation()
            else:
                logger.info("Secret rotation disabled")

            # Configure Unit of Work system
            self._configure_unit_of_work()

            self._initialized = True
            logger.info("Data integrity system initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize data integrity system: {e}")
            raise

    async def _initialize_vault(self) -> None:
        """Initialize Vault client."""
        try:
            vault_config = VaultConfig(
                url=self.config.vault_addr,
                token=self.config.vault_token,
                auth_method=self.config.vault_auth_method,
                verify_ssl=not os.getenv("VAULT_SKIP_VERIFY", "false").lower()
                == "true",
            )

            self._vault_client = VaultClient(vault_config)
            self._vault_client.initialize()

            # Perform initial health check
            health = self._vault_client.health_check()
            logger.info(f"Vault health check passed: {health}")

        except VaultClientError as e:
            if self.config.vault_enabled:
                logger.error(f"Vault initialization failed: {e}")
                raise
            else:
                logger.warning(f"Vault connection failed but not required: {e}")

    async def _initialize_secret_rotation(self) -> None:
        """Initialize secret rotation manager."""
        try:
            self._rotation_manager = SecretRotationManager(self._vault_client)

            # Configure rotation schedules
            from datetime import timedelta

            # Database credentials rotation
            db_config = RotationConfig(
                secret_type="database_credentials",
                rotation_interval=timedelta(
                    hours=self.config.db_credential_rotation_hours
                ),
                advance_warning=timedelta(minutes=30),
                enabled=True,
            )
            self._rotation_manager.configure_rotation("database_credentials", db_config)

            # API keys rotation
            api_config = RotationConfig(
                secret_type="api_keys",
                rotation_interval=timedelta(days=self.config.api_key_rotation_days),
                advance_warning=timedelta(hours=1),
                enabled=True,
            )
            self._rotation_manager.configure_rotation("api_keys", api_config)

            # JWT keys rotation
            jwt_config = RotationConfig(
                secret_type="jwt_keys",
                rotation_interval=timedelta(days=self.config.jwt_key_rotation_days),
                advance_warning=timedelta(days=1),
                enabled=True,
            )
            self._rotation_manager.configure_rotation("jwt_keys", jwt_config)

            # Start rotation scheduler
            self._rotation_manager.start_rotation_scheduler()

            logger.info("Secret rotation manager initialized and started")

        except Exception as e:
            logger.error(f"Secret rotation initialization failed: {e}")
            if self.config.rotation_enabled:
                raise

    def _configure_unit_of_work(self) -> None:
        """Configure Unit of Work system."""
        try:
            # Configure global Unit of Work manager
            configure_unit_of_work()
            logger.info("Unit of Work system configured")

        except Exception as e:
            logger.error(f"Unit of Work configuration failed: {e}")
            raise

    async def shutdown(self) -> None:
        """Shutdown the data integrity system."""
        logger.info("Shutting down data integrity system")

        try:
            # Stop secret rotation
            if self._rotation_manager:
                self._rotation_manager.stop_rotation_scheduler()
                logger.info("Secret rotation manager stopped")

            # Close Vault client
            if self._vault_client:
                self._vault_client.close()
                logger.info("Vault client closed")

            self._initialized = False
            logger.info("Data integrity system shutdown complete")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

    async def health_check(self) -> dict[str, Any]:
        """Perform comprehensive health check."""
        health_status = {
            "system_initialized": self._initialized,
            "timestamp": "datetime.utcnow().isoformat()",
            "components": {},
        }

        # Check Vault health
        if self._vault_client:
            try:
                vault_health = self._vault_client.health_check()
                health_status["components"]["vault"] = {
                    "status": "healthy",
                    "details": vault_health,
                }
            except Exception as e:
                health_status["components"]["vault"] = {
                    "status": "unhealthy",
                    "error": str(e),
                }
        else:
            health_status["components"]["vault"] = {"status": "disabled"}

        # Check secret rotation
        if self._rotation_manager:
            try:
                recent_events = self._rotation_manager.get_rotation_history(limit=5)
                health_status["components"]["secret_rotation"] = {
                    "status": "healthy",
                    "recent_rotations": len(recent_events),
                    "last_rotation": recent_events[0].timestamp.isoformat()
                    if recent_events
                    else None,
                }
            except Exception as e:
                health_status["components"]["secret_rotation"] = {
                    "status": "unhealthy",
                    "error": str(e),
                }
        else:
            health_status["components"]["secret_rotation"] = {"status": "disabled"}

        # Check Unit of Work system
        try:
            uow_manager = get_unit_of_work_manager()
            with uow_manager.transaction() as uow:
                # Simple connectivity test
                result = uow.session.execute("SELECT 1").scalar()
                assert result == 1

            health_status["components"]["unit_of_work"] = {
                "status": "healthy",
                "database_connectivity": True,
            }
        except Exception as e:
            health_status["components"]["unit_of_work"] = {
                "status": "unhealthy",
                "error": str(e),
            }

        # Determine overall status
        component_statuses = [
            comp.get("status", "unknown")
            for comp in health_status["components"].values()
        ]

        if any(status == "unhealthy" for status in component_statuses):
            health_status["overall_status"] = "unhealthy"
        elif all(status in ["healthy", "disabled"] for status in component_statuses):
            health_status["overall_status"] = "healthy"
        else:
            health_status["overall_status"] = "degraded"

        return health_status

    def get_vault_client(self) -> VaultClient | None:
        """Get the Vault client instance."""
        return self._vault_client

    def get_rotation_manager(self) -> SecretRotationManager | None:
        """Get the secret rotation manager."""
        return self._rotation_manager

    @property
    def is_initialized(self) -> bool:
        """Check if system is initialized."""
        return self._initialized


# Global system instance
_data_integrity_system: DataIntegritySystem | None = None


async def get_data_integrity_system() -> DataIntegritySystem:
    """Get the global data integrity system instance."""
    global _data_integrity_system
    if _data_integrity_system is None:
        _data_integrity_system = DataIntegritySystem()
        await _data_integrity_system.initialize()
    return _data_integrity_system


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager for data integrity system."""
    # Startup
    logger.info("Starting data integrity system")
    try:
        await get_data_integrity_system()
        yield
    finally:
        # Shutdown
        logger.info("Stopping data integrity system")
        if _data_integrity_system:
            await _data_integrity_system.shutdown()


# Dependency injection
async def get_vault_client() -> VaultClient | None:
    """Dependency for getting Vault client."""
    system = await get_data_integrity_system()
    return system.get_vault_client()


async def get_rotation_manager() -> SecretRotationManager | None:
    """Dependency for getting rotation manager."""
    system = await get_data_integrity_system()
    return system.get_rotation_manager()


def get_enhanced_uow() -> EnhancedUnitOfWork:
    """Dependency for getting enhanced Unit of Work."""
    return EnhancedUnitOfWork(track_metrics=True)


@contextmanager
def transaction_context(
    track_metrics: bool = True, timeout_seconds: float | None = None
):
    """
    Context manager for database transactions with full data integrity features.

    Usage:
        with transaction_context(track_metrics=True) as uow:
            job = Job(...)
            uow.add(job)
            # Transaction automatically committed on success
    """
    with EnhancedUnitOfWork(track_metrics=track_metrics) as uow:
        # Apply timeout if specified
        if timeout_seconds:
            # Implementation would depend on specific database driver
            pass

        yield uow


# Utility functions for common patterns
def with_vault_secret(secret_path: str, mount_point: str | None = None):
    """
    Decorator for injecting Vault secrets with error handling.

    Usage:
        @with_vault_secret("database/config")
        async def setup_database(secret_data: dict):
            # Use secret_data
            pass
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                system = await get_data_integrity_system()
                vault_client = system.get_vault_client()

                if not vault_client:
                    raise RuntimeError("Vault client not available")

                secret = vault_client.get_secret(secret_path, mount_point)
                if not secret:
                    raise ValueError(f"Secret not found: {secret_path}")

                return await func(secret, *args, **kwargs)

            except Exception as e:
                logger.error(f"Error retrieving Vault secret {secret_path}: {e}")
                raise

        return wrapper

    return decorator


async def force_secret_rotation(secret_type: str) -> bool:
    """Force immediate rotation of a secret type."""
    try:
        system = await get_data_integrity_system()
        rotation_manager = system.get_rotation_manager()

        if not rotation_manager:
            logger.error("Secret rotation manager not available")
            return False

        return rotation_manager.force_rotation(secret_type)

    except Exception as e:
        logger.error(f"Failed to force rotation for {secret_type}: {e}")
        return False


async def get_data_integrity_health() -> dict[str, Any]:
    """Get comprehensive health status for data integrity system."""
    try:
        system = await get_data_integrity_system()
        return await system.health_check()
    except Exception as e:
        return {
            "overall_status": "unhealthy",
            "error": str(e),
            "timestamp": "datetime.utcnow().isoformat()",
        }
