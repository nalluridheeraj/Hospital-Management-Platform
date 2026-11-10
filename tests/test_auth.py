import pytest


@pytest.mark.django_db
def test_jwt_token_obtain_success(api_client):
    """Verify that valid synthetic user credentials return access and refresh JWT tokens."""
    response = api_client.post(
        "/api/v1/auth/token/",
        {"username": "admin", "password": "Admin@Password2026!"},
        format="json",
    )
    assert response.status_code == 200
    assert "access" in response.data
    assert "refresh" in response.data


@pytest.mark.django_db
def test_jwt_token_obtain_invalid_credentials(api_client):
    """Verify rejection on incorrect password."""
    response = api_client.post(
        "/api/v1/auth/token/",
        {"username": "admin", "password": "WrongPassword999!"},
        format="json",
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_unauthenticated_request_rejected(api_client):
    """Verify unauthenticated requests to protected endpoints return 401."""
    response = api_client.get("/api/v1/appointments/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_rbac_admin_audit_logs_permission(patient_client, admin_client):
    """Verify that patient role is forbidden (403) from accessing admin audit logs,
    while admin is authorized (200).
    """
    forbidden_resp = patient_client.get("/api/v1/audit-logs/")
    assert forbidden_resp.status_code == 403

    authorized_resp = admin_client.get("/api/v1/audit-logs/")
    assert authorized_resp.status_code == 200
