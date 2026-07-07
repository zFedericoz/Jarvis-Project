"""
Prometheus metrics for J.A.R.V.I.S.
"""

import time
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

# ── HTTP request metrics ──────────────────────────────────────────────────────
http_requests_total = Counter("jarvis_http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"])
http_request_duration_seconds = Histogram(
    "jarvis_http_request_duration_seconds", "HTTP request latency",
    ["method", "endpoint"], buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)
)

# ── LLM metrics ───────────────────────────────────────────────────────────────
llm_requests_total = Counter("jarvis_llm_requests_total", "Total LLM requests", ["operation"])
llm_tokens_total = Counter("jarvis_llm_tokens_total", "Total LLM tokens processed", ["operation"])
llm_duration_seconds = Histogram(
    "jarvis_llm_duration_seconds", "LLM request latency",
    ["operation"], buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0)
)

# ── Cache metrics ─────────────────────────────────────────────────────────────
cache_hits_total = Counter("jarvis_cache_hits_total", "Total cache hits", ["cache"])
cache_misses_total = Counter("jarvis_cache_misses_total", "Total cache misses", ["cache"])

# ── System gauges (updated periodically) ──────────────────────────────────────
system_info = Gauge("jarvis_system_info", "System information", ["version"])
llm_connected = Gauge("jarvis_llm_connected", "LLM connection status (1=ok, 0=error)")
redis_connected = Gauge("jarvis_redis_connected", "Redis connection status (1=ok, 0=error)")


def metrics_response():
    from fastapi.responses import Response
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


class MetricsMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        start = time.monotonic()
        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "/")

        async def _send_with_metrics(event):
            if event["type"] == "http.response.start":
                status = event.get("status", 0)
                http_requests_total.labels(method=method, endpoint=path, status=status).inc()
                http_request_duration_seconds.labels(method=method, endpoint=path).observe(
                    time.monotonic() - start
                )
            await send(event)

        await self.app(scope, receive, _send_with_metrics)
