# ADR 0002: Allowlist demo tool targets

Status: Accepted

An arbitrary administrator-supplied URL would make the gateway an SSRF proxy and could reach local metadata services or private networks. Registry writes accept only the three Compose demo hostnames, port 8000, and `/invoke`, with no URL credentials, query, or fragment. HTTPX ignores proxy environment variables. This intentionally limits the registry's usefulness as a general integration platform but keeps the portfolio demo safe and focused. New integrations require a reviewed allowlist change and separate threat analysis.

