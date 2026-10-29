# Architecture Decision Records (ADRs)

## ADR 01: Socket.IO over Server-Sent Events (SSE)
- **Status**: Accepted
- **Context**: Need real-time bi-directional messaging (presence updates, room subscription acknowledgments, collaborative events).
- **Decision**: Use Flask-SocketIO on the server and socket.io-client on the frontend.
- **Consequences**: Enables low-latency rooms, bi-directional acknowledgments, built-in reconnection management, and seamless clustering with Redis.

---

## ADR 02: Optimistic Concurrency Control (OCC) over Pessimistic Locking
- **Status**: Accepted
- **Context**: Collaborative Kanban boards have high read-to-write ratios. Holding persistent DB locks or edit locks causes poor UX and orphaned locks on disconnect.
- **Decision**: Tasks carry an integer `version`. Modifications require `expectedVersion` and use `SELECT ... FOR UPDATE` with `WHERE version = expected_version`.
- **Consequences**: High throughput; version mismatches immediately return 409 `VERSION_CONFLICT` with the authoritative server task payload for client reconciliation.

---

## ADR 03: Fractional Indexing over Integer Position Reordering
- **Status**: Accepted
- **Context**: Moving a task within a 1,000-card column must not re-write all 1,000 rows (`UPDATE tasks SET position = position + 1`).
- **Decision**: Use variable-length alphanumeric strings (`COLLATE "C"`) calculated via midpoint fractional indexing (`fractional-indexing`).
- **Consequences**: Moves require updating only 1 row. When key length exceeds 64 bytes, a server-side rebalancing job redistributes keys evenly.

---

## ADR 04: Composite Foreign Keys & Database Row-Level Security (RLS)
- **Status**: Accepted
- **Context**: Multi-tenant systems are vulnerable to cross-tenant data leakage via forged request parameters.
- **Decision**:
  1. Every business table explicitly includes `tenant_id`.
  2. Composite foreign keys enforce that tasks cannot reference columns of other tenants.
  3. Row Level Security (`tenant_isolation_policy`) acts as a second, defense-in-depth isolation layer using `app.tenant_id`.
- **Consequences**: Impossible to leak or write data across tenant boundaries even if an application SQL query omits a WHERE clause.

---

## ADR 05: Stateless Access Tokens & Secure HttpOnly Refresh Rotation
- **Status**: Accepted
- **Context**: Access tokens must be verified without database lookups on every request, but token theft or branch removal must be revocable.
- **Decision**:
  - 15-minute JWT access tokens kept strictly in memory in the SPA.
  - 7-day rotating refresh tokens stored hashed in PostgreSQL and transmitted via an `HttpOnly`, `SameSite=Lax` secure cookie.
- **Consequences**: Fast stateless request verification; immediate access revocation upon tenant membership removal via `access:revoked` event.
