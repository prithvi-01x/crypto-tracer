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
