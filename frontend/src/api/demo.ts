const API_BASE = import.meta.env.VITE_API_URL || '/api/v1';

export interface DemoSeedResponse {
  status: string;
  message: string;
  case_id: string;
  fir_number: string;
  trace_id: string;
  suspect_wallet: string;
  execution_mode: string;
  attribution: {
    attributed_vasp: string;
    confidence: number;
    confidence_band: string;
    candidate_address?: string | null;
    hypothesis_label?: string | null;
  };
  graph_metrics: {
    nodes: number;
    edges: number;
    pruned_transfers: number;
    hops: number;
    duration_ms: number;
  };
  evidence_items_count: number;
}

export interface DemoStatusResponse {
  loaded: boolean;
  case_id?: string | null;
  fir_number?: string | null;
  suspect_wallet?: string | null;
  trace_id?: string | null;
  trace_status?: string | null;
  execution_mode?: string | null;
  message?: string;
  scenario?: CanonicalScenarioResponse;
}

export interface CanonicalScenarioResponse {
  scenario_title: string;
  narrative: string;
  fir_number: string;
  victim: string;
  reported_loss_inr: number;
  reported_loss_usdt: number;
  chain: string;
  asset: string;
  hops: Array<{
    hop: number;
    role: string;
    address: string;
    description: string;
  }>;
}

export async function seedDemoCase(): Promise<DemoSeedResponse> {
  const res = await fetch(`${API_BASE}/demo/seed`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(err?.detail?.message || err?.detail || 'Failed to seed demo case');
  }
  return res.json();
}

export async function getDemoStatus(): Promise<DemoStatusResponse> {
  const res = await fetch(`${API_BASE}/demo/status`);
  if (!res.ok) {
    throw new Error('Failed to retrieve demo status');
  }
  return res.json();
}

export async function getCanonicalScenario(): Promise<CanonicalScenarioResponse> {
  const status = await getDemoStatus();
  if (!status.scenario) {
    throw new Error('Canonical scenario metadata not available');
  }
  return status.scenario;
}
