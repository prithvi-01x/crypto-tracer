import type { FindingListResponse, ForensicFindingItem, FindingReviewPayload } from '../types/findings';

const API_BASE = import.meta.env.VITE_API_URL || '/api/v1';

export async function getCaseFindings(caseId: string): Promise<FindingListResponse> {
  const res = await fetch(`${API_BASE}/cases/${caseId}/findings`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to fetch case findings: ${res.statusText}`);
  }
  return res.json();
}

export async function getTraceFindings(traceId: string): Promise<FindingListResponse> {
  const res = await fetch(`${API_BASE}/traces/${traceId}/findings`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to fetch trace findings: ${res.statusText}`);
  }
  return res.json();
}

export async function reviewFinding(
  caseId: string,
  findingId: string,
  payload: FindingReviewPayload
): Promise<ForensicFindingItem> {
  const res = await fetch(`${API_BASE}/cases/${caseId}/findings/${findingId}/review`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to update finding status: ${res.statusText}`);
  }
  return res.json();
}
