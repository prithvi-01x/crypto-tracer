import asyncio
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Any

from backend.app.adapters.tron_provider import TronProvider
from backend.app.domain.demo.canonical_data import DemoFixtureProvider
from backend.app.domain.tracing.engine import GraphEngine
from backend.app.domain.evidence.generator import EvidenceGenerator
from backend.app.domain.evidence.models import AuditEvent, AuditEventType
from backend.app.domain.evidence.hasher import compute_content_hash
from backend.app.domain.models import InvestigationGraph
from backend.app.domain.attribution.engine import AttributionEngine
from backend.app.domain.reports.dossier_generator import EvidenceDossierGenerator
from backend.app.domain.reports.bnss94_generator import BNSS94DraftGenerator
from backend.app.domain.reports.bsa63_generator import Section63BSAGenerator
from backend.app.persistence.evidence_repository import EvidenceRepository
from backend.app.persistence.audit_repository import AuditRepository
from backend.app.persistence.trace_repository import TraceRepository
from backend.app.persistence.case_repository import CaseRepository
from backend.app.persistence.report_repository import ReportRepository
from backend.app.persistence.models import ReportModel
from backend.app.services.storage import get_storage_service
from backend.app.worker.queue import (
    TraceQueue,
    TraceJobPayload,
    get_trace_queue,
    ReportQueue,
    ReportJobPayload,
    get_report_queue,
)
from backend.app.worker.heartbeat import HeartbeatManager

logger = logging.getLogger("crypto_tracer.worker.fleet")


