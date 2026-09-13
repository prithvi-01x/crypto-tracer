# Project: Crypto-Tracer Enterprise Hardening

## Architecture
- **Backend**: FastAPI (Python 3.12+), SQLAlchemy 2.0 (Async), Pydantic Settings, Alembic migrations, Redis (ARQ/Celery) async job queue.
- **Frontend**: React 19, TypeScript, Vite 8, Tailwind CSS, Cytoscape 3.34, Oxlint linter.
- **Persistence**: PostgreSQL 16 (production), SQLite in-memory (fast test runner with dialect-agnostic models), Redis 7 (caching & task queues).
- **Security & Multi-Tenancy**: OIDC / JWT RS256 token verification, 4-role RBAC (Investigator, Supervisor, Admin, Auditor), 3-tier tenant scoping (tenant_id / district_id / police_station_id), Section 63 BSA & Section 94 BNSS statutory compliance.
- **DevOps**: Multi-stage Dockerfiles (non-root), Docker Compose full-stack orchestration, GitHub Actions CI.

---

## Feature Inventory

| # | Req | Phase | Feature Name | Description | Milestone | Source |
|---|-----|-------|--------------|-------------|-----------|--------|
| 1 | R1 | Phase 0 | Repository Hygiene & Secret Scrubbing | Purge tracked credentials; ensure `.env` and keys gitignored | M1 | survey |
| 2 | R1 | Phase 0 | Strict Production Config Validation | Pydantic SecretStr; zero insecure prod defaults; clean exit on missing secrets | M1 | survey |
| 3 | R1 | Phase 0 | HTTP Security Middlewares & Headers | CSP, HSTS, X-Frame-Options: DENY, nosniff, CORS whitelist | M1 | survey |
| 4 | R1 | Phase 0 | Correlation Tracking & Structured Logs | Inbound/outbound `X-Correlation-ID`; JSON logs for SIEM | M1 | survey |
| 5 | R1 | Phase 0 | Standardized API Error Envelopes | Dual error schema `{ "error": ..., "detail": ... }` maintaining test compatibility | M1 | survey |
| 6 | R1 | Phase 0 | Demo Route Production Gating | Gate `/demo/*` behind `APP_ENV != "production"` | M1 | survey |
| 7 | R1 | Phase 0 | SAST Security Pipeline Integration | Bandit, Semgrep, Gitleaks scanning configuration in CI | M1 | survey |
| 8 | R2 | Phase 1 | OIDC / JWT RS256 Auth Engine | Bearer JWT validation; Parichay/CCTNS SSO; dev mock fallback | M2 | survey |
| 9 | R2 | Phase 1 | 4-Role RBAC Authorization | Investigator, Supervisor, Admin, Auditor role gates | M2 | survey |
| 10 | R2 | Phase 1 | Tenant Hierarchy Partitioning | Partition by tenant_id (State), district_id, station_id | M2 | survey |
| 11 | R2 | Phase 1 | Tenant Isolation & IDOR Defense | Mandatory tenant filtering on all repository queries | M2 | survey |
| 12 | R2 | Phase 1 | DPDP Act 2023 PII Encryption | AES-256-GCM encryption at rest for victim PII in case records | M2 | survey |
| 13 | R3 | Phase 2 | Async Alembic Migrations | Baseline async Alembic framework; versioned migration scripts | M3 | survey |
| 14 | R3 | Phase 2 | Removal of `create_all` from Lifespan | Remove DDL operations from application startup | M3 | survey |
| 15 | R3 | Phase 2 | Native UUID & JSONB Types with Dialect Variants | PostgreSQL UUID and JSONB with SQLite dialect variants (`with_variant`) | M3 | survey |
| 16 | R3 | Phase 2 | GIN Indexes on Forensic Payloads | GIN indexing on `evidence_items.payload` and `traces.graph_data` | M3 | survey |
| 17 | R3 | Phase 2 | Evidentiary Immutability & Soft-Delete | Eliminate cascade deletes; soft-delete on cases only; append-only evidence | M3 | survey |
| 18 | R3 | Phase 2 | Keyset & Cursor-Based Pagination | Standardize `cursor`/`limit` on large collections | M3 | survey |
| 19 | R3 | Phase 2 | Connection Pool Hardening | `pool_pre_ping=True`, recycle, PgBouncer compatibility | M3 | survey |
| 20 | R4 | Phase 3 | Asynchronous Trace Submission (202) | `POST /traces` returns 202 Accepted; sync fallback for test mode | M4 | survey |
| 21 | R4 | Phase 3 | Distributed Worker Fleet (ARQ/Redis) | Redis background workers executing BFS graph engine | M4 | survey |
| 22 | R4 | Phase 3 | 7-State Durable Job Machine | QUEUED, RUNNING, PARTIAL, COMPLETED, FAILED, RETRY, CANCEL | M4 | survey |
| 23 | R4 | Phase 3 | Worker Heartbeats & Checkpointing | Heartbeats in Redis; hop snapshots; crash recovery | M4 | survey |
| 24 | R4 | Phase 3 | Real-Time Progress Streaming | WebSocket `/ws/traces/{id}` & SSE with polling fallback | M4 | survey |
| 25 | R5 | Phase 4 | Formalized BlockchainProvider ABC | Standardized abstract base class for providers | M4 | survey |
| 26 | R5 | Phase 4 | TRON Ingestion Hardening | Resilient ingestion with rate limiting and timeout management | M4 | survey |
| 27 | R5 | Phase 4 | 3-State Circuit Breaker & Backoff | CLOSED, OPEN, HALF_OPEN with jittered exponential backoff | M4 | survey |
| 28 | R5 | Phase 4 | Multi-Endpoint Failover Pool | Redundant endpoint routing with health probes | M4 | survey |
| 29 | R5 | Phase 4 | Distributed Redis Blockchain Cache | Caching finalized blocks/transfers with TTL | M4 | survey |
| 30 | R6 | Phase 5 | Tamper-Evident Merkle Hash Chain | Chained audit ledger: $H_i = \text{SHA256}(H_{i-1} \parallel P_i \parallel T_i \parallel A_i)$ | M5 | survey |
| 31 | R6 | Phase 5 | Chain Integrity Verification API | `GET /cases/{id}/evidence/verify-integrity` detecting single-byte tampering | M5 | survey |
| 32 | R6 | Phase 6 | Asynchronous PDF Compilation | Background compilation of Section 63 BSA & 94 BNSS documents | M5 | survey |
| 33 | R6 | Phase 6 | Encrypted Storage Vault | Encrypted document storage for legal reports | M5 | survey |
| 34 | R6 | Phase 6 | Authenticated Pre-Signed URLs | Time-limited pre-signed download links (15 min) | M5 | survey |
| 35 | R6 | Phase 6 | Statutory Standards (BSA 63 & BNSS 94) | Exact Section 63 BSA Certificate & Section 94 BNSS Notice templates | M5 | survey |
| 36 | R6 | Phase 6 | PAdES X.509 Digital Signatures | Officer digital signature stamping support | M5 | survey |
| 37 | R7 | Phase 7 | React Router Client Routing | Deep linking `/cases/:id`, `/cases/:id/traces/:traceId` | M6 | survey |
| 38 | R7 | Phase 7 | TanStack Query State Management | Query hooks with caching, deduplication, retry | M6 | survey |
| 39 | R7 | Phase 7 | Monolithic View Decomposition | Split `CaseDetailsView.tsx` into clean modular sub-components | M6 | survey |
| 40 | R7 | Phase 7 | Cytoscape Canvas Lifecycle & LOD | `useCytoscapeGraph` hook with teardown; zoom LOD performance | M6 | survey |
| 41 | R7 | Phase 7 | Zero Oxlint Warnings Compliance | Resolve 6 existing warnings across 5 frontend files | M6 | survey |
| 42 | R7 | Phase 7 | Dynamic Health & Telemetry Popover | Connect header bell popover to live `/api/v1/health` | M6 | survey |
| 43 | R7 | Phase 8 | Production Multi-Stage Dockerfiles | Hardened Python 3.12 slim & Nginx Alpine non-root images | M6 | survey |
| 44 | R7 | Phase 8 | Production Compose Orchestration | `docker-compose.prod.yml` full stack (backend, frontend, postgres, redis) | M6 | survey |
| 45 | R7 | Phase 8 | CI/CD Pipeline Expansion | Matrix tests, SAST, Playwright E2E, Alembic check | M6 | survey |

