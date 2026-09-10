# Crypto-Tracer — Implementation Phases

**Purpose:** Build the SIH26182 Crypto-Tracer prototype in controlled phases.  
**Rule:** Do not move to the next phase until the current phase is working and demoable.

---

## Phase 0 — Project Foundation

### Goal
Create the development skeleton and establish the core contracts.

### Build
- Git repository
- React + TypeScript frontend
- FastAPI backend
- PostgreSQL
- Redis
- Docker Compose
- Environment configuration
- Basic logging
- API versioning: `/api/v1`

### Deliverable
The app starts locally and frontend can communicate with backend.

### Do NOT build yet
- blockchain integrations
- complex authentication
- microservices
- Kubernetes

---

## Phase 1 — Case Management

### Goal
Make Crypto-Tracer feel like an actual investigator workstation.

### Build
- Dashboard
- Case list
- New Investigation page
- Case details
- FIR metadata
- Victim reference
- Loss amount
- 1930 acknowledgement/reference
- Suspect wallet / TxID input
- Chain + asset selection

### APIs
```text
POST /cases
GET  /cases
GET  /cases/{case_id}
```

### Deliverable
Officer can create and open an investigation.

---

## Phase 2 — TRON Data Ingestion

### Goal
Get real blockchain data into a normalized internal format.

### Build
- TRON provider adapter
- TRC-20 USDT transfer retrieval
- Pagination
- Provider timeout/retry
- API-key configuration
- Response normalization
- Transaction deduplication
- Cache

### Internal model

```text
Transfer
 ├── tx_hash
 ├── block_number
 ├── timestamp
 ├── from
 ├── to
 ├── asset
 ├── amount
 └── source
```

### Deliverable
Given a valid TRON address, backend can retrieve and normalize relevant USDT transfers.

---

## Phase 3 — Transaction Graph Engine

### Goal
Turn flat blockchain transactions into an investigation graph.

### Build
- NetworkX MultiDiGraph
- Wallet nodes
- Transaction edges
- Hop tracking
- BFS traversal
- Visited-address protection
- Maximum-hop limit
- Maximum-node/edge limits

### Core flow

```text
Suspect Wallet
      ↓
Hop 1
      ↓
Hop 2
      ↓
Hop 3
      ↓
Hop 4
```

### Deliverable
Backend returns a structured multi-hop transaction graph.

---

## Phase 4 — Relevance-Aware Pruning

### Goal
Remove blockchain noise while preserving forensic transparency.

### Build
- Configurable minimum relevant value
- Default MVP dust threshold: `< $1`
- Asset relevance
- Branch ranking
- Maximum branch width
- Pruned-transaction records
- Pruning reason

### Important
Never silently delete data.

Store:

```text
transaction
pruned = true
reason = DUST
threshold = 1.00
```

### Deliverable
Graph focuses on meaningful fund flows and reports how much noise was removed.

---

## Phase 5 — Investigation Graph UI

### Goal
Make the core Crypto-Tracer experience visually obvious.

### Build
- Cytoscape.js
- Zoom/pan
- Node selection
- Edge selection
- Amount labels
- Timestamp display
- Hop labels
- Path highlighting
- Node type styling
- Expand/collapse
- Transaction detail drawer

### Node types

```text
SUSPECT
INTERMEDIATE
DEPOSIT_CANDIDATE
VASP
MIXER
BRIDGE
UNKNOWN
```

### Deliverable
Judge can visually follow the stolen-money path.

---

## Phase 6 — VASP Attribution Engine

### Goal
Implement the central differentiator: explainable attribution.

### Build

#### VASP registry
- known addresses
- chain
- entity
- address type
- source
- verification status

#### Behavioral analysis
- sweep ratio
- destination concentration
- fan-in
- temporal delay
- known-address match

#### Confidence score

```text
CS =
0.35 × direct_tag
+ 0.35 × sweep
+ 0.15 × fan_in
+ 0.15 × temporal
```

### Deliverable

Example:

```text
Likely VASP
Example VASP

Confidence: 94.2%

Why?
✓ Strong sweep behavior
✓ High fan-in
✓ Temporal consistency
✓ Known destination evidence
```

The score must remain an **investigative hypothesis**, not proof of ownership.

---

## Phase 7 — Evidence & Provenance

### Goal
Make every important conclusion traceable back to source data.

### Build
- Evidence model
- Transaction evidence
- Attribution evidence
- Pruning evidence
- Source references
- Collection timestamps
- Engine version
- Configuration snapshot
- Content hashes
- Audit events

