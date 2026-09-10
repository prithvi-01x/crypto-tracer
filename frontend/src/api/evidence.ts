import type {
  EvidenceChain,
  AuditEvent,
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

export async function getCaseAuditEvents(caseId: string): Promise<AuditEvent[]> {
  const response = await fetch(`${API_BASE}/cases/${caseId}/audit`);
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to fetch audit log: ${response.statusText}`);
  }
  return response.json();
}
