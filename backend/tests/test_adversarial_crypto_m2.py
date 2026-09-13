"""
Milestone 2 Cryptographic Rigor & DPDP Act 2023 Verification Harness.
Adversarial test suite designed by Empirical Challenger 2 to stress-test:
1. Direct Raw SQL Database Inspection (plaintext absence, Base64 structure, 12B nonce + CT + 16B tag)
2. Non-deterministic Ciphertext & CSPRNG Nonce Uniqueness across repeated encryptions
3. Authentication Tag Tampering & Bit-Flipping Integrity (InvalidTag detection, no corrupted plaintext leak)
4. ORM Transparency & Mutability Lifecycle (roundtrip transparent decryption, in-place updates, null handling)
5. HKDF-SHA256 Key Derivation & Key Isolation with overrides and hex formats
6. High-concurrency encryption stress and Associated Data (AAD) authentication integrity.
"""
import os
import sys
import base64
import binascii
import asyncio
from concurrent.futures import ThreadPoolExecutor
import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.app.config import settings
from backend.app.persistence.models import Base, Case
from backend.app.persistence.case_repository import CaseRepository
from backend.app.api.v1.schemas.cases import CaseCreate
from backend.app.core.crypto import (
    encrypt_text,
    decrypt_text,
    get_encryption_key,
    CryptoError,
    NONCE_LENGTH_BYTES,
    TAG_LENGTH_BYTES,
    MIN_PAYLOAD_BYTES,
)


# ============================================================================
# 1. Direct Raw SQL Database Inspection
# ============================================================================

@pytest.mark.asyncio
async def test_raw_sql_database_inspection_exact_spec(test_engine):
    """
    Direct Raw SQL Database Inspection:
    Insert a case via repository with victim_reference="Secret Complainant"
    and notes="Private victim statement". Execute raw SQL query
    (SELECT victim_reference, notes FROM cases WHERE id = ...).
    Assert that plaintext strings NEVER appear in raw SQL storage,
    and verify the stored value is valid Base64 containing 12B nonce + ciphertext + 16B tag.
    """
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    victim_secret = "Secret Complainant"
    notes_secret = "Private victim statement"
    ack_secret = "ACK-1930-SECRET-VAL"

    async with session_factory() as session:
        created_case = await CaseRepository.create(
            session=session,
            case_data=CaseCreate(
                fir_number="FIR-CHALLENGE-CRYPTO-001",
                victim_reference=victim_secret,
                notes=notes_secret,
                ack_number=ack_secret,
                loss_amount_inr=500000.0,
            ),
        )
        case_id = created_case.id

    # 1. Inspect raw SQL bypassing SQLAlchemy TypeDecorators
    async with session_factory() as session:
        result = await session.execute(
            text("SELECT victim_reference, notes, ack_number FROM cases WHERE id = :case_id"),
            {"case_id": case_id},
        )
        row = result.first()
        assert row is not None, "Raw SQL row not found for inserted case"
        raw_victim, raw_notes, raw_ack = row[0], row[1], row[2]

        # Assert plaintext strings NEVER appear in raw SQL storage
        assert victim_secret not in raw_victim, f"Plaintext '{victim_secret}' leaked into raw SQL column!"
        assert notes_secret not in raw_notes, f"Plaintext '{notes_secret}' leaked into raw SQL column!"
        assert ack_secret not in raw_ack, f"Plaintext '{ack_secret}' leaked into raw SQL column!"

        # Also assert plaintext does not appear in entire row string representation
        row_repr = str(row)
        assert victim_secret not in row_repr
        assert notes_secret not in row_repr
        assert ack_secret not in row_repr

        # 2. Verify stored values are valid Base64 containing 12B nonce + ciphertext + 16B tag
        for col_name, raw_val, plaintext in [
            ("victim_reference", raw_victim, victim_secret),
            ("notes", raw_notes, notes_secret),
            ("ack_number", raw_ack, ack_secret),
        ]:
            decoded = base64.b64decode(raw_val.encode("ascii"), validate=True)
            expected_ct_len = len(plaintext.encode("utf-8"))
            expected_total_len = NONCE_LENGTH_BYTES + expected_ct_len + TAG_LENGTH_BYTES

            assert len(decoded) == expected_total_len, (
                f"{col_name} byte length mismatch: expected {expected_total_len} "
                f"({NONCE_LENGTH_BYTES}B nonce + {expected_ct_len}B CT + {TAG_LENGTH_BYTES}B tag), "
                f"got {len(decoded)}"
            )

            nonce = decoded[:NONCE_LENGTH_BYTES]
            ciphertext = decoded[NONCE_LENGTH_BYTES:-TAG_LENGTH_BYTES]
            tag = decoded[-TAG_LENGTH_BYTES:]

            assert len(nonce) == 12, f"Nonce must be exactly 12 bytes, got {len(nonce)}"
            assert len(tag) == 16, f"Authentication tag must be exactly 16 bytes, got {len(tag)}"
            assert len(ciphertext) == expected_ct_len, f"Ciphertext length must match plaintext UTF-8 bytes"
            assert ciphertext != plaintext.encode("utf-8"), "Ciphertext matches plaintext bytes!"

    # 3. Direct SQL filter assertion: searching plaintext directly in SQL returns 0 rows
    async with session_factory() as session:
        leak_check = await session.execute(
            text("SELECT id FROM cases WHERE victim_reference = :plain"),
            {"plain": victim_secret},
        )
        assert leak_check.first() is None, "Plaintext SQL query unexpectedly matched encrypted column!"

        like_check = await session.execute(
            text("SELECT id FROM cases WHERE victim_reference LIKE :pattern"),
            {"pattern": f"%{victim_secret}%"},
        )
        assert like_check.first() is None, "Plaintext SQL LIKE query unexpectedly matched encrypted column!"


