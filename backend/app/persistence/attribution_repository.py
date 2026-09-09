from decimal import Decimal
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from backend.app.persistence.models import AttributionResult
from backend.app.domain.attribution.models import VASPCandidate, AttributionReport


class AttributionRepository:
    """
    Persistence layer for VASP attribution hypotheses and factor evidence.
    """

    @staticmethod
    async def save_report(
        session: AsyncSession,
        report: AttributionReport,
    ) -> List[AttributionResult]:
        # Clear existing attribution records for this trace to prevent duplicates
        await session.execute(delete(AttributionResult).where(AttributionResult.trace_id == report.trace_id))

        db_records: List[AttributionResult] = []
        for c in report.candidates:
            record = AttributionResult(
                trace_id=report.trace_id,
                vasp_id=c.vasp_id,
                vasp_name=c.vasp_name,
                candidate_address=c.candidate_address,
                confidence=Decimal(str(c.confidence)),
                confidence_band=c.confidence_band,
                direct_tag_score=Decimal(str(c.factors.direct_tag)),
                downstream_match_score=Decimal(str(c.factors.downstream_vasp_match)),
                sweep_score=Decimal(str(c.factors.sweep)),
                fan_in_score=Decimal(str(c.factors.fan_in)),
                temporal_score=Decimal(str(c.factors.temporal)),
                verification_status=c.verification_status,
                explanation={
                    "hypothesis_label": c.hypothesis_label,
                    "confidence_percentage": c.confidence_percentage,
                    "factors": c.factors.model_dump(mode="json"),
                    "explanations": c.explanations.model_dump(mode="json"),
                    "evidence_bullet_points": c.evidence_bullet_points,
                    "sweep_details": c.sweep_details.model_dump(mode="json") if c.sweep_details else None,
                    "fan_in_details": c.fan_in_details.model_dump(mode="json") if c.fan_in_details else None,
                    "temporal_details": c.temporal_details.model_dump(mode="json") if c.temporal_details else None,
                },
            )
            session.add(record)
            db_records.append(record)

        await session.commit()
        return db_records

    @staticmethod
    async def get_by_trace_id(
        session: AsyncSession,
        trace_id: str,
    ) -> List[AttributionResult]:
        query = (
            select(AttributionResult)
            .where(AttributionResult.trace_id == trace_id)
            .order_by(AttributionResult.confidence.desc())
        )
        result = await session.execute(query)
        return list(result.scalars().all())
