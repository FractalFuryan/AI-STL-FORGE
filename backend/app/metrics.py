from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

REQUEST_COUNT = Counter("http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"])
REQUEST_DURATION = Histogram("http_request_duration_seconds", "HTTP request duration", ["method", "endpoint"])
ACTIVE_REQUESTS = Gauge("http_requests_active", "Active HTTP requests")
RATE_LIMIT_BLOCKED = Counter("rate_limit_blocked_total", "Blocked rate-limited requests")


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