# ============================================================================
# 2. Non-deterministic Ciphertext & CSPRNG Nonce Uniqueness
# ============================================================================

def test_nondeterministic_ciphertext_and_nonce_uniqueness():
    """
    Non-deterministic Ciphertext:
    Encrypt the identical plaintext twice (and 100 times).
    Verify the ciphertexts are completely distinct due to fresh CSPRNG nonces.
    """
    plaintext = "Empirical Challenger Nonce Collision Test 2026 - Critical PII"
    runs = 100

    ciphertexts = [encrypt_text(plaintext) for _ in range(runs)]
    assert all(c is not None for c in ciphertexts)

    # 1. Distinct ciphertexts
    unique_ciphertexts = set(ciphertexts)
    assert len(unique_ciphertexts) == runs, (
        f"Detected ciphertext collision! Generated {runs} ciphertexts but only {len(unique_ciphertexts)} unique."
    )

    # 2. Distinct nonces
    nonces = []
    for c in ciphertexts:
        raw = base64.b64decode(c.encode("ascii"))
        nonce = raw[:NONCE_LENGTH_BYTES]
        assert len(nonce) == NONCE_LENGTH_BYTES
        nonces.append(nonce)

    unique_nonces = set(nonces)
    assert len(unique_nonces) == runs, (
        f"Detected CSPRNG nonce collision! Generated {runs} nonces but only {len(unique_nonces)} unique."
    )

    # 3. All ciphertexts cleanly decrypt back to identical plaintext
    for c in ciphertexts:
        assert decrypt_text(c) == plaintext


def test_nondeterministic_various_payload_types():
    """Verify non-determinism across diverse character encodings and payload sizes."""
    payloads = [
        "A",  # minimal 1-char
        "पीड़ित विवरण - शिकायतकर्ता नाम",  # Unicode / Devanagari
        "🕵️‍♂️ Confidential Officer Note 🛡️ 0x71c6bf5e5338",  # Emojis & hex
        "Line 1\nLine 2\tTabbed\r\nSpecial: !@#$%^&*()_+=-~`[]{}|;:',.<>?/",  # Special chars
        "A" * 16384,  # 16 KB large payload
    ]

    for p in payloads:
        c1 = encrypt_text(p)
        c2 = encrypt_text(p)
        assert c1 != c2, f"Identical ciphertexts generated for payload: {p[:30]}..."
        assert decrypt_text(c1) == p
        assert decrypt_text(c2) == p


# ============================================================================
# 3. Authentication Tag Tampering & Bit-Flipping Integrity
# ============================================================================

