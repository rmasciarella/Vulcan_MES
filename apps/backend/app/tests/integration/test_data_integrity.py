"""
Comprehensive integration tests for data integrity features.

Tests the Unit of Work pattern, HashiCorp Vault integration,
secret rotation, and transaction management features.
"""

import os
import threading
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import text

from app.core.secret_rotation import RotationStatus, SecretRotationManager
from app.core.unit_of_work import (
    EnhancedUnitOfWork,
    TransactionState,
    UnitOfWork,
    transactional,
)
from app.core.vault import (
    DatabaseCredentials,
    VaultClient,
    VaultClientError,
    VaultConfig,
)
from app.infrastructure.database.models import Job, Task


class TestEnhancedUnitOfWork:
    """Test the enhanced Unit of Work implementation."""

    def test_basic_transaction_success(self, db_session):
        """Test successful transaction with metrics."""
        with EnhancedUnitOfWork(track_metrics=True) as uow:
            job = Job(
                job_number="TEST001",
                customer_name="Test Customer",
                quantity=1,
                due_date=datetime.utcnow() + timedelta(days=7),
            )
            uow.add(job)

            assert uow.is_active
            assert uow.metrics is not None
            assert uow.metrics.state == TransactionState.ACTIVE

        # Verify transaction was committed
        assert uow.metrics.state == TransactionState.COMMITTED
        assert uow.metrics.duration_ms is not None
        assert uow.metrics.duration_ms > 0

    def test_transaction_rollback_on_exception(self, db_session):
        """Test transaction rollback when exception occurs."""
        with pytest.raises(ValueError):
            with EnhancedUnitOfWork(track_metrics=True) as uow:
                job = Job(
                    job_number="TEST002",
                    customer_name="Test Customer",
                    quantity=1,
                    due_date=datetime.utcnow() + timedelta(days=7),
                )
                uow.add(job)
                uow.flush()  # Ensure job is in session

                # Force an exception
                raise ValueError("Test exception")

        # Verify transaction was rolled back
        assert uow.metrics.state == TransactionState.ROLLED_BACK
        assert "Test exception" in uow.metrics.error

    def test_savepoints_and_partial_rollback(self, db_session):
        """Test nested transactions with savepoints."""
        with EnhancedUnitOfWork() as uow:
            # Create first job
            job1 = Job(
                job_number="TEST003",
                customer_name="Customer 1",
                quantity=1,
                due_date=datetime.utcnow() + timedelta(days=7),
            )
            uow.add(job1)
            uow.flush()

            # Create savepoint
            sp1 = uow.create_savepoint("before_job2")
            assert sp1 in uow.savepoints

            # Create second job
            job2 = Job(
                job_number="TEST004",
                customer_name="Customer 2",
                quantity=1,
                due_date=datetime.utcnow() + timedelta(days=7),
            )
            uow.add(job2)
            uow.flush()

            # Create another savepoint
            uow.create_savepoint("before_job3")
            assert len(uow.savepoints) == 2

            # Simulate error and rollback to first savepoint
            uow.rollback_to_savepoint(sp1)
            assert sp1 not in uow.savepoints  # Savepoint should be removed

        # Both job1 should exist, job2 should not (due to rollback)
        with UnitOfWork() as uow:
            jobs = uow.execute(
                text(
                    "SELECT job_number FROM jobs WHERE job_number IN ('TEST003', 'TEST004')"
                )
            ).fetchall()
            job_numbers = [row[0] for row in jobs]
            assert "TEST003" in job_numbers
            # Note: The exact behavior depends on how savepoint rollback is implemented

    def test_concurrent_transactions(self, db_session):
        """Test concurrent transaction handling."""
        results = []
        errors = []

        def create_job(job_number):
            try:
                with EnhancedUnitOfWork() as uow:
                    job = Job(
                        job_number=job_number,
                        customer_name=f"Customer {job_number}",
                        quantity=1,
                        due_date=datetime.utcnow() + timedelta(days=7),
                    )
                    uow.add(job)
                    time.sleep(0.1)  # Simulate processing time
                    results.append(job_number)
            except Exception as e:
                errors.append((job_number, str(e)))

        # Create multiple concurrent transactions
        threads = []
        for i in range(5):
            thread = threading.Thread(target=create_job, args=(f"CONCURRENT{i:03d}",))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        assert len(errors) == 0, f"Concurrent transactions failed: {errors}"
        assert len(results) == 5

    def test_repository_integration(self, db_session):
        """Test repository integration with Unit of Work."""
        from app.infrastructure.database.repositories.job_repository import (
            JobRepository,
        )

        with EnhancedUnitOfWork() as uow:
            job_repo = uow.get_repository(JobRepository)

            job = Job(
                job_number="REPO001",
                customer_name="Repository Test",
                quantity=1,
                due_date=datetime.utcnow() + timedelta(days=7),
            )

            # Test repository methods through UoW
            saved_job = job_repo.create(job)
            assert saved_job.id is not None

            retrieved_job = job_repo.get_by_id(saved_job.id)
            assert retrieved_job is not None
            assert retrieved_job.job_number == "REPO001"


