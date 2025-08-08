import secrets
import warnings
from typing import Annotated, Any, Literal

from pydantic import (
    AnyUrl,
    BeforeValidator,
    EmailStr,
    HttpUrl,
    PostgresDsn,
    computed_field,
    model_validator,
)
from pydantic_core import MultiHostUrl
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self


def parse_cors(v: Any) -> list[str] | str:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",")]
    elif isinstance(v, list | str):
        return v
    raise ValueError(v)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Use top level .env file (one level above ./backend/)
        env_file="../.env",
        env_ignore_empty=True,
        extra="ignore",
    )
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    # 60 minutes * 24 hours * 8 days = 8 days
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    FRONTEND_HOST: str = "http://localhost:5173"
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"

    # Feature flags
    USE_SUPABASE_AUTH: bool = False

    # Supabase Configuration (prefer new naming; keep legacy for compatibility)
    SUPABASE_URL: str | None = None
    SUPABASE_PUBLISHABLE_KEY: str | None = None
    SUPABASE_SECRET: str | None = None
    # Legacy envs (optional)
    SUPABASE_ANON_KEY: str | None = None
    SUPABASE_SERVICE_KEY: str | None = None
    SUPABASE_JWT_SECRET: str | None = None

    BACKEND_CORS_ORIGINS: Annotated[
        list[AnyUrl] | str, BeforeValidator(parse_cors)
    ] = []

    @computed_field  # type: ignore[prop-decorator]
    @property
    def all_cors_origins(self) -> list[str]:
        return [str(origin).rstrip("/") for origin in self.BACKEND_CORS_ORIGINS] + [
            self.FRONTEND_HOST
        ]

    PROJECT_NAME: str
    SENTRY_DSN: HttpUrl | None = None
    POSTGRES_SERVER: str
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = ""
    # Supabase specific settings
    SUPABASE_URL: str | None = None
    SUPABASE_KEY: str | None = None
    # JWKS endpoint is usually {SUPABASE_URL}/auth/v1/keys
    SUPABASE_JWKS_URL: str | None = None
    SUPABASE_JWKS_CACHE_SECONDS: int = 300  # 5 minutes
    DATABASE_URL: str | None = None  # Direct connection string (for Supabase)
    USE_SSL: bool = True  # Enable SSL for production databases

    @computed_field  # type: ignore[prop-decorator]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> PostgresDsn:
        # If DATABASE_URL is provided (e.g., from Supabase), use it directly
        if self.DATABASE_URL:
            # Parse the DATABASE_URL and ensure it uses psycopg driver
            if self.DATABASE_URL.startswith("postgresql://"):
                return self.DATABASE_URL.replace(
                    "postgresql://", "postgresql+psycopg://", 1
                )
            elif self.DATABASE_URL.startswith("postgres://"):
                return self.DATABASE_URL.replace(
                    "postgres://", "postgresql+psycopg://", 1
                )
            else:
                return self.DATABASE_URL

        # Otherwise, build from individual components
        return MultiHostUrl.build(
            scheme="postgresql+psycopg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def SQLALCHEMY_TEST_DATABASE_URI(self) -> PostgresDsn:
        """Test database URI with '_test' suffix."""
        test_db_name = f"{self.POSTGRES_DB}_test"
        return MultiHostUrl.build(
            scheme="postgresql+psycopg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=test_db_name,
        )

    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    SMTP_PORT: int = 587
    SMTP_HOST: str | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAILS_FROM_EMAIL: EmailStr | None = None
    EMAILS_FROM_NAME: EmailStr | None = None

    @model_validator(mode="after")
    def _set_default_emails_from(self) -> Self:
        if not self.EMAILS_FROM_NAME:
            self.EMAILS_FROM_NAME = self.PROJECT_NAME
        return self

    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 48

    @computed_field  # type: ignore[prop-decorator]
    @property
    def emails_enabled(self) -> bool:
        return bool(self.SMTP_HOST and self.EMAILS_FROM_EMAIL)

    EMAIL_TEST_USER: EmailStr = "test@example.com"
    FIRST_SUPERUSER: EmailStr
    FIRST_SUPERUSER_PASSWORD: str

    def _check_default_secret(self, var_name: str, value: str | None) -> None:
        if value == "changethis":
            message = (
                f'The value of {var_name} is "changethis", '
                "for security, please change it, at least for deployments."
            )
            if self.ENVIRONMENT == "local":
                warnings.warn(message, stacklevel=1)
            else:
                raise ValueError(message)

    @model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Self:
        self._check_default_secret("SECRET_KEY", self.SECRET_KEY)
        self._check_default_secret("POSTGRES_PASSWORD", self.POSTGRES_PASSWORD)
        self._check_default_secret(
            "FIRST_SUPERUSER_PASSWORD", self.FIRST_SUPERUSER_PASSWORD
        )

        # Map legacy/new Supabase keys for compatibility
        if self.SUPABASE_PUBLISHABLE_KEY and not self.SUPABASE_ANON_KEY:
            self.SUPABASE_ANON_KEY = self.SUPABASE_PUBLISHABLE_KEY
        if self.SUPABASE_SECRET and not self.SUPABASE_SERVICE_KEY:
            self.SUPABASE_SERVICE_KEY = self.SUPABASE_SECRET

        # Auto-populate SUPABASE_JWKS_URL if not explicitly set
        if self.SUPABASE_URL and not self.SUPABASE_JWKS_URL:
            self.SUPABASE_JWKS_URL = f"{self.SUPABASE_URL.rstrip('/')}/auth/v1/keys"

        return self

    # Redis Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str | None = None
    REDIS_SSL: bool = False
    REDIS_CACHE_TTL: int = 3600  # Default cache TTL in seconds
    REDIS_MAX_CONNECTIONS: int = 100

    @computed_field  # type: ignore[prop-decorator]
    @property
    def REDIS_URL(self) -> str:
        """Build Redis connection URL."""
        if self.REDIS_PASSWORD:
            auth = f":{self.REDIS_PASSWORD}@"
        else:
            auth = ""

        protocol = "rediss" if self.REDIS_SSL else "redis"
        return f"{protocol}://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # Celery Configuration
    CELERY_BROKER_URL: str | None = None
    CELERY_RESULT_BACKEND: str | None = None
    CELERY_TASK_TRACK_STARTED: bool = True
    CELERY_TASK_TIME_LIMIT: int = 1800  # 30 minutes
    CELERY_TASK_SOFT_TIME_LIMIT: int = 1500  # 25 minutes
    CELERY_WORKER_CONCURRENCY: int = 4
    CELERY_WORKER_PREFETCH_MULTIPLIER: int = 4

    @computed_field  # type: ignore[prop-decorator]
    @property
    def celery_broker_url(self) -> str:
        """Get Celery broker URL (defaults to Redis)."""
        return self.CELERY_BROKER_URL or self.REDIS_URL

    @computed_field  # type: ignore[prop-decorator]
    @property
    def celery_result_backend(self) -> str:
        """Get Celery result backend URL (defaults to Redis)."""
        return self.CELERY_RESULT_BACKEND or self.REDIS_URL

    # Database Read Replica Configuration
    DATABASE_READ_REPLICA_URL: str | None = None
    DATABASE_MAX_CONNECTIONS: int = 100
    DATABASE_POOL_SIZE: int = 20
    DATABASE_POOL_RECYCLE: int = 3600
    DATABASE_POOL_PRE_PING: bool = True

    @computed_field  # type: ignore[prop-decorator]
    @property
    def SQLALCHEMY_READ_REPLICA_URI(self) -> PostgresDsn | None:
        """Read replica database URI for read-only operations."""
        if not self.DATABASE_READ_REPLICA_URL:
            return None

        if self.DATABASE_READ_REPLICA_URL.startswith("postgresql://"):
            return self.DATABASE_READ_REPLICA_URL.replace(
                "postgresql://", "postgresql+psycopg://", 1
            )
        elif self.DATABASE_READ_REPLICA_URL.startswith("postgres://"):
            return self.DATABASE_READ_REPLICA_URL.replace(
                "postgres://", "postgresql+psycopg://", 1
            )
        else:
            return self.DATABASE_READ_REPLICA_URL

    # Performance Monitoring
    ENABLE_PERFORMANCE_MONITORING: bool = True
    PERFORMANCE_LOG_SLOW_QUERIES: bool = True
    PERFORMANCE_SLOW_QUERY_THRESHOLD: float = 1.0  # seconds
    ENABLE_REQUEST_PROFILING: bool = False
    REQUEST_PROFILING_SAMPLE_RATE: float = 0.1  # 10% of requests

    # Application Performance Settings
    ENABLE_RESPONSE_COMPRESSION: bool = True
    COMPRESSION_MINIMUM_SIZE: int = 500  # bytes
    ENABLE_CONNECTION_POOLING: bool = True

    # Cache Configuration
    CACHE_ENTITY_TTL: dict[str, int] = {
        "job": 3600,  # 1 hour
        "task": 3600,
        "operator": 7200,  # 2 hours
        "machine": 7200,
        "schedule": 1800,  # 30 minutes
        "production_zone": 7200,
    }
    CACHE_WARM_ON_STARTUP: bool = True
    CACHE_KEY_PREFIX: str = "vulcan:"

    # Observability Configuration
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # "json" or "console"
    LOG_SQL: bool = False
    ENABLE_METRICS: bool = True
    ENABLE_TRACING: bool = True
    METRICS_PORT: int = 8001

    # Alert Configuration
    ALERT_EMAIL_TO: str = "alerts@example.com"
    DBA_EMAIL: str = "dba@example.com"
    INFRA_EMAIL: str = "infrastructure@example.com"
    DEV_EMAIL: str = "development@example.com"
    SRE_EMAIL: str = "sre@example.com"
    SLACK_WEBHOOK_URL: str = ""
    GRAFANA_ADMIN_PASSWORD: str = "admin"

    # Health Check Configuration
    HEALTH_CHECK_TIMEOUT: int = 30  # seconds
    HEALTH_CHECK_REDIS: bool = True
    HEALTH_CHECK_FILESYSTEM: bool = True
    HEALTH_CHECK_EXTERNAL_APIS: bool = True

    # SLA and Performance Thresholds
    SLA_API_RESPONSE_TIME_P95: float = 2.0  # seconds
    SLA_API_ERROR_RATE_THRESHOLD: float = 5.0  # percentage
    SLA_SCHEDULER_OPTIMIZATION_TIMEOUT: float = 120.0  # seconds
    SLA_DATABASE_QUERY_TIMEOUT: float = 1.0  # seconds

    # Monitoring Intervals
    METRICS_SCRAPE_INTERVAL: int = 15  # seconds
    HEALTH_CHECK_INTERVAL: int = 30  # seconds
    LOG_RETENTION_DAYS: int = 30
    METRICS_RETENTION_DAYS: int = 90

    # Data Integrity Configuration
    # Vault Integration
    VAULT_ENABLED: bool = False
    VAULT_ADDR: str = "http://localhost:8200"
    VAULT_TOKEN: str | None = None
    VAULT_AUTH_METHOD: str = "token"
    VAULT_SKIP_VERIFY: bool = False
    VAULT_NAMESPACE: str | None = None
    VAULT_MOUNT_POINT: str = "secret"
    VAULT_DATABASE_MOUNT: str = "database"
    VAULT_TRANSIT_MOUNT: str = "transit"

    # Secret Rotation Configuration
    SECRET_ROTATION_ENABLED: bool = False
    DB_CREDENTIAL_ROTATION_HOURS: int = 24
    API_KEY_ROTATION_DAYS: int = 7
    JWT_KEY_ROTATION_DAYS: int = 30

    # Transaction Management
    DEFAULT_TRANSACTION_TIMEOUT: int = 300  # seconds
    DEFAULT_RETRY_ATTEMPTS: int = 3
    TRANSACTION_METRICS_ENABLED: bool = True
    ENABLE_SAVEPOINTS: bool = True
    MAX_SAVEPOINTS_PER_TRANSACTION: int = 10

    # Unit of Work Configuration
    UOW_DEFAULT_TRACK_METRICS: bool = True
    UOW_SLOW_TRANSACTION_THRESHOLD_MS: float = 1000.0
    UOW_ENABLE_QUERY_LOGGING: bool = False
    UOW_MAX_RETRY_ATTEMPTS: int = 3
    UOW_RETRY_BASE_DELAY: float = 0.1
    UOW_RETRY_MAX_DELAY: float = 10.0

    # Data Integrity Health Checks
    DATA_INTEGRITY_HEALTH_CHECK: bool = True
    VAULT_HEALTH_CHECK_INTERVAL: int = 300  # 5 minutes
    ROTATION_HEALTH_CHECK_INTERVAL: int = 900  # 15 minutes


settings = Settings()  # type: ignore
