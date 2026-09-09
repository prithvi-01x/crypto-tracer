export type ReportType = 'EVIDENCE_DOSSIER' | 'SECTION_94_BNSS';

export interface ReportItem {
  id: string;
  case_id: string;
  trace_id?: string | null;
  report_type: ReportType;
  title: string;
  file_name: string;
  file_size_bytes: number;
  content_hash: string;
  generated_by: string;
  metadata: Record<string, any>;
  created_at: string;
  download_url: string;
}

export interface EvidenceDossierCreateInput {
  trace_id: string;
  investigator_name?: string;
  investigator_rank?: string;
  police_station?: string;
  include_graph_snapshot?: boolean;
  notes?: string;
}

export interface BNSS94DraftCreateInput {
  trace_id: string;
  target_vasp?: string;
  candidate_address?: string;
  investigator_name?: string;
  investigator_rank?: string;
  police_station?: string;
  court_jurisdiction?: string;
  compliance_email?: string;
  urgency_hours?: number;
  notes?: string;
}
