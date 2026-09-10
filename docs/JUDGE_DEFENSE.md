# CRYPTO-TRACER — SIH 2026 JUDGE DEFENSE & ARCHITECTURAL REFERENCE
**Problem Statement:** SIH26182 — Automated Attribution of Unknown Cryptocurrency Wallets to Nearest VASPs  
**Team:** Cipher  
**Statutory Framework:** Section 63 Bharatiya Sakshya Adhiniyam, 2023 (BSA) & Section 94 Bharatiya Nagarik Suraksha Sanhita, 2023 (BNSS)

---

## 1. Executive Summary & Core Defense Q&A

### Q1: What exact problem does Crypto-Tracer solve?
**Answer:**  
In modern cyber-financial fraud (investment task fraud, sextortion, illegal betting, P2P mule networks), victims deposit funds into unhosted cryptocurrency wallets (predominantly TRC-20 USDT on TRON). Fraud syndicates immediately layer stolen assets across 3 to 6 intermediary mule wallets before sweeping them into centralized Virtual Asset Service Provider (VASP / exchange) deposit addresses for fiat conversion.  
Investigating Officers (IOs) face three critical bottlenecks:
1. **Speed:** Manual inspection of raw block explorers takes hours, during which criminals liquidate or withdraw the funds.
2. **Noise:** Fraudsters deliberately inject micro-dust transactions ($0.10 to $0.80) to confuse automated scripts and exhaust graph explorers.
3. **Legal Admissibility:** Screenshots of block explorers lack cryptographic integrity, chain-of-custody provenance, and statutory compliance required under Section 63 of Bharatiya Sakshya Adhiniyam, 2023 (BSA).

Crypto-Tracer provides automated multi-hop BFS traversal, relevance-aware dust pruning, mathematical sweep/temporal VASP attribution, and instant generation of Section 63 BSA evidence dossiers and draft Section 94 BNSS notices in seconds.

---

### Q2: Why isn't this just a wrapper around Tronscan?
**Answer:**  
Tronscan is a generic public block explorer built for single-transaction lookups. It has zero law enforcement intelligence:
- **No Multi-Hop Traversal:** Tronscan cannot follow a transaction 4 hops downstream automatically; an investigator must open dozens of browser tabs manually.
- **No Noise Pruning:** Tronscan displays every spam token and dust transfer, overwhelming the investigator with irrelevant data.
- **No Exchange Sweep Heuristics:** Tronscan does not calculate outgoing consolidation ratios, concentration percentages, or deposit-to-sweep temporal delays.
- **No VASP Attribution Engine:** Tronscan only tags hot wallets that are publicly known; it cannot attribute un-tagged user deposit addresses that sweep into exchanges.
- **No Evidentiary Provenance:** Tronscan does not generate cryptographic SHA-256 DAG hash chains or court-ready legal Section 94 notices.

---

### Q3: How does the VASP Attribution Engine work mathematically?
**Answer:**  
Crypto-Tracer uses a transparent, deterministic multi-factor scoring formula:

$$\text{Confidence} = 0.35 \times \text{DirectTag} + 0.35 \times \text{Sweep} + 0.15 \times \text{FanIn} + 0.15 \times \text{Temporal}$$

1. **Direct Tag / Downstream Match ($0.35$ weight):**
   - If candidate address is verified in the VASP registry: $\text{Tag} = 1.0$.
   - If candidate address is unverified but its outgoing funds sweep into a verified VASP hot wallet: $\text{Effective Tag} = 0.35 \times 0.80 = 0.28$.
2. **Sweep Consolidation ($0.35$ weight):**
   - Calculates $\text{Sweep Ratio} = \text{Amount Swept} / \text{Amount Received}$.
   - Measures dominant destination concentration ($C = \text{Dominant} / \text{Total Outgoing}$).
   - If $\text{Sweep Ratio} \ge 90\%$ and $C \ge 90\%$, $\text{Sweep Score} = 1.0$.
3. **Fan-In Convergence ($0.15$ weight):**
   - Evaluates multi-source inflow: $N \ge 3$ distinct senders scoring $0.60$ to $1.0$, characteristic of omnibus exchange infrastructure.
4. **Temporal Delay ($0.15$ weight):**
   - $T(\Delta t) = e^{-\lambda \Delta t}$. Rapid automated sweeps within 15–30 minutes score $> 0.90$, matching programmatic exchange sweeps rather than human behavior.

**Canonical Scenario Result:**  
$0.35(0.80) + 0.35(1.0) + 0.15(0.30) + 0.15(0.9432) = \mathbf{0.8165}$ (**81.6% HIGH Confidence**, Attributed VASP: **Binance**).

---

