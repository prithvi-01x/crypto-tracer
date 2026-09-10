const API_BASE = import.meta.env.VITE_API_URL || '/api/v1';

export interface HealthResponse {
  status: 'HEALTHY' | 'DEGRADED' | string;
  app: string;
  environment: string;
  version: string;
  timestamp: string;
  services: {
    database: { status: string; latency_ms?: number };
    redis: { status: string; latency_ms?: number };
  };
}

export async function getSystemHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) {
    throw new Error(`Health check failed: ${res.statusText}`);
  }
  return res.json();
}
