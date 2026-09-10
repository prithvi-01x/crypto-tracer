"""
Seed Exactly 10 Curated Cybercrime Investigation Cases for Demo Presentation.
Purges test-run artifacts (FIR-2026-TEST-*, FIR-2026-AUDIT-*, etc.) and ensures
the canonical SIH 2026 demo case (FIR-2026-DEL-CY-0812) is the primary case (with trace),
followed by 9 realistic, high-fidelity Indian Law Enforcement cybercrime cases.
"""
import asyncio
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Dict, Any
from sqlalchemy import select
from backend.app.persistence.db import async_session_factory
from backend.app.persistence.models import Case
from backend.app.domain.demo.canonical_data import (
    CANONICAL_CASE_ID,
    CANONICAL_FIR,
    CANONICAL_VICTIM,
    CANONICAL_LOSS_INR,
    CANONICAL_ACK,
    CANONICAL_CHAIN,
    CANONICAL_ASSET,
    CANONICAL_NOTES,
    ADDR_SUSPECT_ROOT,
)

CURATED_DEMO_CASES: List[Dict[str, Any]] = [
    {
        "id": CANONICAL_CASE_ID,
        "fir_number": CANONICAL_FIR,
        "victim_reference": CANONICAL_VICTIM,
        "loss_amount_inr": CANONICAL_LOSS_INR,
        "ack_number": CANONICAL_ACK,
        "suspect_wallet": ADDR_SUSPECT_ROOT,
        "chain": CANONICAL_CHAIN,
        "asset": CANONICAL_ASSET,
        "notes": CANONICAL_NOTES,
        "status": "OPEN",
        "days_ago": 0,  # Most recent: appears at the top of the Case Register
    },
    {
        "id": "10000000-0000-0000-0000-000000000421",
        "fir_number": "FIR-2026-MUM-CY-0421",
        "victim_reference": "Priya Sunderam",
        "loss_amount_inr": Decimal("3500000.00"),
        "ack_number": "1930-MUM-2026-0421",
        "suspect_wallet": "TPriyaLossExitMUM42199999999999999",
        "chain": "TRON",
        "asset": "TRC20:USDT",
        "notes": (
            "WhatsApp Pig Butchering Scam: Complainant lured into fraudulent liquidity farming pool "
            "via WhatsApp investment adviser. Initial deposits yielded fabricated returns before total withdrawal lockout."
        ),
        "status": "OPEN",
        "days_ago": 1,
    },
    {
        "id": "20000000-0000-0000-0000-000000000955",
        "fir_number": "FIR-2026-BLR-CY-0955",
        "victim_reference": "Arunachalam Murthy",
        "loss_amount_inr": Decimal("8250000.00"),
        "ack_number": "1930-BLR-2026-0955",
        "suspect_wallet": "TArunIPOAllocationBLR9559999999999",
        "chain": "TRON",
        "asset": "TRC20:USDT",
        "notes": (
            "Fake Pre-IPO Allocation Scam: Syndicate promised discounted institutional allocations of upcoming "
            "web3 token offerings. Funds routed through multiple unhosted wallets in Karnataka jurisdiction."
        ),
        "status": "OPEN",
        "days_ago": 2,
    },
    {
        "id": "30000000-0000-0000-0000-000000000318",
        "fir_number": "FIR-2026-HYD-CY-0318",
        "victim_reference": "Dr. K. Venkatesh",
        "loss_amount_inr": Decimal("12000000.00"),
        "ack_number": "1930-HYD-2026-0318",
        "suspect_wallet": "TVenkateshExtortionHYD31899999999",
        "chain": "TRON",
        "asset": "TRC20:USDT",
        "notes": (
            "Digital Arrest & Law Enforcement Extortion: Victim coerced during a 72-hour Skype digital arrest "
            "by operatives impersonating CBI and ED officials. Mutual fund redemptions converted to TRC-20 USDT."
        ),
        "status": "OPEN",
        "days_ago": 3,
    },
    {
        "id": "40000000-0000-0000-0000-000000000174",
        "fir_number": "FIR-2026-GGN-CY-0174",
        "victim_reference": "Rohit Malhotra",
        "loss_amount_inr": Decimal("2400000.00"),
        "ack_number": "1930-GGN-2026-0174",
        "suspect_wallet": "TRohitForexArbitrageGGN1749999999",
        "chain": "TRON",
        "asset": "TRC20:USDT",
        "notes": (
            "Forex Arbitrage Bot Scam: Fraudulent MetaTrader 5 brokerage cloned legitimate market feeds. "
            "Suspect wallet distributed funds into rapid automated pass-through mule layers."
        ),
        "status": "OPEN",
        "days_ago": 4,
    },
    {
        "id": "50000000-0000-0000-0000-000000000632",
        "fir_number": "FIR-2026-PUN-CY-0632",
        "victim_reference": "Sneha Kulkarni",
        "loss_amount_inr": Decimal("1850000.00"),
        "ack_number": "1930-PUN-2026-0632",
        "suspect_wallet": "TSnehaRatingFraudPUN6329999999999",
        "chain": "TRON",
        "asset": "TRC20:USDT",
        "notes": (
            "E-Commerce Product Rating Fraud: Work-from-home scam offering commissions for rating travel portals. "
            "Victim pressured into high-value VIP prepaid tasks with locked redemption."
        ),
        "status": "OPEN",
        "days_ago": 5,
    },
    {
        "id": "60000000-0000-0000-0000-000000000289",
        "fir_number": "FIR-2026-KOL-CY-0289",
        "victim_reference": "Debashish Banerjee",
        "loss_amount_inr": Decimal("4500000.00"),
        "ack_number": "1930-KOL-2026-0289",
        "suspect_wallet": "TDebashishDrainerKOL2899999999999",
        "chain": "TRON",
        "asset": "TRC20:USDT",
        "notes": (
            "Permit Phishing Drainer: Victim signed a malicious TRC-20 Permit authorization on a spoofed "
            "decentralized staking portal. Stolen tokens transferred across 3 intermediary hops."
        ),
        "status": "OPEN",
        "days_ago": 6,
    },
    {
        "id": "70000000-0000-0000-0000-000000000514",
        "fir_number": "FIR-2026-AHM-CY-0514",
        "victim_reference": "Rajesh Shah",
        "loss_amount_inr": Decimal("6500000.00"),
        "ack_number": "1930-AHM-2026-0514",
        "suspect_wallet": "TRajeshP2PLaundryAHM5149999999999",
        "chain": "TRON",
        "asset": "TRC20:USDT",
        "notes": (
            "P2P Merchant Mule Network: Mule accounts used to purchase USDT from verified P2P merchants "
            "on behalf of overseas cyber syndicates using compromised domestic bank accounts."
        ),
        "status": "OPEN",
        "days_ago": 7,
    },
    {
        "id": "80000000-0000-0000-0000-000000000761",
        "fir_number": "FIR-2026-CHE-CY-0761",
        "victim_reference": "Meenakshi Sundaram",
        "loss_amount_inr": Decimal("2800000.00"),
        "ack_number": "1930-CHE-2026-0761",
        "suspect_wallet": "TMeenakshiRomanceCHE7619999999999",
        "chain": "TRON",
        "asset": "TRC20:USDT",
        "notes": (
            "Matrimonial Social Engineering: Fraudulent profile on matrimonial site claimed an expensive "
            "custom parcel was detained at airport customs requiring progressive release fees in USDT."
        ),
        "status": "OPEN",
        "days_ago": 8,
    },
    {
        "id": "90000000-0000-0000-0000-000000000883",
        "fir_number": "FIR-2026-CHD-CY-0883",
        "victim_reference": "Harpreet Singh",
        "loss_amount_inr": Decimal("9500000.00"),
        "ack_number": "1930-CHD-2026-0883",
        "suspect_wallet": "THarpreetRansomCHD883999999999999",
        "chain": "TRON",
        "asset": "TRC20:USDT",
        "notes": (
            "Corporate Ransomware Extortion: Manufacturing plant data servers encrypted by BlackCat affiliate. "
            "Decryption key extortion payment demanded and routed through unhosted mixer wallets."
        ),
        "status": "OPEN",
        "days_ago": 9,
    },
]