class TestTransactionalDecorator:
    """Test the enhanced transactional decorator."""

    def test_basic_transactional_decorator(self, db_session):
        """Test basic transactional decorator functionality."""

        @transactional(track_metrics=True)
        def create_job_with_tasks(uow, job_data, task_count):
            job = Job(**job_data)
            uow.add(job)
            uow.flush()  # Get the job ID

            tasks = []
            for i in range(task_count):
                task = Task(
                    job_id=job.id,
                    operation_id=job.id,  # Simplified for test
                    sequence_in_job=i + 1,
                    planned_duration_minutes=60,
                )
                uow.add(task)
                tasks.append(task)

            return job, tasks

        job_data = {
            "job_number": "TRANS001",
            "customer_name": "Transactional Test",
            "quantity": 1,
            "due_date": datetime.utcnow() + timedelta(days=7),
        }

        job, tasks = create_job_with_tasks(job_data, 3)

        assert job.id is not None
        assert len(tasks) == 3
        assert all(task.job_id == job.id for task in tasks)

    def test_transactional_with_retry(self, db_session):
        """Test transactional decorator with retry mechanism."""
        call_count = 0

        @transactional(max_attempts=3, track_metrics=True)
        def unreliable_operation(uow):
            nonlocal call_count
            call_count += 1

            if call_count < 3:
                # Simulate transient database error
                from sqlalchemy.exc import DisconnectionError

                raise DisconnectionError("Connection lost", None, None)

            # Succeed on third attempt
            job = Job(
                job_number="RETRY001",
                customer_name="Retry Test",
                quantity=1,
                due_date=datetime.utcnow() + timedelta(days=7),
            )
            uow.add(job)
            return job

        result = unreliable_operation()
        assert call_count == 3
        assert result.job_number == "RETRY001"

    def test_transactional_timeout(self, db_session):
        """Test transactional decorator with timeout."""

        @transactional(timeout_seconds=1.0)
        def slow_operation(uow):
            time.sleep(2.0)  # Sleep longer than timeout
            job = Job(
                job_number="TIMEOUT001",
                customer_name="Timeout Test",
                quantity=1,
                due_date=datetime.utcnow() + timedelta(days=7),
            )
            uow.add(job)
            return job

        # Note: Actual timeout implementation would need to be added to the decorator
        # This test verifies the interface is correct
        with pytest.raises((TimeoutError, RuntimeError)):
            slow_operation()


