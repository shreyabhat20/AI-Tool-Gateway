# ADR 0003: Store invocation metadata, not payloads

Status: Accepted

Invocation auditability requires who, what, when, outcome, latency, and correlation IDs. Raw arguments and tool responses could contain sensitive data. Audit rows therefore store top-level argument names and serialized byte count, not values or outputs. Actor and tool names are snapshotted so history remains readable after deletion. This reduces forensic detail, but the request and trace IDs support correlation with local JSON logs while limiting data exposure.

