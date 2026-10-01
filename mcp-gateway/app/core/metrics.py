from prometheus_client import Counter, Gauge, Histogram

HTTP_REQUESTS = Counter("gateway_http_requests_total", "HTTP requests", ["method", "route", "status"])
HTTP_LATENCY = Histogram("gateway_http_latency_seconds", "HTTP request latency", ["method", "route"])
TOOL_INVOCATIONS = Counter("gateway_tool_invocations_total", "Tool attempts", ["tool", "outcome"])
AUTH_DENIALS = Counter("gateway_authorization_denials_total", "Authorization denials", ["tool"])
RATE_LIMITS = Counter("gateway_rate_limits_total", "Rate limit denials", ["tool"])
DOWNSTREAM_ERRORS = Counter("gateway_downstream_errors_total", "Downstream failures", ["tool"])
CIRCUIT_OPEN = Gauge("gateway_circuit_open", "Circuit open state", ["tool"])