---

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Security Hardening & Config Validation (Phase 0) | Features 1-7: Repository hygiene, strict config validation, security headers, correlation IDs, dual error envelopes, demo route gating | none | DONE |
| M2 | Auth & Multi-Tenancy Foundation (Phase 1) | Features 8-12: JWT RS256 engine, 4-role RBAC, tenant hierarchy, IDOR defenses, PII encryption | M1 | IN_PROGRESS |
| M3 | Database Hardening & Versioned Migrations (Phase 2) | Features 13-19: Async Alembic migrations, remove create_all, UUID/JSONB with dialect variants, GIN indexes, immutability & soft-delete, cursor pagination, pool hardening | M2 | PLANNED |
| M4 | Asynchronous Traces & Provider Resilience (Phases 3 & 4) | Features 20-29: 202 async trace submission, Redis worker fleet, 7-state job machine, heartbeats/checkpoints, WebSockets/SSE, BlockchainProvider ABC, Circuit Breaker, failover pool, Redis cache | M3 | PLANNED |
| M5 | Forensic Integrity Vault & Statutory Delivery (Phases 5 & 6) | Features 30-36: Cryptographic Merkle hash chain, integrity verify API, async PDF compilation, encrypted vault, pre-signed URLs, Section 63 BSA & Section 94 BNSS compliance | M4 | PLANNED |
| M6 | Frontend Modernization & DevOps (Phases 7 & 8) | Features 37-45: Zero Oxlint warnings, 26 TS type fixes, view decomposition, React Router, TanStack Query, Dockerfiles, docker-compose.prod.yml, CI workflow | M1 | PLANNED |
| M7 | Final E2E Hardening & Dual-Track Acceptance | Comprehensive verification: 100/100 backend tests pass, 35/35 Playwright E2E tests pass, zero Oxlint warnings, production startup rejection | M1-M6 | PLANNED |