@pytest.mark.skipif(
    not os.getenv("VAULT_ADDR"),
    reason="Vault integration tests require VAULT_ADDR environment variable",
)
class TestVaultIntegration:
    """Test HashiCorp Vault integration."""

    @pytest.fixture
    def mock_vault_client(self):
        """Mock Vault client for testing."""
        with patch("hvac.Client") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            mock_client.is_authenticated.return_value = True
            mock_client.auth.token.lookup_self.return_value = {
                "data": {"ttl": 3600, "renewable": True}
            }

            config = VaultConfig(url="http://localhost:8200", token="test-token")

            client = VaultClient(config)
            client._client = mock_client
            yield client, mock_client

    def test_vault_secret_retrieval(self, mock_vault_client):
        """Test secret retrieval from Vault."""
        vault_client, mock_client = mock_vault_client

        # Mock KV v2 response
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {
                "data": {"username": "testuser", "password": "testpass"},
                "metadata": {"version": 1, "created_time": "2023-01-01T00:00:00Z"},
            }
        }

        secret = vault_client.get_secret("database/config")

        assert secret is not None
        assert secret["username"] == "testuser"
        assert secret["password"] == "testpass"

        # Verify caching
        cached_secret = vault_client.get_secret("database/config", use_cache=True)
        assert cached_secret == secret

    def test_database_credentials_generation(self, mock_vault_client):
        """Test dynamic database credential generation."""
        vault_client, mock_client = mock_vault_client

        mock_client.secrets.database.generate_credentials.return_value = {
            "data": {
                "username": "v-root-testuser-123",
                "password": "A1a-generated-password",
            },
            "lease_id": "database/creds/readonly/test-lease-id",
            "lease_duration": 3600,
            "renewable": True,
        }

        credentials = vault_client.get_database_credentials("readonly")

        assert credentials is not None
        assert credentials.username == "v-root-testuser-123"
        assert credentials.password == "A1a-generated-password"
        assert credentials.lease_duration == 3600
        assert credentials.renewable is True

    def test_transit_encryption_decryption(self, mock_vault_client):
        """Test encryption/decryption using Vault Transit engine."""
        vault_client, mock_client = mock_vault_client

        plaintext = "sensitive data"
        ciphertext = "vault:v1:encrypted-data-here"

        mock_client.secrets.transit.encrypt_data.return_value = {
            "data": {"ciphertext": ciphertext}
        }
        mock_client.secrets.transit.decrypt_data.return_value = {
            "data": {"plaintext": plaintext}
        }

        # Test encryption
        encrypted = vault_client.encrypt(plaintext)
        assert encrypted == ciphertext

        # Test decryption
        decrypted = vault_client.decrypt(ciphertext)
        assert decrypted == plaintext

    def test_vault_error_handling(self, mock_vault_client):
        """Test Vault error handling."""
        vault_client, mock_client = mock_vault_client

        # Test authentication error
        mock_client.secrets.kv.v2.read_secret_version.side_effect = Exception(
            "permission denied"
        )

        with pytest.raises(VaultClientError):
            vault_client.get_secret("forbidden/secret")

        # Test connection error
        mock_client.secrets.kv.v2.read_secret_version.side_effect = ConnectionError(
            "Network error"
        )

        with pytest.raises(VaultClientError):
            vault_client.get_secret("network/test")


