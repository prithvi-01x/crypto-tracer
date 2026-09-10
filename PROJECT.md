# Project: Crypto-Tracer Chainalysis Reactor Transformation

## Architecture
The Crypto-Tracer frontend is a single-page React 19 application built with Vite, Tailwind CSS, Cytoscape.js, and Lucide React.
It communicates with a FastAPI backend (`/api/v1/...`) via REST APIs, rendering multi-hop blockchain traces, VASP attributions, forensic alerts/findings, cryptographic evidence chains (DAG), and legal report exports.
The frontend is being overhauled to mirror the visual, structural, and interaction paradigms of Chainalysis Reactor:
- Dual-Mode Token System: Clean Light (`#F4F6FA`, `#D1D3E0`, `#122149`, `#FF5300`) and Cyber Dark (`#040507`, `#122149`, `#27FFBE`, `#B50004` / `#FFE4DF`).
- Cytoscape Reactor Canvas: Pill nodes with badges/balances/hop depth, curved bezier edges with transfer value badges, path-to-root tracing glow, and floating toolbar.
- Entity Profiler Workstation: Right drawer with wallet entity cards, VASP attribution candidates, risk tags, 2-column financial metrics, transaction flow narrative, and legal quick actions.
- Command Header & Subnav: FIR reference, victim details, loss in INR & USDT, chain badge, Safety Orange active tab underline, and quick action modals.
- Zero-Backend Invariance: 100% untouched `backend/` and `chainalysis-reactor-clone/`. All data driven by real backend endpoints.

## Feature Inventory
Every surveyed feature mapped to an assigned milestone:
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Reactor Clean Light Palette | Product slate `#F4F6FA` canvas, `#D1D3E0` borders, `#122149` navy headers, `#FF5300` safety orange | M1 | ORIGINAL_REQUEST §R1, Clone CSS |
| 2 | Reactor Cyber Dark Palette | `#040507` / `#122149` background, `#27FFBE` matrix teal glow, `#B50004` / `#FFE4DF` illicit red chips | M1 | ORIGINAL_REQUEST §R1, Clone CSS |
| 3 | Dual-Theme Token Architecture | CSS variables and Tailwind semantic classes eliminating hardcoded `police-*` dark-only colors | M1 | ORIGINAL_REQUEST §R1, Frontend Survey |
| 4 | Cytoscape Pill Node Styling | 42px concentric circular nodes with bottom pill chips, icons, risk labels, hop chips, balance indicators | M2 | ORIGINAL_REQUEST §R2, Clone Survey |
| 5 | Curved Directional Edges & Badges | Smooth bezier edges with arrowheads and transfer value badges (e.g., `60,000 USDT`, timestamps) | M2 | ORIGINAL_REQUEST §R2, Clone Survey |
| 6 | Path-to-Root Tracing Glow | Dijkstra path glow (`#27FFBE` dark / `#294DCD` light) with 0.12 background element dimming | M2 | ORIGINAL_REQUEST §R2, Frontend Survey |
| 7 | Floating Graph Toolbar | Zoom in/out, fit to screen, center root suspect, relayout trigger, and legend indicators | M2 | ORIGINAL_REQUEST §R2, Clone Survey |
| 8 | Entity Profiler Wallet Card | Real-time wallet card displaying VASP attribution (Binance), confidence (`81.6%`), hypothesis label, deposit cluster | M3 | ORIGINAL_REQUEST §R3, Frontend Survey |
| 9 | Risk Indicator Pill Badges | `Exchange / VASP`, `Mule Intermediary`, `Mixer / Tumbler`, `Unhosted Suspect` with illicit red tags | M3 | ORIGINAL_REQUEST §R3, Clone Survey |
| 10 | 2-Column Financial Summary Card | Metrics for Balance, Sent, Received, Fees, and Transaction count | M3 | ORIGINAL_REQUEST §R3, Clone Survey |
| 11 | Transaction Interpretation Narrative | Plain-English narrative summarizing hop movements, consolidation timing, and rapid sweep velocity | M3 | ORIGINAL_REQUEST §R3, Clone Survey |
| 12 | Entity Quick Actions | Copy address, view on TronScan, Draft Section 91 CrPC / Section 94 BNSS notices, View Findings deep-link | M3 | ORIGINAL_REQUEST §R3, Frontend Survey |
| 13 | Reactor Command Header | Prominent FIR reference, victim details pill, dual currency loss display (INR & USDT), chain pill | M4 | ORIGINAL_REQUEST §R4, Clone Survey |
| 14 | Reactor Subnav Tabs | 5 tabs with live alert counter badge on Findings, Safety Orange `#FF5300` active underline | M4 | ORIGINAL_REQUEST §R4, Clone Survey |
| 15 | Working Quick-Action Modals | Export Dossier modal and Case Notes modal (append timestamped entry & edit full notes) | M4 | ORIGINAL_REQUEST §R4, Frontend Survey |
| 16 | Opaque-Box E2E Testing Suite | Requirements-driven Playwright test suite covering Tiers 1-4 for all features | Test Track | ORIGINAL_REQUEST §R5, Testing Survey |
| 17 | Hostile Regression & Zero-Backend Guard | Verification that `git diff backend/` is 0 lines, `npm run lint` 0 errors, `npm run build` exits 0, `pytest` 94/94 passes | M5 | ORIGINAL_REQUEST §R5, Testing Survey |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Design Tokens & Dual-Mode Visual Foundation | `src/index.css`, `tailwind.config.js`, `App.tsx` theme toggle | none | PLANNED |
| M2 | Reactor-Grade Graph Canvas & Node/Edge Styling | `src/components/graph/InvestigationGraphCanvas.tsx`, `TraceStatsBar.tsx` | M1 | PLANNED |
| M3 | Entity Profiler Workstation & Flow Inspector | `src/components/graph/GraphDetailDrawer.tsx` | M1 | PLANNED |
| M4 | Case Command Header, Navigation & Modals | `src/components/cases/CaseDetailsView.tsx`, `CaseNotesModal.tsx`, `ReportExportModal.tsx` | M1 | PLANNED |
| M5 | Hostile Regression & Zero-Backend Disruption | 100% E2E tests passing, hostile regression, zero-backend audit | M1, M2, M3, M4, Test Track | PLANNED |

