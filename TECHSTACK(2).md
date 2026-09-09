# Crypto-Tracer --- Technology Stack

**Goal:** Fast SIH prototype now, production-capable foundations later.

------------------------------------------------------------------------

## 1. Stack Summary

  Layer            Technology                              Role
  ---------------- --------------------------------------- -----------------------------
  Frontend         React + TypeScript                      Investigator UI
  UI               Tailwind CSS                            Layout/styling
  Graph UI         Cytoscape.js                            Transaction graph
  Backend          Python 3.12+                            Core platform
  API              FastAPI                                 REST/OpenAPI
  Validation       Pydantic                                Request/domain schemas
  ORM              SQLAlchemy 2.x                          PostgreSQL access
  Database         PostgreSQL                              Cases/evidence/transactions
  Cache            Redis                                   Cache/status
  Jobs             Celery                                  Background traces/reports
  Graph engine     NetworkX                                BFS/DFS + graph model
  TRON             TronPy and/or official TRON HTTP APIs   TRON ingestion
  EVM              Web3.py                                 Future EVM ingestion
  Bitcoin          Blockstream API / Bitcoin adapter       Future BTC ingestion
  PDF              ReportLab                               Evidence/legal drafts
  Container        Docker Compose                          SIH deployment
  Testing          pytest                                  Backend tests
  Frontend tests   Vitest + Playwright                     UI/integration
  API contract     OpenAPI                                 API documentation

------------------------------------------------------------------------

## 2. Frontend

### React + TypeScript

Use for:

-   routing
-   case forms
-   investigation workspace
-   graph controls
-   evidence panels
-   report actions

Recommended packages:

``` text
react
react-router-dom
typescript
zod
@tanstack/react-query
axios OR fetch
```

### Why React

The submitted architecture already targets React and Cytoscape.js. The
investigation UI has enough state and interaction that a component-based
frontend is appropriate.

------------------------------------------------------------------------

## 3. Graph Visualization

### Cytoscape.js

Use it for:

-   directed graph
-   wallet nodes
-   transaction edges
-   zoom/pan
-   node selection
-   path highlighting
-   hop grouping
-   evidence overlays

Cytoscape.js is specifically designed for interactive graph
visualization and graph manipulation in JavaScript.

Example node types:

``` text
suspect
intermediate
deposit_candidate
vasp
mixer
bridge
unknown
```

Example edge types:

``` text
transfer
sweep
bridge
```

------------------------------------------------------------------------

## 4. Backend

### Python

Use Python because the project needs:

-   blockchain APIs
-   graph algorithms
-   data processing
-   scoring
-   PDF generation
-   rapid iteration

### FastAPI

Use:

``` text
FastAPI
Pydantic
SQLAlchemy
Alembic
```

FastAPI provides type-driven API development and automatic OpenAPI
documentation.

------------------------------------------------------------------------

## 5. API Structure

``` text
/api/v1
├── /cases
├── /traces
├── /graphs
├── /attribution
├── /evidence
├── /reports
└── /legal-drafts
```

Suggested initial endpoints:

``` text
POST   /cases
GET    /cases
GET    /cases/{id}

POST   /traces
GET    /traces/{id}
GET    /traces/{id}/graph
GET    /traces/{id}/attribution
POST   /cases/{id}/reports
POST   /cases/{id}/legal-drafts
```

------------------------------------------------------------------------

## 6. Blockchain Ingestion

### Primary: TRON

Use the official TRON API infrastructure as the primary source, with a
Python adapter around it.

TRON's official developer hub documents API, SDK and protocol interfaces
and provides an API reference.

For the MVP, retrieve:

-   account transaction history
-   TRC-20 token transfers
-   transaction metadata
-   block/time information as required
-   contract/event data where needed

### TRON adapter

``` text
TronClient
   ↓
TronProvider
   ↓
Normalized Transfer
```

Never allow raw provider JSON to become the internal domain model.

------------------------------------------------------------------------

## 7. Normalized Transaction Model

``` python
class Transfer:
    chain: str
    tx_hash: str
    block_number: int | None
    timestamp: datetime
    from_address: str
    to_address: str
    asset_contract: str
    asset_symbol: str
    amount_raw: int
    amount_decimal: Decimal
    source: str
    raw: dict
```

This allows future providers to produce the same object.

------------------------------------------------------------------------

## 8. TRC-20 USDT

Treat the token contract/address as configuration rather than scattering
a literal throughout the code.

``` text
config/
  chains/
    tron.yaml
```

Example concept:

``` yaml
tron:
  assets:
    usdt_trc20:
      symbol: USDT
      contract: "<verified contract address>"
      decimals: 6
```