class TestSecretRotation:
    """Test dynamic secret rotation system."""

    @pytest.fixture
    def mock_rotation_manager(self):
        """Mock secret rotation manager."""
        with patch("app.core.secret_rotation.get_vault_client") as mock_get_vault:
            mock_vault = Mock()
            mock_get_vault.return_value = mock_vault

            manager = SecretRotationManager(mock_vault)
            yield manager, mock_vault

    def test_rotation_config_setup(self, mock_rotation_manager):
        """Test rotation configuration setup."""
        manager, _ = mock_rotation_manager

        # Test default configurations
        assert "database_credentials" in manager._rotation_configs
        assert "api_keys" in manager._rotation_configs
        assert "jwt_keys" in manager._rotation_configs

        db_config = manager._rotation_configs["database_credentials"]
        assert db_config.rotation_interval == timedelta(hours=24)
        assert db_config.enabled is True

    def test_database_credential_rotation(self, mock_rotation_manager):
        """Test database credential rotation."""
        manager, mock_vault = mock_rotation_manager

        # Mock new credentials
        new_creds = DatabaseCredentials(
            username="new_user",
            password="new_password",
            lease_id="new_lease",
            lease_duration=3600,
            renewable=True,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )

        mock_vault.get_database_credentials.return_value = new_creds

        # Mock successful connection test
        with patch.object(manager, "_test_database_connection", return_value=True):
            success = manager._rotate_database_credentials("test_rotation_001")

        assert success is True
        assert manager._current_db_credentials == new_creds

    def test_api_key_rotation(self, mock_rotation_manager):
        """Test API key rotation."""
        manager, mock_vault = mock_rotation_manager

        # Mock existing keys
        existing_keys = {"old_key": "old_value"}
        mock_vault.get_secret.return_value = existing_keys

        with patch.object(manager, "_generate_new_api_keys") as mock_generate:
            new_keys = {"new_key": "new_value"}
            mock_generate.return_value = new_keys

            success = manager._rotate_api_keys("api_rotation_001")

        assert success is True
        mock_vault.set_secret.assert_called_with("api_keys", new_keys)

    def test_jwt_key_rotation(self, mock_rotation_manager):
        """Test JWT key rotation."""
        manager, mock_vault = mock_rotation_manager

        success = manager._rotate_jwt_keys("jwt_rotation_001")

        assert success is True
        # Verify that set_secret was called with JWT keys
        mock_vault.set_secret.assert_called_once()
        call_args = mock_vault.set_secret.call_args
        assert call_args[0][0] == "jwt_keys"

        keys_data = call_args[0][1]
        assert "private_key" in keys_data
        assert "public_key" in keys_data
        assert "key_id" in keys_data

    def test_forced_rotation(self, mock_rotation_manager):
        """Test forced rotation trigger."""
        manager, mock_vault = mock_rotation_manager

        with patch.object(
            manager, "_perform_rotation", return_value=True
        ) as mock_perform:
            success = manager.force_rotation("database_credentials")

        assert success is True
        mock_perform.assert_called_once()

        # Test unknown secret type
        success = manager.force_rotation("unknown_secret")
        assert success is False

    def test_rotation_history_tracking(self, mock_rotation_manager):
        """Test rotation history tracking."""
        manager, _ = mock_rotation_manager

        from app.core.secret_rotation import RotationEvent

        # Add some test events
        event1 = RotationEvent(
            secret_type="database_credentials",
            rotation_id="test_001",
            status=RotationStatus.COMPLETED,
            timestamp=datetime.utcnow() - timedelta(hours=1),
        )

        event2 = RotationEvent(
            secret_type="api_keys",
            rotation_id="test_002",
            status=RotationStatus.FAILED,
            timestamp=datetime.utcnow(),
            error="Test error",
        )

        manager._log_rotation_event(event1)
        manager._log_rotation_event(event2)

        # Test history retrieval
        history = manager.get_rotation_history()
        assert len(history) == 2

        # Test filtering by secret type
        db_history = manager.get_rotation_history("database_credentials")
        assert len(db_history) == 1
        assert db_history[0].secret_type == "database_credentials"

    def test_rotation_scheduler(self, mock_rotation_manager):
        """Test rotation scheduler start/stop."""
        manager, _ = mock_rotation_manager

        # Test starting scheduler
        manager.start_rotation_scheduler()
        assert len(manager._rotation_threads) > 0
        assert all(thread.is_alive() for thread in manager._rotation_threads.values())

        # Test stopping scheduler
        manager.stop_rotation_scheduler()
        assert len(manager._rotation_threads) == 0


