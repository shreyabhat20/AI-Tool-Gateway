# Local operations runbook

## Start and migrate

1. Run `make setup` (or `python -m app.core.setup`) to create `.env` with random, local-only values. Alternatively copy `.env.example` and fill `POSTGRES_PASSWORD`, `JWT_SECRET`, `DEMO_ACCESS_KEY`, and the matching URL-encoded `DATABASE_URL` manually.
2. Run `make dev`. Without Make, run `docker compose up --build -d`, `docker compose exec -T api alembic upgrade head`, then `docker compose exec -T api python -m app.db.seeds`.
3. Check `curl -i http://localhost:8000/health/live` and `curl -i http://localhost:8000/health/ready`. Both should return 200. Inspect `docker compose ps` for container health.
4. Open `http://localhost:8000/docs` for routes and `http://localhost:9090` for Prometheus.

`make migrate` applies pending Alembic revisions. `make seed` safely reruns seed data. `make stop` preserves PostgreSQL, Redis, and Prometheus volumes. Database rollback is `docker compose exec -T api alembic downgrade -1`; review the revision and data impact first.

## Tests and static checks

Install Python 3.12 dependencies with `python -m pip install -e '.[dev]'`, then run `make lint`, `make typecheck`, and `make test`. The migration test requires a disposable PostgreSQL database named with `test` in its final URL segment and `TEST_DATABASE_URL` set to its URL; it is skipped otherwise. CI provides an isolated PostgreSQL service for it. Unit and API integration tests use SQLite and a fake Redis instance.

## Audit and traces

Use an admin JWT with `GET /audit/invocations`. Filters: `actor`, `tool`, `outcome`, `from_time`, `to_time`, `limit`, and `offset`. Correlate a response's `X-Request-ID` and `X-Trace-ID` with JSON logs from `docker compose logs api`. Audit rows contain argument names and byte counts only. No response body or argument values are saved.

## Metrics

Prometheus scrapes `api:8000/metrics/` every 15 seconds. Useful series: `gateway_http_requests_total`, `gateway_http_latency_seconds`, `gateway_tool_invocations_total`, `gateway_authorization_denials_total`, `gateway_rate_limits_total`, `gateway_downstream_errors_total`, and `gateway_circuit_open`. `curl http://localhost:8000/metrics/` shows the raw endpoint. The circuit gauge is process-local and updates when a call trips or resets a circuit; Redis is the authoritative state.

## Common failures

| Symptom | Check | Action |
|---|---|---|
| Compose rejects variables | `.env` values | Fill all required fields; URL-encode the database password in `DATABASE_URL`. |
| API readiness 503 | `docker compose ps`, API logs | Confirm PostgreSQL and Redis are healthy and local auth keys are set. |
| Tables missing | `alembic current` | Run `make migrate`, then `make seed`. |
| `invalid_demo_key` | Request header | Use the value of `DEMO_ACCESS_KEY` as `X-Demo-Key`; do not post it to a public service. |
| `permission_denied` | Tool permissions | Check `GET /tools/{name}/permissions` with a JWT; update mapping as admin. |
| `rate_limited` | Redis counter | Wait for the inactivity window or change the local limit in settings and restart. |
| `circuit_open` | Downstream health | Check the matching demo service and wait for cooldown. |
| Prometheus target down | `/metrics/` and Compose health | Confirm the API is healthy and scrape path includes the trailing slash. |

## Data handling

`.env` is ignored by Git and must stay local. The mock ticket service does not send or persist tickets. To reset demo data, stop the stack and remove named volumes only when the data is disposable; `docker compose down -v` permanently removes local PostgreSQL, Redis, and Prometheus data.

