import pytest
from rest_framework.test import APIClient
from django.contrib.auth.models import User
from django.core.management import call_command


@pytest.fixture(scope="session", autouse=True)
def setup_database(django_db_setup, django_db_blocker):
    """Initializes and seeds the database before test sessions."""
    with django_db_blocker.unblock():
        call_command("seed_data", force=True)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_client(db):
    client = APIClient()
    response = client.post(
        "/api/v1/auth/token/",
        {"username": "admin", "password": "Admin@Password2026!"},
        format="json",
    )
    assert response.status_code == 200, response.data
    token = response.data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


@pytest.fixture
def doctor_client(db):
    client = APIClient()
    response = client.post(
        "/api/v1/auth/token/",
        {"username": "dr.smith", "password": "Doctor@Password2026!"},
        format="json",
    )
    assert response.status_code == 200, response.data
    token = response.data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


@pytest.fixture
def patient_client(db):
    client = APIClient()
    response = client.post(
        "/api/v1/auth/token/",
        {"username": "patient.john", "password": "Patient@Password2026!"},
        format="json",
    )
    assert response.status_code == 200, response.data
    token = response.data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client
