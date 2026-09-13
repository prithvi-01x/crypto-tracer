"""
Tests for Feature 12: DPDP Act 2023 PII Encryption at Rest.
Verifies AES-256-GCM authenticated encryption, raw SQL storage verification,
ORM transparent decryption, tamper resistance, and legacy plaintext resilience.
"""
import base64
import pytest
from httpx import AsyncClient
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.persistence.models import Case
from backend.app.persistence.case_repository import CaseRepository
from backend.app.api.v1.schemas.cases import CaseCreate
from backend.app.core.crypto import (
    encrypt_text,
    decrypt_text,
    get_encryption_key,
    NONCE_LENGTH_BYTES,
    TAG_LENGTH_BYTES,
)


def test_aes_256_gcm_primitives():
    """Verifies AES-256-GCM encryption, decryption, and nonce uniqueness."""
    key = get_encryption_key()
    assert len(key) == 32, "Derived AES key must be exactly 256 bits (32 bytes)."

    plaintext = "Sensitive Complainant Aadhar & Bank Info 2026"
    c1 = encrypt_text(plaintext)
    c2 = encrypt_text(plaintext)

    assert c1 is not None and c2 is not None
    # Randomized CSPRNG nonces guarantee distinct ciphertexts for identical plaintext
    assert c1 != c2

    # Decoding base64 confirms minimum envelope length
    raw1 = base64.b64decode(c1.encode("ascii"))
    min_expected = NONCE_LENGTH_BYTES + len(plaintext.encode("utf-8")) + TAG_LENGTH_BYTES
    assert len(raw1) >= min_expected

    # Decryption recovers exact plaintext
    assert decrypt_text(c1) == plaintext
    assert decrypt_text(c2) == plaintext


def test_tamper_detection_resilience():
    """Corrupted ciphertext or tampered authentication tag is safely handled."""
    plaintext = "Tamper Proof Witness Account"
    cipher_b64 = encrypt_text(plaintext)
    assert cipher_b64 is not None

    raw = bytearray(base64.b64decode(cipher_b64.encode("ascii")))
    # Flip bits in the ciphertext payload
    raw[15] ^= 0xFF
    tampered_b64 = base64.b64encode(bytes(raw)).decode("ascii")

    # AES-GCM authentication tag verification fails; graceful fallback returns ciphertext rather than crashing
    decrypted = decrypt_text(tampered_b64)
    assert decrypted != plaintext


def test_legacy_plaintext_resilience():
    """Unencrypted legacy plaintexts are handled gracefully without raising exceptions."""
    legacy = "Pre-DPDP Plaintext Victim Name"
    assert decrypt_text(legacy) == legacy
    assert decrypt_text(None) is None
    assert decrypt_text("") == ""


@pytest.mark.asyncio
async def test_raw_sql_at_rest_encryption_verification(test_engine):
    """
    Direct raw SQL query against database engine confirms that PII columns
    (victim_reference, ack_number, notes) are stored strictly as encrypted Base64
    at rest and contain zero cleartext.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker

    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    victim_secret = "Ramesh Kumar S/O Mohan Lal"
    ack_secret = "1930-PORTAL-DELHI-998877"
    notes_secret = "Victim transferred Rs. 15,00,000 from SBI Account 123456789012"

    async with session_factory() as session:
        created_case = await CaseRepository.create(
            session=session,
            case_data=CaseCreate(
                fir_number="FIR-2026-DPDP-001",
                victim_reference=victim_secret,
                loss_amount_inr=1500000.00,
                ack_number=ack_secret,
                notes=notes_secret,
            ),
        )
        case_id = created_case.id

    # Raw SQL inspection bypassing ORM TypeDecorators
    async with session_factory() as session:
        raw_result = await session.execute(
            text("SELECT victim_reference, ack_number, notes FROM cases WHERE id = :case_id"),
            {"case_id": case_id},
        )
        row = raw_result.first()
        assert row is not None

        raw_victim, raw_ack, raw_notes = row[0], row[1], row[2]

        # 1. Plaintext MUST NOT exist in raw database columns
        assert victim_secret not in raw_victim, "Plaintext victim name was found stored in raw database!"
        assert ack_secret not in raw_ack, "Plaintext 1930 ack number was found stored in raw database!"
        assert notes_secret not in raw_notes, "Plaintext sensitive bank notes found stored in raw database!"

        # 2. Raw columns MUST be valid Base64 ciphertexts
        assert base64.b64decode(raw_victim.encode("ascii"), validate=True)
        assert base64.b64decode(raw_ack.encode("ascii"), validate=True)
        assert base64.b64decode(raw_notes.encode("ascii"), validate=True)

    # ORM query verifies transparent automatic decryption
    async with session_factory() as session:
        orm_res = await session.execute(select(Case).where(Case.id == case_id))
        orm_case = orm_res.scalars().first()
        assert orm_case is not None
        assert orm_case.victim_reference == victim_secret
        assert orm_case.ack_number == ack_secret
        assert orm_case.notes == notes_secret


@pytest.mark.asyncio
async def test_api_transparent_decryption(async_client: AsyncClient):
    """FastAPI case endpoints return cleanly decrypted PII over HTTPS API responses."""
    victim_name = "Sunita Deshmukh"
    ack_code = "1930-MH-2026-7788"
    notes_body = "Digital arrest extortion via fake Supreme Court summons"

    create_res = await async_client.post(
        "/api/v1/cases",
        json={
            "fir_number": "FIR-2026-API-DPDP",
            "victim_reference": victim_name,
            "loss_amount_inr": 750000.00,
            "ack_number": ack_code,
            "notes": notes_body,
        },
    )
    assert create_res.status_code == 201
    data = create_res.json()
    assert data["victim_reference"] == victim_name
    assert data["ack_number"] == ack_code
    assert data["notes"] == notes_body

    # GET endpoint also transparently serves decrypted content
    get_res = await async_client.get(f"/api/v1/cases/{data['id']}")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["victim_reference"] == victim_name
    assert get_data["ack_number"] == ack_code
    assert get_data["notes"] == notes_body
