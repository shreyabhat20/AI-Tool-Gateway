# ADR 0004: Redis for rate limits and circuit state

Status: Accepted

Redis is already part of the local stack and supports fast shared state across API workers. Each user/tool pair has a counter with a refreshed expiry. Each tool has a transient-failure counter and a short-lived open-circuit key. The gateway fails closed if Redis is unavailable. The limit is simple and may reject a burst for longer than a strict fixed window; a production implementation would use an atomic sliding-window algorithm and formal capacity policies.

