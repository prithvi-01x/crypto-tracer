# Original User Request

## 2026-09-10T07:52:21Z

Upgrade the Crypto-Tracer frontend into an enterprise-grade blockchain forensic investigation suite modeled directly after the visual, layout, and interaction paradigms of Chainalysis Reactor, featuring a signature Reactor-style graph canvas, entity profiling workstation, transaction flow interpretation, and dual light/dark design tokens, while strictly leaving the backend untouched.

Working directory: /home/gabiimaruuu/crypto-tracer/frontend
Integrity mode: demo

## Reference Material
- Local Chainalysis Reactor clone: `/home/gabiimaruuu/crypto-tracer/chainalysis-reactor-clone`
- Color tokens & CSS variables: `chainalysis-reactor-clone/assets/css/template-shared.css` and `variables.css`
- UI layout, graph styles, and interaction patterns: `chainalysis-reactor-clone/components/` and `screenshots/`
- Palette references: Safety Orange (`#FF5300`), Midnight Navy (`#122149`), Deep Blue (`#293972`), Matrix Teal (`#27FFBE`), Product UI Slate (`#F4F6FA`), Stroke (`#D1D3E0`), High-risk/Illicit red (`#B50004` / `#FFE4DF`)

## Mandatory Operational Guardrails
- **Strict Scope Boundary**: Only `frontend/` may be modified. Do NOT modify `backend/` or `chainalysis-reactor-clone/`.
- **Zero Backend Disruption**: Git diff must contain ZERO changes under `backend/`. All existing FastAPI endpoints, DB models, and repository contracts remain 100% untouched.
- **Reference Only**: Use Reactor strictly as a visual, structural, and interaction reference. Do NOT copy Chainalysis branding, logos, proprietary copy, or identity. Maintain the "Crypto-Tracer" identity.
- **No Fake / Mock Data**: All views, nodes, edges, attributions, evidence items, and alerts must be driven exclusively by real backend API data.
- **Full Workflow Preservation**: Existing real Alerts/Findings, Attribution, Evidence Vault, Notes, and Reports/Dossier features must continue to function completely.
- **Hostile Regression Testing**: Before finalizing, run a complete regression of the existing end-to-end workflow (Case selection -> Trace Graph -> Alerts drawer / Findings tab -> Evidence Vault navigation -> Report generation -> Case notes).

## Requirements

### R1. Reactor Design Tokens & Dual-Mode Visual Identity
Implement Chainalysis Reactor's signature styling into the frontend design system with full dual-mode support:
- **Reactor Clean Light**: Enterprise look with product slate `#F4F6FA` canvas, clean borders (`#D1D3E0`), deep navy headers (`#122149`), and safety orange (`#FF5300`) primary accents.
- **Reactor Cyber Dark**: Midnight investigation room look with deep navy `#122149` / `#040507` background, glowing matrix teal (`#27FFBE`) accents, and high-contrast forensic indicators.
- Modernized typography, rounded pill badges, and refined iconography matching Reactor's design standard.

### R2. Reactor-Grade Graph Canvas & Node/Edge Architecture
Upgrade the Cytoscape transaction graph visualization:
- Node presentation styled as Reactor pill chips with entity icons, risk labels (e.g., Suspect, Intermediate, Terminal/VASP), hop depth markers, and wallet balance indicators.
- Smooth curved directional edges with transfer value badges (e.g. "60,000 USDT"), timestamps, and clear arrowheads indicating money flow.
- High-visibility path-to-root tracing with glowing edge highlighting and dimmed background elements during node selection.
- Graph toolbar with Reactor-style zoom controls, layout relayout triggers, fit-to-screen, and legend indicators.

### R3. Entity Profiler & Transaction Flow Inspector
Upgrade the right-hand inspection drawer into a Reactor-grade Entity Profiler:
- Real-time wallet entity card displaying VASP attribution, confidence ratings, entity tags (Exchange, Mule, Mixer, P2P, Unhosted), and deposit cluster info.
- Human-readable transaction narrative summarizing hop-by-hop fund movements, consolidation timing, and rapid sweep velocity.
- Integrated quick actions for copying addresses, viewing on TronScan, generating Section 91 CrPC / Section 94 BNSS preservation notices, and reviewing forensic findings.

### R4. Case Workspace Header & Navigation Polish
Refactor the top case context strip and tab navigation into Reactor's command header:
- Prominent FIR reference, victim details, reported loss amount in INR & USDT, and chain indicator.
- Streamlined tab switching between Trace Graph, VASP Attribution, Forensic Findings (with live alert counter), Evidence Vault, and Legal Dossier reports.
- Working quick-actions for Export Dossier and Investigator Notes.

### R5. Hostile Regression & Zero-Backend Verification
Execute hostile regression across all tabs and workflows, ensuring build stability, lint clean, and verifying that `git diff backend/` is completely empty.

## Acceptance Criteria