def test_authentication_tag_tampering_bit_flips():
    """
    Authentication Tag Tampering:
    Tamper with a single bit in the ciphertext or tag.
    Verify that decryption raises or catches InvalidTag and does not return corrupted data.
    """
    key = get_encryption_key()
    plaintext = "Authenticity Verification Payload - Section 63 BSA Forensic Seal"
    cipher_b64 = encrypt_text(plaintext)
    assert cipher_b64 is not None

    raw = bytearray(base64.b64decode(cipher_b64.encode("ascii")))
    total_len = len(raw)
    pt_len = len(plaintext.encode("utf-8"))

    # Layout:
    # 0..11: Nonce (12 bytes)
    # 12..(12+pt_len-1): Ciphertext
    # (total_len-16)..total_len-1: Tag (16 bytes)

    tamper_scenarios = [
        ("Tag last byte bit flip", total_len - 1, 0x01),
        ("Tag first byte bit flip", total_len - 16, 0x01),
        ("Tag middle byte bit flip", total_len - 8, 0x80),
        ("Ciphertext first byte bit flip", 12, 0x01),
        ("Ciphertext middle byte bit flip", 12 + (pt_len // 2), 0x02),
        ("Ciphertext last byte bit flip", total_len - 17, 0x04),
        ("Nonce byte 0 bit flip", 0, 0x01),
        ("Nonce byte 11 bit flip", 11, 0x40),
    ]

    for name, byte_idx, bit_mask in tamper_scenarios:
        tampered = bytearray(raw)
        tampered[byte_idx] ^= bit_mask
        tampered_b64 = base64.b64encode(bytes(tampered)).decode("ascii")

        # 1. Direct AESGCM primitive check: MUST raise InvalidTag
        nonce = bytes(tampered[:NONCE_LENGTH_BYTES])
        ct_and_tag = bytes(tampered[NONCE_LENGTH_BYTES:])
        with pytest.raises(InvalidTag):
            AESGCM(key).decrypt(nonce, ct_and_tag, None)

        # 2. Module decrypt_text check: catches InvalidTag and NEVER returns corrupted plaintext
        decrypted = decrypt_text(tampered_b64)
        assert decrypted != plaintext, f"[{name}] Unexpectedly recovered original plaintext!"
        assert plaintext not in (decrypted or ""), f"[{name}] Plaintext leaked in tampered result!"
        # In our implementation, decrypt_text catches InvalidTag and returns fallback (ciphertext string)
        assert decrypted == tampered_b64, f"[{name}] Expected fallback to tampered string on tag failure"


def test_malformed_and_truncated_ciphertext_resilience():
    """Stress test boundary payloads: truncated bytes, invalid base64, corrupted tags."""
    key = get_encryption_key()

    # 1. Sub-minimum length payloads (< 28 bytes)
    short_payloads = [
        b"",
        b"short",
        os.urandom(NONCE_LENGTH_BYTES),  # only nonce, 12 bytes
        os.urandom(27),  # 27 bytes (1 short of 28B minimum)
    ]
    for sp in short_payloads:
        b64 = base64.b64encode(sp).decode("ascii")
        # Direct AESGCM decrypt on < 16B ciphertext+tag must raise InvalidTag
        if len(sp) > NONCE_LENGTH_BYTES:
            with pytest.raises(InvalidTag):
                AESGCM(key).decrypt(sp[:NONCE_LENGTH_BYTES], sp[NONCE_LENGTH_BYTES:], None)
        # decrypt_text handles safely without unhandled exceptions
        res = decrypt_text(b64)
        assert res == b64

    # 2. Tag truncated by 1 byte (27 bytes total when plaintext is 0-length)
    empty_ct_b64 = encrypt_text("")
    raw_empty = bytearray(base64.b64decode(empty_ct_b64.encode("ascii")))
    assert len(raw_empty) == 28  # 12B nonce + 0B CT + 16B tag
    truncated_tag = raw_empty[:-1]  # 27B
    trunc_b64 = base64.b64encode(bytes(truncated_tag)).decode("ascii")
    assert decrypt_text(trunc_b64) == trunc_b64

    # 3. Invalid Base64 strings
    corrupted_b64 = "This is NOT valid base64 !!@@##$$%%^^"
    assert decrypt_text(corrupted_b64) == corrupted_b64

    # 4. None and empty inputs
    assert decrypt_text(None) is None
    assert decrypt_text("") == ""
    assert encrypt_text(None) is None


def test_associated_data_integrity():
    """Verify AEAD Associated Data (AAD) authentication enforcement."""
    key = get_encryption_key()
    plaintext = "Authenticated With Tenant AAD Context"
    aad_correct = b"tenant_id:TN-STATE:district:HQ"
    aad_tampered = b"tenant_id:KL-STATE:district:HQ"

    c_b64 = encrypt_text(plaintext, associated_data=aad_correct)
    assert c_b64 is not None

    # Valid AAD decrypts cleanly
    dec = decrypt_text(c_b64, associated_data=aad_correct)
    assert dec == plaintext

    # Tampered AAD fails authentication
    raw = base64.b64decode(c_b64.encode("ascii"))
    with pytest.raises(InvalidTag):
        AESGCM(key).decrypt(raw[:NONCE_LENGTH_BYTES], raw[NONCE_LENGTH_BYTES:], aad_tampered)

    # Missing AAD fails authentication
    with pytest.raises(InvalidTag):
        AESGCM(key).decrypt(raw[:NONCE_LENGTH_BYTES], raw[NONCE_LENGTH_BYTES:], None)

    # decrypt_text with wrong AAD catches InvalidTag and returns fallback
    wrong_dec = decrypt_text(c_b64, associated_data=aad_tampered)
    assert wrong_dec != plaintext


# ============================================================================
# 4. ORM Transparency & Mutability Lifecycle
# ============================================================================

@pytest.mark.asyncio
async def test_orm_transparency_and_mutability(test_engine):
    """
    ORM Transparency:
    Verify that querying the case back through the SQLAlchemy ORM session
    yields the exact original plaintext strings.
    Verify modifying encrypted fields re-encrypts with a fresh nonce and
    updates raw storage without cleartext leakage.
    """
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    victim_initial = "Secret Complainant Initial"
    notes_initial = "Private victim statement initial"

    # Step A: Insert case
    async with session_factory() as session:
        case = await CaseRepository.create(
            session=session,
            case_data=CaseCreate(
                fir_number="FIR-ORM-TRANS-001",
                victim_reference=victim_initial,
                notes=notes_initial,
                loss_amount_inr=250000.0,
            ),
        )
        case_id = case.id

    # Step B: Query back through ORM session - exact plaintext returned
    async with session_factory() as session:
        orm_res = await session.execute(select(Case).where(Case.id == case_id))
        queried_case = orm_res.scalars().first()
        assert queried_case is not None
        assert queried_case.victim_reference == victim_initial
        assert queried_case.notes == notes_initial

    # Step C: Capture initial raw ciphertexts
    async with session_factory() as session:
        res = await session.execute(
            text("SELECT victim_reference, notes FROM cases WHERE id = :id"),
            {"id": case_id},
        )
        raw1_victim, raw1_notes = res.first()
        assert victim_initial not in raw1_victim
        assert notes_initial not in raw1_notes

    # Step D: Mutate encrypted fields via ORM
    victim_updated = "Amended Complainant Statement Section 164"
    notes_updated = "Revised forensic notes with confirmed VASP wallet attribution"

    async with session_factory() as session:
        orm_res = await session.execute(select(Case).where(Case.id == case_id))
        case_to_update = orm_res.scalars().first()
        case_to_update.victim_reference = victim_updated
        case_to_update.notes = notes_updated
        await session.commit()

    # Step E: Query raw SQL to verify new ciphertexts, fresh nonces, zero plaintext
    async with session_factory() as session:
        res = await session.execute(
            text("SELECT victim_reference, notes FROM cases WHERE id = :id"),
            {"id": case_id},
        )
        raw2_victim, raw2_notes = res.first()

        assert victim_updated not in raw2_victim
        assert notes_updated not in raw2_notes
        assert victim_initial not in raw2_victim
        assert notes_initial not in raw2_notes

        # Raw ciphertexts changed
        assert raw1_victim != raw2_victim
        assert raw1_notes != raw2_notes

        # Fresh nonces used on update
        n1 = base64.b64decode(raw1_victim.encode("ascii"))[:NONCE_LENGTH_BYTES]
        n2 = base64.b64decode(raw2_victim.encode("ascii"))[:NONCE_LENGTH_BYTES]
        assert n1 != n2, "Nonce was reused across ORM field updates!"

    # Step F: Query back through ORM session - updated plaintext returned
    async with session_factory() as session:
        orm_res = await session.execute(select(Case).where(Case.id == case_id))
        case_final = orm_res.scalars().first()
        assert case_final.victim_reference == victim_updated
        assert case_final.notes == notes_updated

    # Step G: Null handling in ORM
    async with session_factory() as session:
        orm_res = await session.execute(select(Case).where(Case.id == case_id))
        case_to_null = orm_res.scalars().first()
        case_to_null.victim_reference = None
        await session.commit()

    async with session_factory() as session:
        res = await session.execute(
            text("SELECT victim_reference FROM cases WHERE id = :id"),
            {"id": case_id},
        )
        raw_null_val = res.scalar()
        assert raw_null_val is None, "Expected SQL NULL in raw database when setting None via ORM"

        orm_res = await session.execute(select(Case).where(Case.id == case_id))
        assert orm_res.scalars().first().victim_reference is None


# ============================================================================
# 5. HKDF-SHA256 Key Derivation & Key Overrides
# ============================================================================

def test_hkdf_sha256_key_derivation_and_overrides():
    """
    Key derivation:
    Test HKDF-SHA256 key derivation with key overrides.
    Verify 256-bit (32B) key expansion, isolation between different keys,
    and cross-key decryption rejection.
    """
    key_alpha_str = "secret-agency-key-alpha-9988"
    key_beta_str = "secret-agency-key-beta-7766"

    k_alpha = get_encryption_key(key_override=key_alpha_str)
    k_beta = get_encryption_key(key_override=key_beta_str)

    # 1. 256-bit key length
    assert len(k_alpha) == 32, f"Expected 32 bytes (256 bits), got {len(k_alpha)}"
    assert len(k_beta) == 32, f"Expected 32 bytes (256 bits), got {len(k_beta)}"

    # 2. Key separation
    assert k_alpha != k_beta, "Different key overrides produced identical HKDF derived keys!"

    # 3. Determinism
    k_alpha_repeat = get_encryption_key(key_override=key_alpha_str)
    assert k_alpha == k_alpha_repeat, "HKDF key derivation must be strictly deterministic!"

    # 4. Cross-key decryption isolation
    secret_message = "Confidential Inter-Agency Intel Payload"
    c_alpha = encrypt_text(secret_message, key_override=key_alpha_str)
    assert c_alpha is not None

    # Decrypting with correct key succeeds
    assert decrypt_text(c_alpha, key_override=key_alpha_str) == secret_message

    # Decrypting with wrong key MUST fail InvalidTag
    raw_alpha = base64.b64decode(c_alpha.encode("ascii"))
    with pytest.raises(InvalidTag):
        AESGCM(k_beta).decrypt(
            raw_alpha[:NONCE_LENGTH_BYTES],
            raw_alpha[NONCE_LENGTH_BYTES:],
            None,
        )

    # decrypt_text safely handles wrong key without leaking plaintext
    wrong_dec = decrypt_text(c_alpha, key_override=key_beta_str)
    assert wrong_dec != secret_message


def test_hex_key_override_and_empty_key_error():
    """Test 64-char hex key passthrough and error on empty key."""
    # 64-char hex key (32 bytes in hex)
    hex_key = "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90"
    derived_hex = get_encryption_key(key_override=hex_key)
    assert derived_hex == bytes.fromhex(hex_key)

    # Plaintext roundtrip with hex key
    msg = "Hex Key Roundtrip Test"
    ct = encrypt_text(msg, key_override=hex_key)
    assert decrypt_text(ct, key_override=hex_key) == msg

    # Whitespace key override strips to empty and raises CryptoError
    with pytest.raises(CryptoError, match="empty"):
        get_encryption_key(key_override="   ")

    # Empty key override is falsy in Python (`if key_override:`); verify it falls back to default key
    fallback_key = get_encryption_key(key_override="")
    assert fallback_key == get_encryption_key(key_override=None)

    # When both SECRET_KEY and ENCRYPTION_KEY are empty, CryptoError is raised
    get_encryption_key.cache_clear()
    try:
        from unittest.mock import patch, PropertyMock
        from backend.app.config import Settings
        with patch.object(Settings, "encryption_key_value", new_callable=PropertyMock, return_value=""):
            with pytest.raises(CryptoError, match="empty"):
                get_encryption_key(key_override=None)
    finally:
        get_encryption_key.cache_clear()


# ============================================================================
# 6. Concurrency & Stress Harness
# ============================================================================

def test_concurrent_encryption_thread_safety():
    """
    Stress test concurrent encryptions of the same plaintext across 50 threads.
    Verify zero race conditions, 100% unique nonces, and clean decryption.
    """
    plaintext = "Concurrent High-Throughput Investigator Telemetry"
    worker_count = 50

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(encrypt_text, plaintext) for _ in range(worker_count)]
        results = [f.result() for f in futures]

    assert len(results) == worker_count
    assert len(set(results)) == worker_count, "Detected duplicate ciphertext under concurrent load!"

    # Check nonces
    nonces = [base64.b64decode(r.encode("ascii"))[:NONCE_LENGTH_BYTES] for r in results]
    assert len(set(nonces)) == worker_count, "Detected duplicate nonce under concurrent load!"

    # Decrypt all
    with ThreadPoolExecutor(max_workers=10) as pool:
        dec_futures = [pool.submit(decrypt_text, r) for r in results]
        dec_results = [f.result() for f in dec_futures]

    assert all(d == plaintext for d in dec_results)


# ============================================================================
# Standalone execution runner
# ============================================================================

if __name__ == "__main__":
    pytest_args = ["-v", "-s", __file__]
    print(f"Executing Milestone 2 Cryptographic Rigor Tests with args: {pytest_args}")
    sys.exit(pytest.main(pytest_args))
