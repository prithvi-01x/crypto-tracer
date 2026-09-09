import type {
  EvidenceChain,
  EvidenceItem,
  AuditEvent,
  AttributionReviewRequest,
  AttributionReviewResponse,
  EvidenceClassification,
} from '../types/evidence';

const API_BASE = import.meta.env.VITE_API_URL || '/api/v1';

export async function getTraceEvidence(
  traceId: string,
  classification?: EvidenceClassification
): Promise<EvidenceChain> {
  const query = classification ? `?classification=${encodeURIComponent(classification)}` : '';
  const response = await fetch(`${API_BASE}/traces/${traceId}/evidence${query}`);
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to fetch trace evidence: ${response.statusText}`);
  }
  return response.json();
}

export async function getCaseEvidence(
  caseId: string,
  classification?: EvidenceClassification
): Promise<EvidenceChain> {
  const query = classification ? `?classification=${encodeURIComponent(classification)}` : '';
  const response = await fetch(`${API_BASE}/cases/${caseId}/evidence${query}`);
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to fetch case evidence: ${response.statusText}`);
  }
  return response.json();
}

export async function getEvidenceById(evidenceId: string): Promise<EvidenceItem> {
  const response = await fetch(`${API_BASE}/evidence/${evidenceId}`);
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to fetch evidence item: ${response.statusText}`);
  }
  return response.json();
}

export async function getCaseAuditEvents(caseId: string): Promise<AuditEvent[]> {
  const response = await fetch(`${API_BASE}/cases/${caseId}/audit`);
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to fetch audit log: ${response.statusText}`);
  }
  return response.json();
}

export async function recordAuditEvent(
  caseId: string,
  data: {
    trace_id?: string;
    event_type: string;
    actor_id?: string;
    action_summary: string;
    metadata?: Record<string, any>;
  }
): Promise<AuditEvent> {
  const response = await fetch(`${API_BASE}/cases/${caseId}/audit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to record audit event: ${response.statusText}`);
  }
  return response.json();
}

export async function reviewAttributionHypothesis(
  caseId: string,
  candidateAddress: string,
  req: AttributionReviewRequest
): Promise<AttributionReviewResponse> {
  const response = await fetch(`${API_BASE}/cases/${caseId}/attributions/${candidateAddress}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to record attribution review: ${response.statusText}`);
  }
  return response.json();
}
