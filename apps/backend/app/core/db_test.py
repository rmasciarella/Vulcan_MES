"""Test database configuration and utilities."""

from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings

# Use test database
test_engine = create_engine(
    str(settings.SQLALCHEMY_TEST_DATABASE_URI),
    echo=False,  # Set to True for debugging SQL queries during tests
)


def create_test_db() -> None:
    """Create all tables in test database."""
    SQLModel.metadata.create_all(test_engine)


def drop_test_db() -> None:
    """Drop all tables in test database."""
    SQLModel.metadata.drop_all(test_engine)


def get_test_session() -> Session:
    """Get a test database session."""
    return Session(test_engine)
