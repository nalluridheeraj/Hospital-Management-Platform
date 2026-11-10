from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from appointments.views import (
    HealthLivenessView,
    HealthReadinessView,
    PrometheusMetricsView,
    DashboardView,
)

urlpatterns = [
    # Interactive Web Testing Dashboard
    path("", DashboardView.as_view(), name="dashboard"),
    path("admin/", admin.site.urls),
    # Observability Probes
    path("health/liveness/", HealthLivenessView.as_view(), name="health-liveness"),
    path("health/readiness/", HealthReadinessView.as_view(), name="health-readiness"),
    path("metrics/", PrometheusMetricsView.as_view(), name="metrics"),
    # JWT Authentication Endpoints
    path("api/v1/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/v1/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # Appointments Domain API
    path("api/v1/", include("appointments.urls")),
]
