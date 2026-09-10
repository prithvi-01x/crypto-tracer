import type { InvestigationGraph, TraceCreateInput, TraceStatus } from '../types/graph';
import type { AttributionResponse } from '../types/attribution';

const API_BASE = import.meta.env.VITE_API_URL || '/api/v1';

export async function startTrace(input: TraceCreateInput): Promise<TraceStatus> {
  const response = await fetch(`${API_BASE}/traces`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      case_id: input.case_id,
      chain: input.chain || 'TRON',
      input_type: input.input_type || 'address',
      input: input.input.trim(),
      asset: input.asset || 'TRC20:USDT',
      max_hops: input.max_hops ?? 4,
      min_relevant_usd: input.min_relevant_usd ?? 1.0,
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to initiate trace: ${response.statusText}`);
  }

  return response.json();
}

export async function getTraceStatus(traceId: string): Promise<TraceStatus> {
  const response = await fetch(`${API_BASE}/traces/${traceId}`);
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to fetch trace status: ${response.statusText}`);
  }
  return response.json();
}

export async function getTraceGraph(traceId: string): Promise<InvestigationGraph> {
  const response = await fetch(`${API_BASE}/traces/${traceId}/graph`);
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to load investigation graph: ${response.statusText}`);
  }
  return response.json();
}

export async function getTracesByCase(caseId: string): Promise<TraceStatus[]> {
  const response = await fetch(`${API_BASE}/cases/${caseId}/traces`);
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to fetch case traces: ${response.statusText}`);
  }
  return response.json();
}

export async function getTraceAttribution(traceId: string): Promise<AttributionResponse> {
  const response = await fetch(`${API_BASE}/traces/${traceId}/attribution`);
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to fetch trace attribution: ${response.statusText}`);
  }
  return response.json();
}

