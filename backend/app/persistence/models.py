import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Numeric,
    Text,
    DateTime,
    Integer,
    JSON,
    ForeignKey,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Case(Base):
    __tablename__ = "cases"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    fir_number = Column(String(100), nullable=False, index=True)
    victim_reference = Column(String(100), nullable=True)
    loss_amount_inr = Column(Numeric(precision=15, scale=2), nullable=True)
    ack_number = Column(String(100), nullable=True)
    suspect_wallet = Column(String(255), nullable=True)
    chain = Column(String(50), nullable=False, default="TRON")
    asset = Column(String(50), nullable=False, default="TRC20:USDT")
    status = Column(String(50), nullable=False, default="OPEN", index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    traces = relationship("Trace", back_populates="case", cascade="all, delete-orphan", lazy="selectin")


class Trace(Base):
    __tablename__ = "traces"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    chain = Column(String(50), nullable=False, default="TRON")
    input_type = Column(String(20), nullable=False, default="address")
    input_value = Column(String(255), nullable=False)
    asset = Column(String(50), nullable=False, default="TRC20:USDT")
    status = Column(String(50), nullable=False, default="QUEUED", index=True)
    max_hops = Column(Integer, nullable=False, default=4)
    min_relevant_usd = Column(Numeric(precision=10, scale=2), nullable=False, default=1.00)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    engine_version = Column(String(50), nullable=False, default="0.1.0")
    config = Column(JSON, nullable=True)

    case = relationship("Case", back_populates="traces")
