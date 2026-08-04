from django.db import connection
from django.http import JsonResponse


def healthz(request):
    """Liveness/readiness probe: confirms the DB connection is usable."""
    db_ok = True
    try:
        connection.ensure_connection()
    except Exception:  # pragma: no cover - defensive
        db_ok = False

    status = 200 if db_ok else 503
    return JsonResponse({"status": "ok" if db_ok else "degraded", "db": db_ok}, status=status)