---

## Interface Contracts

### 1. Error Envelope Contract
All API errors return a dual envelope satisfying both legacy test expectations and enterprise SIEM requirements:
```json
{
  "error": {
    "code": "INVALID_ADDRESS",
    "message": "The provided cryptocurrency address is invalid.",
    "timestamp": "2026-09-13T12:00:00Z",
    "trace_id": "corr-uuid-1234"
  },
  "detail": {
    "code": "INVALID_ADDRESS",
    "message": "The provided cryptocurrency address is invalid."
  }
}
```

### 2. Configuration & Startup Contract
In `APP_ENV=production`:
- Required secrets (`SECRET_KEY`, `DATABASE_URL`) must be explicitly set with non-default, secure values.
- If missing, application terminates immediately with a clear error and exit code 1.
In `APP_ENV=test` or `development`:
- Safe in-memory defaults permitted.

### 3. Authentication & Multi-Tenancy Contract
- In `APP_ENV=production`: Endpoints enforce `Authorization: Bearer <token>`, validating RS256 signature and extracting `tenant_id`, `district_id`, `police_station_id`, `role`.
- In `APP_ENV=test` or `development`: Missing authorization header falls back to default officer session fixture (`role=INVESTIGATING_OFFICER`, `tenant_id="TN-STATE"`), preserving all 100 existing backend tests.

### 4. Trace Submission Contract
- In `POST /api/v1/traces`:
  - When `sync=true` or in test environment (`APP_ENV=test`), executes synchronously and returns `HTTP 201 Created` with full graph payload (preserving test assertions in `test_tron_provider.py`).
  - In production background mode, enqueues the job into Redis worker and returns `HTTP 202 Accepted` with `{ "job_id": ..., "status": "QUEUED" }`.

### 5. Database Dialect Contract
- Columns use dialect-compatible variants:
  - `String(36).with_variant(UUID(as_uuid=True), "postgresql")`
  - `JSON().with_variant(JSONB, "postgresql")`
- This ensures tests continue passing against SQLite in-memory while production executes against PostgreSQL 16.

---

## Code Layout
- `backend/app/config.py`: Hardened settings using `pydantic-settings`.
- `backend/app/main.py`: Security headers, correlation ID middleware, error handlers, route registration.
- `backend/app/core/`: Security, auth, cryptographic hashing, circuit breaker.
- `backend/app/persistence/`: Models, repositories, database connection pool, Alembic migrations in `backend/alembic/`.
- `backend/app/domain/`: Forensic logic (`GraphEngine`, `RelevancePruner`, `AttributionEngine`, `EvidenceGenerator`).
- `backend/app/services/`: Asynchronous jobs, document generation, storage vault.
- `frontend/src/`: Clean modular components (< 250 LOC), React Router, TanStack Query, Cytoscape hook.
- `docker/` & root: `Dockerfile.backend`, `Dockerfile.frontend`, `docker-compose.prod.yml`.
