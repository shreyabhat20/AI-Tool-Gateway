# Architecture

## Request path

```mermaid
sequenceDiagram
  participant C as AI client
  participant G as FastAPI gateway
  participant P as PostgreSQL
  participant R as Redis
  participant T as Demo tool
  C->>G: POST /tools/{name}/invoke + JWT
  G->>P: Resolve user, tool, permission
  G->>G: Validate JSON schema
  G->>R: Increment user/tool limit; check circuit
  G->>T: POST /invoke (request ID, bounded timeout)
  T-->>G: Mock result
  G->>P: Store metadata-only audit event
  G-->>C: Result + request/trace IDs
```

`app/api` owns request validation and routes. `app/core` owns configuration, JWTs, JSON logging, metrics, and tracing. `app/db` owns models, Alembic migrations, sessions, and idempotent seeds. `app/services` owns registry validation, authorization, execution, rate limiting, and audit persistence. `app/demo_tools` contains three safe mocks; the same image runs each mock with a different `TOOL_KIND`.

## Identity and authorization

The only identities are seeded `admin`, `developer`, and `viewer`. A local bootstrap key can mint a short-lived JWT for a seeded identity. There is no password or user registration API. An admin can manage tools and permissions; other roles need an explicit allowed mapping for each tool. Authorization happens before input validation, Redis operations, and downstream requests, avoiding tool data exposure to unauthorized actors.

## Execution controls

Tool targets are restricted to exact Compose hostnames on port 8000 with `/invoke`. The client disables environment proxy settings. Schema registration rejects remote references, requires an object schema, and caps schema size. Invocation validates arguments before rate limiting and proxying. The Redis counter is scoped to actor and tool, and its expiry is refreshed on each attempt. The circuit opens after a configured number of transient failures and cools down automatically. Each downstream attempt has a timeout; one retry is allowed only for transport failures or HTTP 502/503/504. The ticket mock derives its ID from `X-Request-ID`, so retries do not create duplicate simulated tickets.

## Data and observability

PostgreSQL stores users, tools, permissions, and invocations. Invocations include actor and tool snapshots, argument keys and encoded byte count, outcome, status, latency, request ID, UTC timestamp, and trace ID. Raw argument values and downstream output are never stored in audit records. The audit query is admin-only, filtered, and paginated. Prometheus scrapes `/metrics/`; metric labels use bounded dimensions (route templates and tool names, although admin-created tool names can increase cardinality). OpenTelemetry spans are exported as structured local logs. Request and trace IDs appear in responses and logs.

## Trust boundary and limitations

Everything is local Docker Compose infrastructure. API, PostgreSQL, Redis, and Prometheus bind to loopback; mock services have no host ports. The demo key can mint an admin token and must remain local. Redis has no authentication because it is a local demo. This stack is not suitable for public exposure without a real identity provider, transport security, secret management, network policy, stronger rate-limit atomicity, audit retention policy, and a hardened tool sandbox.

