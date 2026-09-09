import type { CaseItem, CaseCreateInput, CaseListResponse } from '../types/case';

const API_BASE = import.meta.env.VITE_API_URL || '/api/v1';

export async function getCases(skip = 0, limit = 50): Promise<CaseListResponse> {
  const res = await fetch(`${API_BASE}/cases?skip=${skip}&limit=${limit}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch cases: ${res.statusText}`);
  }
  return res.json();
}

export async function getCaseById(caseId: string): Promise<CaseItem> {
  const res = await fetch(`${API_BASE}/cases/${caseId}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch case: ${res.statusText}`);
  }
  return res.json();
}

export async function createCase(data: CaseCreateInput): Promise<CaseItem> {
  const res = await fetch(`${API_BASE}/cases`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const errorJson = await res.json().catch(() => null);
    throw new Error(errorJson?.detail || `Failed to create case: ${res.statusText}`);
  }
  return res.json();
}