## Parallel Track: E2E Testing Track
- **Orchestrator**: `E2E Testing Orchestrator`
- **Output**: `TEST_INFRA.md`, comprehensive test suite in `tests/e2e/`, and `TEST_READY.md`.
- **Methodology**: Category-Partition, BVA, Pairwise Combinations, and Real-World Application Workloads using Python Playwright.

## Interface Contracts

### 1. Theming CSS Variables (`frontend/src/index.css` ↔ All Components)
- `--theme-product-ui-background`: `#F4F6FA` (light) / `#040507` (dark)
- `--theme-product-ui-stroke`: `#D1D3E0` (light) / `#293972` (dark)
- `--theme-dark-blue`: `#122149` (midnight navy)
- `--theme-deep-blue`: `#293972`
- `--theme-orange`: `#FF5300` (safety orange accent)
- `--theme-teal`: `#27FFBE` (matrix teal cyber accent)
- `--theme-illicit-red`: `#B50004`
- `--theme-illicit-red-bg`: `#FFE4DF`

### 2. Backend REST Contracts (Preserved 100% Untouched)
- `GET /api/v1/cases/`: List cases (returns `CaseItem[]`)
- `GET /api/v1/cases/{case_id}`: Case details (returns `CaseItem`)
- `PATCH /api/v1/cases/{case_id}`: Update case / notes
- `POST /api/v1/cases/{case_id}/notes`: Add timestamped note entry
- `GET /api/v1/traces/{trace_id}/graph`: Graph topology (returns `InvestigationGraph`: `nodes`, `edges`, `pruned_records`, `meta`)
- `GET /api/v1/traces/{trace_id}/attribution`: VASP Attribution (returns `AttributionResponse`: `candidates`, `best_candidate`)
- `GET /api/v1/cases/{case_id}/findings`: Forensic alerts (returns `ForensicFindingItem[]`)
- `PATCH /api/v1/cases/{case_id}/findings/{finding_id}`: Review finding
- `GET /api/v1/cases/{case_id}/evidence`: Evidence DAG (returns `EvidenceItem[]`)
- `POST /api/v1/cases/{case_id}/reports`: Generate Dossier / Section 94 PDF

## Code Layout & File Ownership
| File Path | Owning Milestone | Purpose |
|---|---|---|
| `frontend/src/index.css` | M1 | CSS custom properties, dual-mode theme tokens, global utility overrides |
| `frontend/tailwind.config.js` | M1 | Tailwind color tokens, font configurations, theme variables mapping |
| `frontend/src/App.tsx` | M1 | Root layout, header, theme toggle persistence, health indicator |
| `frontend/src/components/graph/InvestigationGraphCanvas.tsx` | M2 | Cytoscape graph canvas, pill nodes, curved edges, path-to-root glow, toolbar |
| `frontend/src/components/graph/TraceStatsBar.tsx` | M2 | Floating stats bar with hop depth and pruned node counts |
| `frontend/src/components/graph/GraphDetailDrawer.tsx` | M3 | Reactor Entity Profiler, wallet card, VASP attribution, 2-col stats, narrative |
| `frontend/src/components/cases/CaseDetailsView.tsx` | M4 | Command header, FIR/victim/loss, Reactor subnav tabs with active underline |
| `frontend/src/components/cases/CaseNotesModal.tsx` | M4 | Notes modal (timestamped entry & full notes editing) |
| `frontend/src/components/reports/ReportExportModal.tsx` | M4 | ReportLab legal dossier & Section 94 export modal |
| `frontend/src/components/findings/ForensicFindingsPanel.tsx` | Read-only in M4 | Alerts panel & compact drawer alerts |
| `backend/**` | READ-ONLY (DO NOT MODIFY) | Pristine backend services and tests |
| `chainalysis-reactor-clone/**` | READ-ONLY (DO NOT MODIFY) | Reference material only |
