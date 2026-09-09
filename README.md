# Crypto-Tracer

> Desktop-first blockchain forensic investigation platform for tracing illicit cryptocurrency fund flows and attributing unhosted deposit addresses to custodial Virtual Asset Service Providers (VASPs).

[![SIH 2026](https://img.shields.io/badge/SIH-2026%20Prototype-blue.svg)](https://sih.gov.in/)
[![Network](https://img.shields.io/badge/Network-TRON%20%28TRC--20%20USDT%29-red.svg)](https://tron.network/)
[![Backend](https://img.shields.io/badge/Backend-FastAPI%20%7C%20Python%203.12-emerald.svg)](https://fastapi.tiangolo.com/)
[![Frontend](https://img.shields.io/badge/Frontend-React%2018%20%7C%20TypeScript-cyan.svg)](https://react.dev/)
[![Database](https://img.shields.io/badge/Database-PostgreSQL%2016%20%7C%20Redis%207-darkblue.svg)](https://www.postgresql.org/)
[![Tests](https://img.shields.io/badge/Tests-83%20Passing-brightgreen.svg)]()
[![Validation Score](https://img.shields.io/badge/SIH%20Readiness-9.8%20%2F%2010-purple.svg)]()

---

## Overview

Crypto-Tracer is a desktop-first forensic analysis platform built to assist cybercrime investigating officers (IOs) and law enforcement analysts in tracing defrauded crypto funds.

The platform addresses the operational bottleneck that occurs when defrauded funds enter unhosted cryptocurrency wallets. In contemporary cyber-financial fraud, criminals rapidly funnel stolen assets through multi-tier intermediary mule wallets before sweeping them into custodial exchange accounts for fiat liquidation. While raw blockchain explorers display individual transactions, investigating officers must manually inspect dozens of tabs, struggle with micro-dust transaction noise, and manually correlate exchange deposit patterns.

Crypto-Tracer automates multi-hop TRC-20 token tracing, applies dynamic dust-relevance pruning, calculates explainable multi-factor VASP attribution scores, maintains an unbroken cryptographic evidence Directed Acyclic Graph (DAG), and compiles court-admissible legal deliverables aligned with modern Indian procedural law.

The platform enforces a foundational architectural principle:
- **Transaction tracing is deterministic:** On-chain fund movements, token transfers, block timestamps, and ledger balances are immutable mathematical facts extracted directly from blockchain consensus nodes.
- **VASP attribution is inferential:** Linking an unhosted wallet address to a custodial exchange is an investigative hypothesis derived from clustering heuristics and behavioral patterns. Every attribution requires human investigator validation before statutory action is taken.

---

## The Problem

In modern cyber-financial fraud across India (including task-based investment scams, part-time job fraud, digital arrest extortion, and illegal betting), fraud syndicates launder illicit proceeds predominantly through Tether USD (USDT) on the TRON (TRC-20) network.

Investigating Officers face three severe operational bottlenecks:

1. **Investigation Latency:** Manual tracing across public block explorers takes hours or days. By the time an investigator manually identifies an exchange deposit address, the fraudsters have already liquidated the assets into fiat via P2P markets or withdrawn them.
2. **Micro-Dust Transaction Noise:** Syndicates intentionally inject dozens of low-value transfers ($0.10 to $0.80) to confuse automated scrapers, create exponential branching in visual graph tools, and exhaust investigator bandwidth.
3. **Evidentiary Inadmissibility:** Screenshots of block explorer web pages lack cryptographic hash integrity, tamper verification, and compliance with statutory standards required in Indian criminal courts.

---

## The Solution

Crypto-Tracer replaces ad-hoc block explorer lookups with an integrated forensic pipeline:

- **Automated Multi-Hop Traversal:** Recursively traces TRC-20 USDT transfers up to 4 hops downstream from root suspect addresses in sub-second execution time.
- **Relevance-Aware Noise Pruning:** Automatically isolates the primary illicit money trail by filtering out micro-dust transfers and secondary operational noise while preserving complete conservation of funds in audit ledgers.
- **Multi-Factor VASP Attribution Heuristics:** Evaluates candidate deposit addresses against exchange sweep consolidation ratios, fan-in convergence, and programmatic temporal delays to identify likely custodial endpoints.
- **Cryptographic Evidence DAG:** Secures every observed transaction, derived metric, and attribution hypothesis into a tamper-evident Directed Acyclic Graph with RFC-8785 canonical JSON payloads and SHA-256 content hashes.
- **Automated Statutory Legal Drafting:** Instantly generates court-admissible Section 63 BSA Evidence Dossiers and ready-to-serve Section 94 BNSS production orders for law enforcement officers.

---

## Intended Audience & Operational Context

Crypto-Tracer is purpose-built for law enforcement personnel and financial crime specialists:

- **Cybercrime Investigating Officers (IOs):** State police cyber cells and local cyber police stations handling 1930 portal complaints and formal First Information Reports (FIRs).
- **Forensic Intelligence Analysts:** Technical analysts conducting complex multi-wallet flow analysis, fund layering reconstruction, and exchange cluster mapping.
- **Supervisory Law Enforcement Officers:** Senior officers reviewing evidence dossiers and authorizing statutory production notices under Section 94 BNSS prior to formal dispatch to exchange legal compliance desks.

> **Operational Scope Note:** Crypto-Tracer is an investigative intelligence and decision-support workstation. It generates verifiable evidentiary trails and draft legal notices to accelerate lawful investigation. The system does not autonomously freeze accounts, execute financial transactions, or bypass judicial or police oversight.

---

## End-to-End Investigation Workflow

The platform implements an integrated 9-stage investigative pipeline:

```
[Case Registration] 
        │
        ▼
[Root Suspect Ingestion] (Wallet Address / Tx Hash)
        │
        ▼
[Multi-Hop BFS Traversal] (TRC-20 USDT Transfer Events)
        │
        ▼
[Relevance Pruning] (Dust Threshold & Volume Ratio Filtering)
        │
        ▼
[Interactive Graph Canvas] (Visual Flow Exploration & Node Inspection)
        │
        ▼
[VASP Attribution Engine] (Multi-Factor Heuristic Scoring)
        │
        ▼
[Cryptographic Evidence DAG] (RFC-8785 Canonical JSON & SHA-256 Hashes)
        │
        ▼
[Investigator Review] (Officer Verification & Hypothesis Acceptance)
        │
        ▼
[Statutory Document Generation] (Section 63 BSA Dossier & Section 94 BNSS Order)
```

1. **Case Registration:** The investigator inputs formal incident metadata (FIR number, complainant details, reported loss amount in INR and USDT equivalent).
2. **Suspect Ingestion:** The initial fraudulent receiving wallet address or transaction ID is ingested as the root suspect node.
3. **Multi-Hop Traversal:** The traversal engine queries on-chain TRC-20 transfer logs, expanding outbound fund paths hop-by-hop.
4. **Relevance Pruning:** Automated pruning algorithms filter out noise while recording pruned volume in the case ledger.
5. **Graph Visualization:** The transaction topology is rendered on an interactive Cytoscape.js canvas with hop levels, node types, and edge amounts.
6. **VASP Attribution:** Downstream endpoints are evaluated against direct registry tags and indirect sweep patterns to identify candidate exchange deposit addresses.
7. **Evidence Provenance:** Every fact and metric is logged as an immutable evidence record with cryptographic parent linkages.
8. **Investigator Review:** The investigator inspects individual signals and formally reviews the attribution hypothesis.
9. **Legal Drafting:** The system compiles the complete Section 63 BSA Evidence Dossier PDF and Section 94 BNSS Legal Production Notice PDF.

---

## Core Capabilities

| Capability | Technical Description | Operational Benefit |
|---|---|---|
| **TRC-20 Ingestion** | Real-time TRON RPC / TronGrid HTTP integration with fallback fixture support. | Ingests live transfer logs and transaction receipts directly from TRON mainnet. |
| **Multi-Hop BFS Traversal** | Directed graph traversal with cycle detection and configurable hop bounds (1–6 hops). | Traces funds through complex mule layering networks in under 20 milliseconds. |
| **Dual-Mode Noise Pruning** | Combined absolute dust threshold ($100 USD) and relative tranche ratio (10%). | Eliminates visual clutter without losing track of total stolen fund volume. |
| **VASP Attribution Engine** | 4-factor scoring heuristic combining direct tags, downstream sweep, fan-in, and timing. | Identifies exchange deposit wallets even when the specific address is unlisted. |
| **Evidence DAG Workstation** | Cryptographic Directed Acyclic Graph tracking OBSERVED, DERIVED, and INFERRED records. | Provides full auditability and parent-child provenance for all forensic conclusions. |
| **Canonical JSON Hashing** | RFC-8785 compliant canonical payload serialization before SHA-256 hash generation. | Guarantees deterministic, tamper-evident document and record verification. |
| **Section 63 BSA Dossier** | Automated PDF generation including case summary, transaction ledger, and hash chains. | Meets strict electronic record admissibility requirements under Indian evidence law. |
| **Section 94 BNSS Order** | Automated drafting of formal police production notices to exchange compliance officers. | Accelerates the formal KYC and account-freeze request process from days to minutes. |

---

## Blockchain Layer: TRON & TRC-20 USDT Tracing

Over 90% of contemporary cyber-financial crime reported on the Indian National Cyber Crime Reporting Portal (1930) involves Tether USD (USDT) on the TRON blockchain. The TRON network is preferred by illicit syndicates due to its minimal network fees (approx. $1–$2 per transfer) and rapid block confirmation times (approx. 3 seconds).

### Smart Contract Transfer Event Decoding
USDT on TRON is implemented as a TRC-20 token contract at address `TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t`. Fund transfers occur through smart contract `triggerconstantcontract` or `triggersmartcontract` calls triggering the standardized `Transfer` event:

$$\text{Transfer}(\text{address indexed from}, \text{address indexed to}, \text{uint256 value})$$

### Address Encoding & Representation
TRON uses dual address formats:
- **Base58Check Format:** Human-readable addresses starting with `T` (e.g., `TSuspectScamRootWallet111111111111`), carrying a 4-byte checksum.
- **Hexadecimal Format:** 42-character raw byte string starting with `41` (the TRON mainnet address prefix byte, corresponding to Ethereum's `0x`).

Crypto-Tracer normalizes all addresses to Base58Check across the API and persistence layers, performing cryptographic checksum verification on every ingested input.

---

## Multi-Hop Graph Traversal Engine

The core traversal engine expands transaction paths from suspect wallets using an optimized Breadth-First Search (BFS) algorithm implemented with NetworkX:

- **Search Algorithm:** Directed Breadth-First Search starting from the root suspect wallet node $V_0$.
- **Configurable Hop Limit:** Investigations are bounded by a configurable depth limit (default: 4 hops, range: 1 to 6 hops) to maintain focus on the immediate laundering chain and prevent unbounded graph expansion.
- **Graph Representation:** Directed multigraph $G = (V, E)$ where vertices $V$ represent unhosted wallets, smart contracts, or VASP clusters, and directed edges $E$ represent confirmed on-chain TRC-20 token transfers.
- **Cycle & Re-entry Detection:** The engine tracks visited wallet addresses per path to detect circular layering loops (where funds are circulated between mule wallets to artificially simulate legitimate trading activity).
- **Sub-Second Performance:** In benchmark evaluations on 4-hop layering networks with 50+ transfers, graph generation completes in 12–25 milliseconds.

---

## Relevance Pruning & Noise Reduction

Illicit syndicates deliberately pollute transaction histories with dozens of micro-value transactions (dusting attacks and micro-splits) to evade automated analysis. Unfiltered graph visualizations rapidly become illegible "hairballs" containing hundreds of irrelevant nodes.

### Dual-Threshold Pruning Criteria
Crypto-Tracer applies an automated, dual-criteria pruning filter:
1. **Absolute Dust Threshold:** Any outgoing transfer with a value below a configurable threshold (default: $100.00 USDT) is flagged as secondary dust.
2. **Relative Volume Threshold:** Any outgoing transfer carrying less than 10% of the total incoming funds received by that wallet is categorized as operational noise or gas fee slippage.

### Conservation of Funds Accounting
Pruning does not mean data loss. Pruned transfers are retained in the database and audit trail:
- The graph canvas collapses pruned branches into a summary metric (`pruned_transfers_count`, `pruned_volume_usd`).
- Investigators can open the Pruning Drawer at any time to inspect all filtered micro-transfers.
- Total input volume equals total retained volume plus total pruned volume, ensuring full financial reconciliation.