### Code Quality & Build Verification
- [ ] `npm run lint` passes with 0 errors across all frontend files.
- [ ] `npm run build` succeeds cleanly with production bundle compiled in `frontend/dist/`.
- [ ] Backend test suite passes at its current baseline (`PYTHONPATH=. ./venv/bin/pytest backend/tests`) with ZERO changes under `backend/`.
- [ ] `git diff backend/` explicitly confirms 0 lines modified or added in backend.
- [ ] `chainalysis-reactor-clone/` remains completely unmodified.

### Functional & Interactive Verification
- [ ] Graph Canvas renders multi-hop traces with Reactor pill nodes, clear transfer labels, and curved directional arrows.
- [ ] Clicking any node centers the view, highlights the fund flow to root, and opens the Entity Profiler drawer.
- [ ] Forensic Alerts drawer opens and navigates directly to graph nodes via `[View on Graph]` and to the Evidence Vault via `[View Evidence]`.
- [ ] "Add Note" modal allows appending timestamped notes and saving full notes with immediate UI update.
- [ ] Dual-mode theme toggle works smoothly across all workspace views without visual regressions.
- [ ] Hostile regression test confirms all core investigation features (Cases, Graph, Attribution, Findings, Evidence, Reports) work without disruption.

## 2026-09-13T07:16:22Z

Refactor Crypto-Tracer from a hackathon prototype into an enterprise, production-grade cryptocurrency tracing and VASP attribution platform for law enforcement agencies, preserving core forensic domain logic while implementing production hardening incrementally.

Working directory: /home/gabiimaruuu/crypto-tracer
Integrity mode: development

## Verification Resources
- Backend Test Suite: backend/tests/ (100 existing passing tests covering tracing, attribution, evidence, reports, boundaries, hardening, health, and TRON provider).
- End-to-End Suite: tests/e2e/ (35 existing Playwright tests covering critical judge gaps, command header, theme toggle, entity profiler, canvas interactions).
- Execution Script: start.sh (one-command boot with environment verification and service health checks).
- Production Refactor Blueprint: prod_readiness_refactor_plan.md.

## Requirements

### R1. Security Hardening & Repository Hygiene (Phase 0)
- Enforce strict repository hygiene: eliminate secrets from tracked/distributable files; ensure .env and sensitive environment configurations are untracked and excluded from distributable packages.
- Establish strict production configuration validation in backend/app/config.py: require environment-injected secrets with zero insecure production defaults; fail startup immediately if required production secrets (SECRET_KEY, DATABASE_URL, OIDC_ISSUER, etc.) are absent.
- Mount essential security middlewares on FastAPI in backend/app/main.py: TrustedHostMiddleware, security headers (CSP, HSTS, X-Frame-Options: DENY, X-Content-Type-Options: nosniff), environment-governed CORS origins, and request correlation IDs (X-Correlation-ID).
- Standardize all API error responses into an envelope schema ({ "error": { "code", "message", "timestamp", "trace_id" } }).
- Gate DEMO routes and fixture providers behind APP_ENV != "production"; never mount or expose fixture/demo endpoints in production mode.
- Integrate automated security analysis tools (Bandit / Semgrep / Gitleaks) into the repository verification pipeline.

### R2. Authentication, Authorization & Multi-Tenancy Foundation (Phase 1)
- Replace mock authentication in backend/app/api/v1/endpoints/auth.py with an extensible authentication abstraction supporting OIDC / JWT with RSA256 signature validation.
- Implement Role-Based Access Control (RBAC) with 4 distinct roles:
  - ROLE_INVESTIGATOR: Run traces, view assigned cases, add case notes.
  - ROLE_SUPERVISOR: Review/approve cases, authorize Section 94 BNSS production requests.
  - ROLE_ADMIN: Manage system configuration, user accounts, and VASP intelligence registries.
  - ROLE_AUDITOR: Read-only access to tamper-evident audit logs and verification roots.
- Implement tenant hierarchy data partitioning: tenant_id (State/Agency), district_id, police_station_id.
- Enforce tenant isolation and authorization checks across all repository queries and API endpoints accessing cases, traces, evidence, findings, reports, attributions, and audit records.
- Prevent Insecure Direct Object References (IDOR): authorize resource access exclusively using tenant context alongside resource IDs.

### R3. Database Hardening & Versioned Migrations (Phase 2)
- Introduce Alembic (alembic init -t async backend/alembic); make Alembic migrations the sole mechanism for production schema management.
- Remove Base.metadata.create_all from application startup in backend/app/main.py.
- Migrate primary key identifiers to PostgreSQL native UUID and queryable payload fields to PostgreSQL JSONB where justified.
- Add GIN indexes on queryable JSONB fields (evidence_items.payload, traces.graph_data).
- Standardize pagination on large query collections using cursor/keyset pagination.
- Enforce append-only evidentiary immutability for forensic evidence (evidence_items) and audit records (audit_events); separate ordinary business-data soft deletion (is_deleted, deleted_at) from evidence retention rules.