### Q4: Why is the confidence score explainable?
**Answer:**  
Crypto-Tracer completely avoids unexplainable black-box machine learning models (LLMs or deep neural networks) in attribution scoring. Under Indian criminal jurisprudence, evidence presented under Section 63 BSA must be verifiable and deterministic:
- Every factor has an exact numerical value and human-readable explanation.
- An investigator or judge can inspect the exact transaction hashes proving the 99.8% sweep and the 14m 2s automated delay.
- The hypothesis is stated as an **investigative finding under Section 94 BNSS**, never as "absolute mathematical proof".

---

### Q5: What happens when a mixer or tumbler is encountered?
**Answer:**  
Crypto-Tracer enforces strict privacy and obfuscation boundaries:
- Traversal halts immediately on that branch upon detecting known mixer contracts (e.g. Tornado Cash, Blender.io, TRON obfuscators).
- The node is highlighted with a crimson **OBFUSCATION BOUNDARY [MIXER]** badge.
- The system **never claims mixer de-anonymization**, which is cryptographically impossible on-chain without off-chain signals.
- Automated Section 94 BNSS generation is disabled for mixer nodes because decentralized smart contracts cannot comply with police summonses.

---

### Q6: What happens when NO VASP is found?
**Answer:**  
- If all branches terminate in unhosted wallets or low-volume endpoints, the candidate is classified as **Unidentified / Unhosted Wallet**.
- Confidence remains below $10\%$ (`LOW` confidence band).
- Marked with `is_low_confidence = True`.
- The system **never fabricates or hallucinates a VASP**. The report clearly instructs the IO to pursue alternative physical leads (KYC from mule accounts, IP logs from ISP).

---

### Q7: Does Crypto-Tracer freeze funds autonomously?
**Answer:**  
**NO.** Crypto-Tracer is strictly an investigative intelligence tool:
- **No private keys:** The application holds zero private keys or credentials.
- **No exchange write access:** It cannot execute trades, transfers, or freezes.
- Statutory freezing authority under Indian law resides solely with the Investigating Officer and Court of Magistrate under Section 106 / Section 94 BNSS.
- The system prepares the formal Section 94 BNSS record-production order and freezing requisition, ready for the officer to review, sign, and serve on the VASP compliance desk.

---

### Q8: What electronic evidence is preserved?
**Answer:**  
In strict compliance with **Section 63 of Bharatiya Sakshya Adhiniyam, 2023 (BSA)**:
- **Observed Facts:** Raw blockchain transfer events, block numbers, transaction hashes, timestamps, normalized USDT amounts.
- **Derived Metrics:** Traversal hop numbers, dust pruning audit records, sweep ratios, fan-in convergence scores.
- **Inferred Hypotheses:** Attribution candidate confidence breakdowns and factor explanations.
- **Human Actions:** Investigator login, trace execution, hypothesis acceptance/rejection with timestamp and badge number.
- **Integrity Seal:** Every evidence item and final PDF dossier is sealed with a deterministic SHA-256 cryptographic digest.

---

### Q9: Is DEMO mode clearly disclosed?
**Answer:**  
**YES, at every layer of the architecture:**
- Database record: `traces.execution_mode = "DEMO"`
- Dashboard UI: Gold `⚡ DEMO REPLAY` / `DEMO FIXTURE` badges.
- Trace Launcher: Explicit selection between `⚡ Demo Replay (Deterministic fixtures)` and `🌐 Live TRON RPC`.
- PDF Dossiers & Section 94 Notices: Bold header warning:  
  `DEMONSTRATION / REPLAY (FIXTURE DATA) — FOR EVALUATION ONLY`.

---

## 2. Performance Benchmarks

Measured on standard commodity workstation hardware (10-run sample, sub-second latency across all modules):

| Operation / Pipeline Stage | Minimum | Average | Maximum |
|---|---|---|---|
| **In-Memory Graph Traversal (4-Hop BFS)** | 0.4 ms | **0.6 ms** | 1.0 ms |
| **VASP Attribution Engine (All Factors)** | 0.3 ms | **0.4 ms** | 0.6 ms |
| **Section 63 BSA Evidence DAG (59 Items)** | 1.2 ms | **1.3 ms** | 1.5 ms |
| **Section 94 BNSS Notice PDF Generation** | 25.4 ms | **27.2 ms** | 32.2 ms |
| **Evidence Dossier PDF Generation (Multi-Page)** | 53.2 ms | **58.3 ms** | 61.7 ms |
| **Full DEMO Pipeline (Seed + BFS + DB Persist)** | 71.1 ms | **101.2 ms** | 203.1 ms |

---

## 3. Test Coverage Summary

- **Total Backend Tests:** 83 passing tests across 12 modules (`test_attribution.py`, `test_boundaries.py`, `test_cases.py`, `test_demo_e2e.py`, `test_evidence.py`, `test_graph_engine.py`, `test_hardening.py`, `test_health.py`, `test_pruning.py`, `test_reports.py`, `test_tron_provider.py`).
- **Pass Rate:** 100% (83/83 passed in 7.49s).
- **Frontend Build:** TypeScript + Vite bundle compilation clean with zero errors (`dist/assets/index-3Pk_3ji0.js`).