Verify the production contract against authoritative token/provider
documentation before deployment.

------------------------------------------------------------------------

## 9. Graph Engine

### NetworkX

Use:

``` python
nx.MultiDiGraph()
```

because multiple transactions can exist between the same pair of
addresses.

NetworkX supports:

-   directed graphs
-   multigraphs
-   BFS
-   DFS
-   path operations
-   graph analysis

### Why not Neo4j now?

Because SIH MVP graph sizes are bounded and the core challenge is
investigation logic, not operating a graph database.

Add Neo4j later only if persistent large-scale graph queries justify it.

------------------------------------------------------------------------

## 10. Traversal

Use BFS as the primary investigation traversal.

Configuration:

``` yaml
tracing:
  max_hops: 4
  max_nodes: 500
  max_edges: 2000
  min_relevant_usd: 1.0
```

Future:

-   beam search
-   best-first traversal
-   weighted path ranking
-   reverse tracing
-   bidirectional search
-   cross-chain correlation

------------------------------------------------------------------------

## 11. Attribution Engine

Do not start with ML.

Start with an explainable rule/score engine:

``` text
Direct tag         35%
Sweep behavior     35%
Fan-in             15%
Temporal           15%
```

Output:

``` json
{
  "candidate": "Example VASP",
  "confidence": 0.942,
  "factors": {
    "direct_tag": 0.90,
    "sweep": 0.99,
    "fan_in": 0.95,
    "temporal": 0.91
  }
}
```

This gives the investigator an inspectable explanation.

------------------------------------------------------------------------

## 12. Entity/VASP Registry

### MVP

Use a version-controlled database table or JSON/YAML seed.

Fields:

``` text
entity_id
name
chain
address
address_type
source
source_url/reference
verification_status
confidence
first_verified_at
last_verified_at
```

Verification status:

``` text
VERIFIED
ANALYST_CONFIRMED
HEURISTIC
UNKNOWN
```

Do not represent a heuristic match as a verified VASP identity.

------------------------------------------------------------------------

## 13. Database

### PostgreSQL

Use for durable state.

Core tables:

``` text
cases
traces
wallets
transactions
graph_edges
vasps
vasp_addresses
attribution_results
evidence_items
reports
audit_events
```

### JSONB

Use JSONB for:

-   raw provider payload
-   attribution explanation
-   configuration snapshot
-   provider-specific metadata

Use normal relational columns for fields frequently queried.

PostgreSQL supports GIN indexing over JSONB where structured JSON
queries need acceleration.

------------------------------------------------------------------------

## 14. Redis

Use Redis for:

### Cache

``` text
account transfers
transaction details
entity lookups
trace result fragments
```

### Job infrastructure

Celery can use Redis as broker/result backend.

### Status

``` text
trace:{id}:status
```

### Important

Redis is **not** the authoritative evidence store.

PostgreSQL remains the source of truth.

------------------------------------------------------------------------

## 15. Celery

Use Celery for:

``` text
trace_wallet
fetch_transactions
run_attribution
generate_report
```

Celery is appropriate when tracing becomes too slow for a normal HTTP
request or when provider calls need retries/background execution.

For the SIH demo, the architecture can support both:

``` text
small/cached trace → synchronous
large/live trace   → Celery
```

------------------------------------------------------------------------

## 16. PDF

### ReportLab

Use ReportLab for:

-   evidence dossier
-   transaction tables
-   attribution explanation
-   graph image
-   legal draft

The PDF should include:

``` text
Case metadata
Investigation input
Executive finding
Transaction path
Evidence
Attribution
Confidence
Limitations
Provenance
Investigator review
```

------------------------------------------------------------------------

## 17. Frontend State

Use React Query/TanStack Query for server state:

``` text
cases
trace status
graph
attribution
evidence
reports
```

Keep local UI state separate:

``` text
selectedNode
selectedEdge
graphLayout
filters
expandedHops
```

Do not create a giant global state store unless the UI actually needs
it.

------------------------------------------------------------------------

## 18. Styling

Use Tailwind CSS.

Design direction:

``` text
dark investigator workstation
high information density
clear hierarchy
minimal decoration
strong status indicators
```

The graph should be visually dominant.

Recommended layout:

``` text
sidebar
   ↓
case workspace
   ├── graph
   ├── attribution
   ├── evidence
   └── actions
```

------------------------------------------------------------------------

## 19. Development Environment

### Docker Compose

Services:

``` yaml
services:
  frontend:
  api:
  worker:
  postgres:
  redis:
```

Optional:

``` text
flower
pgadmin
```

Do not require these optional tools for the judge demo.

------------------------------------------------------------------------

## 20. Environment Variables