### R4. Asynchronous Trace Execution & Durable Job State (Phase 3)
- Retain existing GraphEngine BFS logic while converting POST /api/v1/traces into an asynchronous job submission endpoint returning HTTP 202 Accepted with durable job state.
- Implement background worker execution via Redis task queue (ARQ or Celery).
- Establish durable job states: QUEUED, RUNNING, PARTIAL, COMPLETED, FAILED, RETRYABLE, CANCELLED.
- Persist worker heartbeats, attempt counts, execution progress, failure classifications, and intermediate graph checkpoints.
- Stream incremental progress events over WebSockets/SSE with polling fallback.

### R5. Blockchain Provider Abstraction & Resilience (Phase 4)
- Formalize the BlockchainProvider abstraction to unify TronGrid REST and TRON node gRPC clients.
- Implement a 3-state Circuit Breaker (CLOSED, OPEN, HALF_OPEN) with exponential backoff and jittered retries.
- Maintain existing TRON transaction normalization semantics and cache finalized blockchain data in Redis.

### R6. Forensic Integrity Vault & Statutory Document Delivery (Phases 5 & 6)
- Replace isolated SHA-256 digests with a tamper-evident cryptographic hash chain: Hash_i = SHA256(Hash_{i-1} || CanonicalPayload_i || Timestamp_i || ActorID_i).
- Expose an integrity verification API that walks the chain from genesis and pinpoints the exact sequence number of any tampered record.
- Offload CPU-heavy PDF report generation (Section 63 BSA Dossier and Section 94 BNSS Written Production Request) to background workers.
- Store generated reports in S3/MinIO encrypted object storage instead of pod-local disk.

### R7. Frontend Modernization & Production DevOps (Phases 7 & 8)
- Implement client-side routing (react-router-dom) enabling direct deep linking (/cases/:id, /cases/:id/traces/:traceId).
- Integrate TanStack Query (@tanstack/react-query) for server state caching and real-time streaming updates.
- Decompose monolithic CaseDetailsView.tsx (1,198 LOC) into focused sub-components and isolate Cytoscape lifecycle inside a dedicated hook with explicit cleanup.
- Author production multi-stage Dockerfile, docker-compose.prod.yml, and expand CI with Playwright, Alembic checks, and security scans.

## Acceptance Criteria

### Security & Repository Hygiene
- [ ] Production mode (APP_ENV=production) fails to start with an informative configuration error when required secrets/keys are missing.
- [ ] No .env or sensitive credentials exist in tracked Git files or release archives.
- [ ] Demo endpoints (/demo/*) return 404 Not Found or 403 Forbidden when running in production mode.
- [ ] All API responses include standard security headers (X-Content-Type-Options, X-Frame-Options, Strict-Transport-Security).
- [ ] Static security scanning passes with zero high/critical vulnerabilities.

### Authentication & Tenant Isolation
- [ ] Unauthenticated requests to protected endpoints return 401 Unauthorized.
- [ ] Requests attempting to access cases or evidence belonging to a different tenant_id return 404 Not Found or 403 Forbidden (IDOR proof).
- [ ] Role permissions are enforced: INVESTIGATOR cannot access user administration; non-supervisors cannot approve legal notices.
- [ ] Authorization matrix test suite passes 100%.

### Database & Migrations
- [ ] Fresh database setup can be created entirely via alembic upgrade head.
- [ ] Application startup does not mutate or alter the database schema.
- [ ] Existing SQLite in-memory test suite continues to pass without regression.
- [ ] Forensic evidence records cannot be deleted via cascade or regular API calls.

### Asynchronous Tracing
- [ ] POST /api/v1/traces responds in < 300ms with 202 Accepted and initial job status QUEUED.
- [ ] Background worker successfully executes multi-hop BFS and updates job status to COMPLETED or PARTIAL.
- [ ] Worker restart or kill does not leave dangling locks; interrupted jobs can resume from checkpoints.

### Forensic Integrity & Reports
- [ ] Modifying a single character in an audit payload causes the integrity verification API to detect tampering and return the corrupted sequence ID.
- [ ] Generated PDF reports are persisted in object storage (MinIO/S3) and served via authenticated pre-signed URLs.
- [ ] Legal documents correctly use statutory terminology: Section 63 BSA Evidence Certificate and Section 94 BNSS Written Production Request.

### Regression & E2E Validation
- [ ] All 100 existing backend pytest tests pass without modifications to test expectations.
- [ ] All 35 existing Playwright E2E tests pass cleanly.
- [ ] Frontend builds cleanly with zero Oxlint warnings.

## 2026-09-13T07:57:49Z

Continue execution of Milestone 2 (Phase 1 Auth & Multi-Tenancy). Use the completed explorer handoffs from .agents/teamwork_preview_explorer_m2_1, m2_2, and m2_3 to implement the Phase 1 deliverables.

## 2026-09-13T09:44:37Z

Milestone 4 backend verification confirmed: 256/256 tests passing (13/13 async, 11/11 resilience, 232 baseline). Proceed with certifying Gate 4 and advancing to Milestone 5 (Phases 5 & 6: Evidence Integrity Vault & Statutory Document Delivery).

## 2026-09-13T12:15:24Z

Continue with Milestone 5 (Phases 5 & 6: Evidence Integrity Vault & Statutory Document Delivery). Verify test suite and proceed.




