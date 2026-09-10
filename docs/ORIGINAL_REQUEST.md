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