class TraceWorker:
    """
    Asynchronous worker processing background trace jobs with distributed locking,
    heartbeats, hop progress streaming, and partial/complete state persistence.
    """

    def __init__(
        self,
        worker_id: Optional[str] = None,
        queue: Optional[TraceQueue] = None,
        db_session_factory: Any = None,
        redis_client: Optional[Any] = None,
    ):
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.queue = queue or get_trace_queue(redis_client)
        self.db_session_factory = db_session_factory
        self.redis = redis_client
        self.running = False

    async def run_loop(self):
        """Continuous execution loop polling the job queue."""
        self.running = True
        logger.info(f"TraceWorker [{self.worker_id}] started loop.")
        while self.running:
            try:
                job = await self.queue.pop(timeout_seconds=1.0)
                if job:
                    await self.process_job(job)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"TraceWorker [{self.worker_id}] loop error: {e}", exc_info=True)
                await asyncio.sleep(0.5)

    async def process_job(self, job: TraceJobPayload):
        """Execute a single trace job through its complete lifecycle."""
        trace_id = job.trace_id
        logger.info(f"TraceWorker [{self.worker_id}] processing trace {trace_id}")

        # 1. Early cancellation check
        if await self.queue.is_cancelled(trace_id):
            logger.info(f"Trace {trace_id} was pre-cancelled; skipping.")
            if self.db_session_factory:
                async with self.db_session_factory() as session:
                    await TraceRepository.update_cancelled(
                        session, trace_id, "Pre-cancelled by investigator", tenant_id=job.tenant_id
                    )
            return

        # 2. Acquire distributed execution lock
        acquired = await HeartbeatManager.acquire_lock(
            trace_id=trace_id,
            worker_id=self.worker_id,
            redis_client=self.redis,
            lock_ttl=30,
        )
        if not acquired:
            logger.warning(f"Trace {trace_id} is already locked by another worker. Skipping.")
            return

        hb = HeartbeatManager(
            trace_id=trace_id,
            worker_id=self.worker_id,
            redis_client=self.redis,
            lock_ttl=30,
            heartbeat_interval=5.0,
        )
        await hb.start()

        try:
            # 3. Transition status to RUNNING
            if self.db_session_factory:
                async with self.db_session_factory() as session:
                    await TraceRepository.update_running(
                        session=session,
                        trace_id=trace_id,
                        worker_id=self.worker_id,
                        tenant_id=job.tenant_id,
                    )

            # 4. Broadcast JOB_STARTED
            await self.queue.publish_event(trace_id, {
                "event": "JOB_STARTED",
                "trace_id": trace_id,
                "worker_id": self.worker_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            # 5. Build BlockchainProvider & GraphEngine
            if job.execution_mode.upper() == "LIVE":
                provider = TronProvider(redis_client=self.redis)
            else:
                provider = DemoFixtureProvider()

            engine = GraphEngine(
                provider=provider,
                max_hops=job.max_hops,
                min_relevant_usd=Decimal(job.min_relevant_usd),
            )

            # 6. Progress and Cancellation Callbacks
            async def on_progress(hop: int, max_hops: int, nodes: int, edges: int, pruned: int):
                pct = min(100.0, ((hop + 1) / (max_hops + 1)) * 100.0)
                if self.db_session_factory:
                    async with self.db_session_factory() as session:
                        await TraceRepository.update_progress(
                            session=session,
                            trace_id=trace_id,
                            current_hop=hop,
                            progress_percent=pct,
                            tenant_id=job.tenant_id,
                        )
                event_data = {
                    "event": "HOP_PROGRESS",
                    "trace_id": trace_id,
                    "current_hop": hop,
                    "max_hops": max_hops,
                    "progress_percent": round(pct, 2),
                    "node_count": nodes,
                    "edge_count": edges,
                    "pruned_count": pruned,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                await self.queue.publish_event(trace_id, event_data)

            async def check_cancelled() -> bool:
                return await self.queue.is_cancelled(trace_id)

            # 7. Execute Multi-Hop Traversal
            graph = await engine.trace(
                source_address=job.input_value,
                progress_callback=on_progress,
                cancel_checker=check_cancelled,
            )

            # 8. Check if cancelled during traversal
            if await self.queue.is_cancelled(trace_id):
                if self.db_session_factory:
                    async with self.db_session_factory() as session:
                        await TraceRepository.update_cancelled(
                            session, trace_id, "Cancelled during execution by investigator", tenant_id=job.tenant_id
                        )
                await self.queue.publish_event(trace_id, {
                    "event": "JOB_CANCELLED",
                    "trace_id": trace_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                return

            # 9. Determine terminal status and persist
            is_partial = graph.meta.get("is_partial", False)
            final_status = "PARTIAL" if is_partial else "COMPLETED"
            duration_ms = int(graph.meta.get("duration_ms", 0))
            boundary_code = graph.meta.get("boundary_reached")
            summary = graph.meta.get("investigator_explanation")

            if self.db_session_factory:
                async with self.db_session_factory() as session:
                    await TraceRepository.update_completed(
                        session=session,
                        trace_id=trace_id,
                        graph=graph,
                        duration_ms=duration_ms,
                        boundary_code=boundary_code,
                        investigator_summary=summary,
                        status=final_status,
                        tenant_id=job.tenant_id,
                    )

                    # Generate forensic evidence items
                    try:
                        ev_items = EvidenceGenerator.generate_trace_evidence(
                            case_id=job.case_id,
                            trace_id=trace_id,
                            graph=graph,
                            config_snapshot={"max_hops": job.max_hops, "min_relevant_usd": str(job.min_relevant_usd)},
                        )
                        await EvidenceRepository.save_evidence_items(
                            session,
                            ev_items,
                            tenant_id=job.tenant_id,
                            district_id=job.district_id,
                            police_station_id=job.police_station_id,
                        )
                    except Exception as ev_err:
                        logger.warning(f"Evidence generation warning for trace {trace_id}: {ev_err}")

                    # Audit Event
                    try:
                        now_utc = datetime.now(timezone.utc)
                        audit_ev = AuditEvent(
                            id=str(uuid.uuid4()),
                            case_id=job.case_id,
                            trace_id=trace_id,
                            actor_id=job.officer_id,
                            event_type=AuditEventType.TRACE_STARTED,
                            action_summary=f"Trace completed with status {final_status} (nodes: {len(graph.nodes)}, edges: {len(graph.edges)}).",
                            metadata={"status": final_status, "nodes": len(graph.nodes), "edges": len(graph.edges)},
                            content_hash=compute_content_hash({"trace_id": trace_id, "status": final_status, "timestamp": now_utc.isoformat()}),
                            created_at=now_utc,
                        )
                        await AuditRepository.record_event(
                            session,
                            audit_ev,
                            tenant_id=job.tenant_id,
                            district_id=job.district_id,
                            police_station_id=job.police_station_id,
                        )
                    except Exception as aud_err:
                        logger.warning(f"Audit recording warning for trace {trace_id}: {aud_err}")

            # 10. Broadcast terminal event
            await self.queue.publish_event(trace_id, {
                "event": "JOB_COMPLETED",
                "trace_id": trace_id,
                "status": final_status,
                "node_count": len(graph.nodes),
                "edge_count": len(graph.edges),
                "graph": graph.model_dump(mode="json"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            logger.info(f"TraceWorker [{self.worker_id}] finished trace {trace_id} ({final_status})")

        except Exception as ex:
            logger.error(f"TraceWorker [{self.worker_id}] failed trace {trace_id}: {ex}", exc_info=True)
            if self.db_session_factory:
                async with self.db_session_factory() as session:
                    await TraceRepository.update_failed(
                        session=session,
                        trace_id=trace_id,
                        error_message=str(ex),
                        boundary_code="EXECUTION_ERROR",
                        tenant_id=job.tenant_id,
                    )
            await self.queue.publish_event(trace_id, {
                "event": "JOB_FAILED",
                "trace_id": trace_id,
                "error": str(ex),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        finally:
            await hb.stop()


class WorkerFleet:
    """Manages a pool of concurrent TraceWorker instances."""

    def __init__(
        self,
        concurrency: int = 2,
        queue: Optional[TraceQueue] = None,
        db_session_factory: Any = None,
        redis_client: Optional[Any] = None,
    ):
        self.concurrency = max(1, concurrency)
        self.queue = queue or get_trace_queue(redis_client)
        self.db_session_factory = db_session_factory
        self.redis = redis_client
        self.workers: List[TraceWorker] = []
        self.tasks: List[asyncio.Task] = []

    async def start(self):
        """Start all workers in fleet."""
        for i in range(self.concurrency):
            worker = TraceWorker(
                worker_id=f"worker-fleet-{i + 1}",
                queue=self.queue,
                db_session_factory=self.db_session_factory,
                redis_client=self.redis,
            )
            self.workers.append(worker)
            task = asyncio.create_task(worker.run_loop())
            self.tasks.append(task)
        logger.info(f"WorkerFleet started {self.concurrency} workers.")

    async def stop(self):
        """Gracefully stop all workers."""
        for worker in self.workers:
            worker.running = False
        for task in self.tasks:
            task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
        self.workers.clear()
        logger.info("WorkerFleet stopped.")


class ReportWorker:
    """
    Asynchronous worker processing background report compilation jobs (Section 63 BSA,
    Section 94 BNSS, Evidence Dossier), persisting PDFs to encrypted storage vault.
    """

    def __init__(
        self,
        worker_id: Optional[str] = None,
        queue: Optional[ReportQueue] = None,
        db_session_factory: Any = None,
        redis_client: Optional[Any] = None,
    ):
        self.worker_id = worker_id or f"report-worker-{uuid.uuid4().hex[:8]}"
        self.queue = queue or get_report_queue(redis_client)
        self.db_session_factory = db_session_factory
        self.redis = redis_client
        self.running = False

    async def run_loop(self):
        self.running = True
        logger.info(f"ReportWorker [{self.worker_id}] started loop.")
        while self.running:
            try:
                job = await self.queue.pop(timeout_seconds=1.0)
                if job:
                    await self.process_job(job)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"ReportWorker [{self.worker_id}] loop error: {e}", exc_info=True)
                await asyncio.sleep(0.5)

    async def process_job(self, job: ReportJobPayload):
        logger.info(f"ReportWorker [{self.worker_id}] processing report {job.report_id} ({job.report_type})")
        if not self.db_session_factory:
            logger.warning("No db_session_factory configured for ReportWorker; cannot process job.")
            return

        storage_service = get_storage_service()

        async with self.db_session_factory() as session:
            report = await ReportRepository.get_by_id(session, job.report_id, tenant_id=job.tenant_id)
            if not report:
                logger.error(f"Report {job.report_id} not found in DB.")
                return

            report.status = "PROCESSING"
            await session.commit()
            await self.queue.publish_event(job.job_id, {"status": "PROCESSING", "report_id": job.report_id})

            try:
                case = await CaseRepository.get_by_id(session, job.case_id, tenant_id=job.tenant_id)
                trace = None
                if job.trace_id:
                    trace = await TraceRepository.get_by_id(session, job.trace_id, tenant_id=job.tenant_id)

                pdf_bytes: bytes = b""
                report_hash: str = ""
                meta: dict = {}

                if job.report_type == "EVIDENCE_DOSSIER":
                    graph = InvestigationGraph(**(trace.graph_data if trace and trace.graph_data else {"nodes": [], "edges": []}))
                    engine = AttributionEngine()
                    attribution_report = engine.evaluate_trace(trace_id=trace.id if trace else "", graph=graph)
                    evidence_items = await EvidenceRepository.get_by_trace_id(session, trace.id if trace else "", tenant_id=job.tenant_id)
                    pdf_bytes, report_hash, meta = EvidenceDossierGenerator.generate_pdf(
                        case=case,
                        trace=trace,
                        graph=graph,
                        attribution_report=attribution_report,
                        evidence_items=evidence_items,
                        investigator_name=job.parameters.get("investigator_name", "IO-Vikram-742"),
                        investigator_rank=job.parameters.get("investigator_rank", "Inspector of Police"),
                        police_station=job.parameters.get("police_station", "Cyber Crime Police Station"),
                        include_graph_snapshot=job.parameters.get("include_graph_snapshot", True),
                        notes=job.parameters.get("notes"),
                    )
                elif job.report_type == "SECTION_94_BNSS":
                    engine = AttributionEngine()
                    graph = InvestigationGraph(**(trace.graph_data if trace and trace.graph_data else {"nodes": [], "edges": []}))
                    attribution_report = engine.evaluate_trace(trace_id=trace.id if trace else "", graph=graph)
                    pdf_bytes, report_hash, meta = BNSS94DraftGenerator.generate_pdf(
                        case=case,
                        trace=trace,
                        attribution_report=attribution_report,
                        target_vasp_override=job.parameters.get("target_vasp"),
                        candidate_address_override=job.parameters.get("candidate_address"),
                        investigator_name=job.parameters.get("investigator_name", "IO-Vikram-742"),
                        investigator_rank=job.parameters.get("investigator_rank", "Inspector of Police"),
                        police_station=job.parameters.get("police_station", "Cyber Crime Police Station"),
                        court_jurisdiction=job.parameters.get("court_jurisdiction", "Chief Judicial Magistrate / Cyber Special Court"),
                        compliance_email=job.parameters.get("compliance_email"),
                        urgency_hours=job.parameters.get("urgency_hours", 48),
                        notes=job.parameters.get("notes"),
                    )
                elif job.report_type == "SECTION_63_BSA":
                    evidence_items = await EvidenceRepository.get_by_trace_id(session, trace.id if trace else "", tenant_id=job.tenant_id)
                    pdf_bytes, report_hash, meta = Section63BSAGenerator.generate_pdf(
                        case=case,
                        trace=trace,
                        evidence_items=evidence_items,
                        investigator_name=job.parameters.get("investigator_name", "IO-Vikram-742"),
                        investigator_rank=job.parameters.get("investigator_rank", "Inspector of Police"),
                        police_station=job.parameters.get("police_station", "Cyber Crime Police Station"),
                        technical_examiner=job.parameters.get("technical_examiner"),
                        notes=job.parameters.get("notes"),
                    )
                else:
                    raise ValueError(f"Unsupported report type: {job.report_type}")

                # Store PDF in encrypted storage vault
                storage_key = f"reports/{job.tenant_id}/{job.case_id}/{job.report_type}_{job.report_id[:8]}.pdf"
                stored_doc = await storage_service.put_object(
                    key=storage_key,
                    data=pdf_bytes,
                    content_type="application/pdf",
                    encrypt=True,
                    metadata={"case_id": job.case_id, "report_id": job.report_id},
                )

                # Update ReportModel in DB
                report.status = "COMPLETED"
                report.file_path = stored_doc.key
                report.storage_path = stored_doc.key
                report.s3_key = stored_doc.key
                report.file_hash = report_hash
                report.content_hash = report_hash
                report.file_size_bytes = stored_doc.size_bytes
                report.storage_backend = stored_doc.storage_backend
                report.encryption_metadata = stored_doc.encryption_metadata
                report.completed_at = datetime.now(timezone.utc)
                if meta:
                    current_meta = report.metadata_json or {}
                    current_meta.update(meta)
                    report.metadata_json = current_meta

                # Audit Log
                audit_event = AuditEvent(
                    id=uuid.uuid4().hex,
                    case_id=job.case_id,
                    trace_id=job.trace_id,
                    actor_id=job.officer_id,
                    event_type=AuditEventType.REPORT_GENERATED,
                    action_summary=f"Compiled statutory {job.report_type} report asynchronously: {report.title}",
                    metadata={"report_id": report.id, "report_type": job.report_type, "content_hash": report_hash},
                    content_hash=report_hash,
                )
                await AuditRepository.record_event(
                    session,
                    audit_event,
                    tenant_id=job.tenant_id,
                    district_id=job.district_id,
                    police_station_id=job.police_station_id,
                )

                await session.commit()
                await self.queue.publish_event(job.job_id, {
                    "status": "COMPLETED",
                    "report_id": job.report_id,
                    "content_hash": report_hash,
                    "file_size_bytes": stored_doc.size_bytes,
                })
                logger.info(f"ReportWorker successfully completed report {job.report_id}")

            except Exception as e:
                logger.error(f"ReportWorker failed processing report {job.report_id}: {e}", exc_info=True)
                report.status = "FAILED"
                report.error_message = str(e)
                await session.commit()
                await self.queue.publish_event(job.job_id, {
                    "status": "FAILED",
                    "report_id": job.report_id,
                    "error": str(e),
                })

