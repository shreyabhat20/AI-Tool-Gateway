# ADR 0001: Seeded local identities and JWTs

Status: Accepted

The portfolio demo needs to show role authorization without storing passwords or integrating a real identity provider. We seed three users and mint short-lived HS256 JWTs only when the caller supplies a locally configured demo access key. The key can mint an admin token, so the API binds to loopback and the README warns against public exposure. This preserves a realistic bearer-token boundary while keeping the project reproducible offline. A production system would replace the issuer with an external identity provider and managed keys.