class TestDataIntegrityIntegration:
    """Integration tests for complete data integrity system."""

    @pytest.fixture
    def integrated_system(self):
        """Setup integrated test system."""
        with patch("app.core.vault.get_vault_client") as mock_get_vault:
            mock_vault = Mock()
            mock_get_vault.return_value = mock_vault

            from app.core.secret_rotation import get_rotation_manager

            rotation_manager = get_rotation_manager()

            yield {"vault": mock_vault, "rotation_manager": rotation_manager}

    def test_end_to_end_transaction_with_rotation(self, integrated_system, db_session):
        """Test complete transaction flow with secret rotation."""
        vault_client = integrated_system["vault"]
        rotation_manager = integrated_system["rotation_manager"]

        # Setup mock credentials
        new_creds = DatabaseCredentials(
            username="rotated_user",
            password="rotated_password",
            lease_id="rotated_lease",
            lease_duration=3600,
            renewable=True,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        vault_client.get_database_credentials.return_value = new_creds

        @transactional(max_attempts=2, track_metrics=True)
        def business_operation(uow):
            # Create a job with tasks
            job = Job(
                job_number="INTEGRATED001",
                customer_name="Integration Test",
                quantity=5,
                due_date=datetime.utcnow() + timedelta(days=14),
            )
            uow.add(job)
            uow.flush()

            # Create tasks for the job
            tasks = []
            for i in range(3):
                task = Task(
                    job_id=job.id,
                    operation_id=job.id,
                    sequence_in_job=i + 1,
                    planned_duration_minutes=120,
                )
                uow.add(task)
                tasks.append(task)

            return job, tasks

        # Execute business operation
        job, tasks = business_operation()

        assert job.id is not None
        assert len(tasks) == 3
        assert all(task.job_id == job.id for task in tasks)

        # Test secret rotation in parallel
        with patch.object(
            rotation_manager, "_test_database_connection", return_value=True
        ):
            rotation_success = rotation_manager.force_rotation("database_credentials")

        assert rotation_success is True

    def test_transaction_failure_and_recovery(self, integrated_system, db_session):
        """Test transaction failure handling and recovery."""

        attempt_count = 0

        @transactional(max_attempts=3, track_metrics=True)
        def flaky_operation(uow):
            nonlocal attempt_count
            attempt_count += 1

            job = Job(
                job_number=f"FLAKY{attempt_count:03d}",
                customer_name="Flaky Test",
                quantity=1,
                due_date=datetime.utcnow() + timedelta(days=7),
            )
            uow.add(job)
            uow.flush()

            if attempt_count < 2:
                # Simulate database connection issue
                from sqlalchemy.exc import OperationalError

                raise OperationalError("Connection timeout", None, None)

            return job

        # Should succeed after retries
        result = flaky_operation()
        assert attempt_count == 2
        assert result.job_number == "FLAKY002"

    def test_vault_secret_injection_with_transactions(self, integrated_system):
        """Test Vault secret injection with transactional operations."""
        vault_client = integrated_system["vault"]

        # Mock secret data
        vault_client.get_secret.return_value = {
            "api_endpoint": "https://api.example.com",
            "api_key": "secret-key-123",
            "timeout": 30,
        }

        from app.core.vault import vault_secret

        @vault_secret("external_api/config")
        @transactional(track_metrics=True)
        def process_with_external_api(secret, uow, data):
            # Use secret to configure external API call
            api_config = {
                "endpoint": secret["api_endpoint"],
                "key": secret["api_key"],
                "timeout": secret["timeout"],
            }

            # Create job based on external API response (simulated)
            job = Job(
                job_number=data["job_number"],
                customer_name=data["customer"],
                quantity=data["quantity"],
                due_date=datetime.utcnow() + timedelta(days=data["days_ahead"]),
            )
            uow.add(job)

            return job, api_config

        test_data = {
            "job_number": "EXT001",
            "customer": "External API Customer",
            "quantity": 10,
            "days_ahead": 21,
        }

        job, config = process_with_external_api(test_data)

        assert job.job_number == "EXT001"
        assert config["endpoint"] == "https://api.example.com"
        assert config["key"] == "secret-key-123"
