import pytest


@pytest.mark.django_db
def test_liveness_probe(api_client):
    """Verify that liveness probe returns HTTP 200 with service metadata."""
    response = api_client.get("/health/liveness/")
    assert response.status_code == 200
    assert response.data["status"] == "alive"
    assert "version" in response.data
    assert "timestamp" in response.data


@pytest.mark.django_db
def test_readiness_probe(api_client):
    """Verify that readiness probe checks database connectivity and returns HTTP 200."""
    response = api_client.get("/health/readiness/")
    assert response.status_code == 200
    assert response.data["status"] == "ready"
    assert "database" in response.data
    assert response.data["database"]["status"] == "healthy"


@pytest.mark.django_db
def test_prometheus_metrics(api_client):
    """Verify that Prometheus metrics exposition endpoint returns metrics text."""
    response = api_client.get("/metrics/")
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "django_hospital_http_requests_total" in content
    assert "django_hospital_appointment_operations_total" in content