### Separate

```text
OBSERVED
DERIVED
INFERRED
HUMAN DECISION
```

### Deliverable
An investigator can click an attribution factor and see the evidence supporting it.

---

## Phase 8 — Reports & Legal Draft

### Goal
Turn analysis into an actionable investigator package.

### Build
- Evidence dossier
- Graph snapshot
- Transaction table
- Attribution explanation
- Limitations
- Provenance
- Report hash
- ReportLab PDF

### Legal draft

Generate:

```text
Draft Section 94 BNSS
Record-Production Request
```

with:

- case details
- relevant wallet addresses
- transaction references
- requested records
- VASP target
- investigator review state

### Critical boundary

The software:

```text
GENERATES DRAFT
      ↓
INVESTIGATOR REVIEWS
      ↓
INVESTIGATOR APPROVES/DISPATCHES
```

It does **not** autonomously freeze funds.

### Deliverable
One click generates a polished evidence dossier and draft legal request.

---

## Phase 9 — Failure & Boundary Handling

### Goal
Make the prototype credible when the ideal path fails.

### Handle

```text
Invalid wallet
Unsupported chain
Unsupported asset
RPC timeout
Rate limit
No transactions
No VASP found
Low confidence
Max hops reached
Mixer encountered
Bridge encountered
Report failure
```

### Mixer behavior

```text
Mixer detected
      ↓
High-Risk Obfuscation
      ↓
Stop/limit traversal
      ↓
Preserve evidence
```

Never claim mixer de-anonymization.

### Deliverable
Every failure produces a useful investigator-facing result instead of a broken screen.

---

## Phase 10 — Demo Reliability

### Goal
Make the SIH presentation deterministic.

### Build

```text
LIVE MODE
   ↓
Real TRON data

REPLAY MODE
   ↓
Prepared normalized fixture
```

### Demo fixture

Create a deterministic 4-hop investigation:

```text
Suspect
   ↓
Wallet B
   ↓
Wallet C
   ↓
Deposit Address
   ↓
Known VASP Endpoint
```

Include:

- meaningful USDT transfers
- dust/noise
- sweep behavior
- fan-in
- timestamps
- evidence
- attribution
- report

### Rule

The fallback fixture is for **demo reliability**, not for pretending synthetic data is live.

### Deliverable
The complete demo works even if a public blockchain provider temporarily fails.

---

## Phase 11 — Hardening

### Goal
Prepare the prototype for judge questions.

### Build
- Input validation
- API rate limits
- request IDs
- trace IDs
- structured logs
- database indexes
- caching
- bounded traversal
- timeout handling
- unit tests
- integration tests
- frontend tests
- Docker deployment

### Benchmark

Measure:

```text
trace duration
nodes discovered
edges discovered
nodes pruned
provider latency
attribution latency
PDF generation time
```

### Deliverable
You have actual measurements instead of unsupported performance claims.

---

## Phase 12 — Optional Extensions

Only after the core prototype is stable.

### P1

- Ethereum / EVM
- BNB
- Polygon
- richer entity registry
- background Celery workers

### P2

- Bitcoin UTXO tracing
- bridge correlation
- cross-chain graph
- advanced OSINT integration
- SAHYOG integration subject to official access/authorization

### P3

- RBAC
- SSO/MFA
- production deployment
- large-scale graph infrastructure
- specialized graph database if justified

---

# Recommended SIH Priority

If time is extremely limited:

```text
P0  Foundation
 ↓
P1  Case UI
 ↓
P2  TRON ingestion
 ↓
P3  BFS graph
 ↓
P4  Pruning
 ↓
P5  Graph UI
 ↓
P6  VASP attribution       ← DIFFERENTIATOR
 ↓
P7  Evidence
 ↓
P8  PDF / BNSS draft       ← PAYOFF
 ↓
P10 Demo reliability       ← CRITICAL
```

Everything after that is optional.

---

# Definition of "Prototype Complete"

Crypto-Tracer is prototype-complete when this single path works end-to-end:

```text
CREATE CASE
    ↓
ENTER WALLET
    ↓
TRACE
    ↓
FETCH TRON DATA
    ↓
BUILD 4-HOP GRAPH
    ↓
PRUNE NOISE
    ↓
DETECT SWEEP
    ↓
RANK VASP
    ↓
SHOW CONFIDENCE + EVIDENCE
    ↓
GENERATE DOSSIER
    ↓
GENERATE DRAFT SECTION 94 BNSS REQUEST
```

The judge should understand the value without needing to understand the implementation first.
