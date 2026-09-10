import type {
  ReportItem,
  EvidenceDossierCreateInput,
  BNSS94DraftCreateInput,
} from '../types/reports';

const API_BASE = import.meta.env.VITE_API_URL || '/api/v1';

export async function generateEvidenceDossier(
  caseId: string,
  input: EvidenceDossierCreateInput
): Promise<ReportItem> {
  const response = await fetch(`${API_BASE}/cases/${caseId}/reports/dossier`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to generate Evidence Dossier: ${response.statusText}`);
  }
  return response.json();
}

export async function generateBNSS94Draft(
  caseId: string,
  input: BNSS94DraftCreateInput
): Promise<ReportItem> {
  const response = await fetch(`${API_BASE}/cases/${caseId}/reports/bnss94`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to generate Section 94 BNSS draft: ${response.statusText}`);
  }
  return response.json();
}

export async function getCaseReports(
  caseId: string,
  reportType?: string
): Promise<ReportItem[]> {
  const query = reportType ? `?report_type=${encodeURIComponent(reportType)}` : '';
  const response = await fetch(`${API_BASE}/cases/${caseId}/reports${query}`);
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to fetch case reports: ${response.statusText}`);
  }
  return response.json();
}

export function getReportDownloadUrl(reportId: string): string {
  return `${API_BASE}/reports/${reportId}/download`;
}
