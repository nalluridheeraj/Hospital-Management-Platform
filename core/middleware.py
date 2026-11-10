import json
import logging
import sys
import time
import uuid
from datetime import datetime

logger = logging.getLogger("django.access")


class StructuredLoggingMiddleware:
    """Middleware to inject correlation IDs, track execution latency,
    and emit structured JSON access logs for observability.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Extract or assign Correlation ID
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        request.correlation_id = correlation_id

        client_ip = (
            request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
            or request.META.get("REMOTE_ADDR", "unknown")
        )

        start_time = time.time()
        response = self.get_response(request)
        duration_ms = round((time.time() - start_time) * 1000, 2)

        # 2. Attach correlation header to response
        response["X-Correlation-ID"] = correlation_id

        # 3. Emit structured JSON log (skip spamming frequent liveness / metrics probes)
        if request.path not in ["/health/liveness/", "/metrics/"]:
            log_data = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": "INFO" if response.status_code < 400 else "WARNING",
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "client_ip": client_ip,
                "user": str(request.user) if hasattr(request, "user") else "anonymous",
            }
            sys.stdout.write(json.dumps(log_data) + "\n")
            sys.stdout.flush()

        return response