``` text
DATABASE_URL
REDIS_URL

TRON_API_BASE_URL
TRON_API_KEY

ETH_RPC_URL
BTC_API_BASE_URL

REPORT_STORAGE_PATH

APP_ENV
LOG_LEVEL
```

Never commit secrets.

------------------------------------------------------------------------

## 21. Testing

### Backend

``` text
pytest
pytest-asyncio
httpx
```

Test:

-   API validation
-   graph traversal
-   normalization
-   pruning
-   attribution
-   provider mocks
-   report generation

### Frontend

``` text
Vitest
Testing Library
Playwright
```

Test:

-   case creation
-   trace action
-   graph rendering
-   attribution panel
-   report generation

------------------------------------------------------------------------

## 22. Code Quality

Recommended:

``` text
ruff
mypy
pre-commit
```

Formatting:

``` text
ruff format
```

Linting:

``` text
ruff check
```

Type checking:

``` text
mypy
```

------------------------------------------------------------------------

## 23. Observability

MVP:

-   structured JSON logs
-   request ID
-   trace ID
-   case ID
-   provider latency
-   trace duration

Production:

``` text
OpenTelemetry
Prometheus
Grafana
```

Do not introduce a full observability stack before the core product
works.

------------------------------------------------------------------------

## 24. Security

Required:

-   HTTPS in deployed environments
-   API-key secrets outside source
-   input validation
-   maximum traversal limits
-   provider timeout
-   rate limiting
-   audit events
-   no private wallet keys
-   no transaction signing
-   no autonomous exchange actions

Recommended later:

-   RBAC
-   SSO
-   MFA
-   secrets manager
-   network segmentation
-   database encryption
-   immutable audit storage

------------------------------------------------------------------------

## 25. Dependency Philosophy

### Use now

``` text
React
TypeScript
Tailwind
Cytoscape.js
FastAPI
Pydantic
SQLAlchemy
PostgreSQL
Redis
Celery
NetworkX
TRON API/SDK
ReportLab
Docker
pytest
```

### Do not add yet

``` text
Kubernetes
Kafka
Neo4j
Elasticsearch
Spark
Ray
LLM agents
ML attribution
microservices
```

Add them only when a measured requirement exists.

------------------------------------------------------------------------

## 26. AI/ML Position

The MVP does **not** need an LLM or ML model to claim intelligence.

The core intelligence is:

``` text
graph traversal
+
noise pruning
+
behavioral heuristics
+
entity matching
+
explainable scoring
```

If ML is added later, it should rank candidate VASPs or anomalous
behaviors while preserving the raw evidence and deterministic features
underneath.

Never allow an LLM to invent transaction facts or entity ownership.

------------------------------------------------------------------------

## 27. Recommended Repository

``` text
crypto-tracer/
│
├── apps/
│   ├── web/
│   └── api/
│
├── packages/
│   └── shared-types/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── domain/
│   │   ├── adapters/
│   │   ├── workers/
│   │   ├── persistence/
│   │   └── config/
│   └── tests/
│
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── features/
│   │   ├── api/
│   │   └── graph/
│   └── tests/
│
├── fixtures/
│   ├── traces/
│   └── vasp-registry/
│
├── docs/
│
├── docker-compose.yml
└── README.md
```

For a very fast SIH build, this can be simplified to:

``` text
frontend/
backend/
fixtures/
docker-compose.yml
```

------------------------------------------------------------------------

## 28. Recommended Build Order

### Sprint 1 --- Product skeleton

``` text
React UI
FastAPI
PostgreSQL
case creation
investigation page
```

### Sprint 2 --- Core trace

``` text
TRON adapter
normalization
NetworkX
BFS
pruning
graph API
```

### Sprint 3 --- Differentiator

``` text
VASP registry
sweep detection
fan-in
temporal scoring
confidence UI
```

### Sprint 4 --- Evidence

``` text
evidence model
audit trail
PDF
BNSS draft
```

### Sprint 5 --- Demo hardening

``` text
fixture replay
loading states
error states
animations
benchmark
Docker
```

------------------------------------------------------------------------

## 29. Final Stack Decision

### Build the SIH prototype with:

**Frontend**

> React + TypeScript + Tailwind + Cytoscape.js

**Backend**

> Python + FastAPI + Pydantic + SQLAlchemy

**Data**

> PostgreSQL + Redis

**Processing**

> NetworkX + Celery

**Blockchain**

> TRON official APIs / TronPy first

**Reports**

> ReportLab

**Deployment**

> Docker Compose

**Testing**

> pytest + Vitest + Playwright

This stack closely follows the team's submitted architecture while
keeping the implementation realistic for a short SIH build.
