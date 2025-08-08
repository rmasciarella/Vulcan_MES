from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import settings


def test_health_check(client: TestClient) -> None:
    """Test health check endpoint."""
    r = client.get(f"{settings.API_V1_STR}/utils/health-check/")
    assert r.status_code == 200
    assert r.json() is True


def test_test_email(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """Test email endpoint with superuser permissions."""
    with (
        patch("app.utils.send_email", return_value=None),
        patch("app.core.config.settings.SMTP_HOST", "smtp.example.com"),
        patch("app.core.config.settings.SMTP_USER", "admin@example.com"),
    ):
        email = "test@example.com"
        r = client.post(
            f"{settings.API_V1_STR}/utils/test-email/",
            headers=superuser_token_headers,
            params={"email_to": email},
        )
        assert r.status_code == 201
        assert r.json() == {"message": "Test email sent"}


def test_test_email_normal_user_insufficient_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    """Test that normal users cannot access test email endpoint."""
    email = "test@example.com"
    r = client.post(
        f"{settings.API_V1_STR}/utils/test-email/",
        headers=normal_user_token_headers,
        params={"email_to": email},
    )
    assert r.status_code == 403


def test_test_email_no_auth(client: TestClient) -> None:
    """Test that unauthenticated users cannot access test email endpoint."""
    email = "test@example.com"
    r = client.post(
        f"{settings.API_V1_STR}/utils/test-email/",
        params={"email_to": email},
    )
    assert r.status_code == 401