async def seed_curated_demo_cases():
    curated_ids = {c["id"] for c in CURATED_DEMO_CASES}
    curated_firs = {c["fir_number"] for c in CURATED_DEMO_CASES}
    now = datetime.now(timezone.utc)

    async with async_session_factory() as session:
        # 1. Delete all non-curated cases (test runs, leftover audit artifacts)
        res = await session.execute(select(Case))
        existing_cases = res.scalars().all()
        for case in existing_cases:
            if case.id not in curated_ids and case.fir_number not in curated_firs:
                await session.delete(case)
        await session.commit()

        # 2. Insert or update the 10 curated cases
        for case_data in CURATED_DEMO_CASES:
            case_id = case_data["id"]
            fir_num = case_data["fir_number"]
            case_time = now - timedelta(days=case_data["days_ago"], hours=case_data["days_ago"] * 2)

            existing_res = await session.execute(
                select(Case).where((Case.id == case_id) | (Case.fir_number == fir_num))
            )
            existing = existing_res.scalars().first()

            if existing:
                existing.fir_number = fir_num
                existing.victim_reference = case_data["victim_reference"]
                existing.loss_amount_inr = case_data["loss_amount_inr"]
                existing.ack_number = case_data["ack_number"]
                existing.suspect_wallet = case_data["suspect_wallet"]
                existing.chain = case_data["chain"]
                existing.asset = case_data["asset"]
                existing.notes = case_data["notes"]
                existing.status = case_data["status"]
                existing.created_at = case_time
                existing.updated_at = case_time
            else:
                new_case = Case(
                    id=case_id,
                    fir_number=fir_num,
                    victim_reference=case_data["victim_reference"],
                    loss_amount_inr=case_data["loss_amount_inr"],
                    ack_number=case_data["ack_number"],
                    suspect_wallet=case_data["suspect_wallet"],
                    chain=case_data["chain"],
                    asset=case_data["asset"],
                    notes=case_data["notes"],
                    status=case_data["status"],
                    created_at=case_time,
                    updated_at=case_time,
                )
                session.add(new_case)
        await session.commit()

        # 3. Verify total count
        count_res = await session.execute(select(Case).order_by(Case.created_at.desc()))
        all_cases = count_res.scalars().all()
        print(f"Successfully seeded curated cases! Total in database: {len(all_cases)}")
        for i, c in enumerate(all_cases):
            print(f"  {i+1}. [{c.fir_number}] {c.victim_reference} - ₹{c.loss_amount_inr:,.2f} ({c.status})")


if __name__ == "__main__":
    asyncio.run(seed_curated_demo_cases())
