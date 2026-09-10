export type FindingSeverity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';

export type FindingType =
  | 'VASP_CONSOLIDATION'
  | 'RAPID_SWEEP'
  | 'FAN_IN_CONCENTRATION'
  | 'MULTI_HOP_LAYERING'
  | 'MIXER_ENCOUNTERED'
  | 'BRIDGE_ENCOUNTERED'
  | 'LOW_CONFIDENCE_ATTRIBUTION'
  | 'OPERATIONAL_BOUNDARY'
  | 'TRACE_COMPLETED';

export type FindingStatus = 'OPEN' | 'REVIEWED' | 'DISMISSED';

export interface EvidenceReference {
  id: string;
  title: string;
  classification: string;
  content_hash: string;
  evidence_type: string;
}

export interface ForensicFindingItem {
  finding_id: string;
  case_id: string;
  trace_id: string;
  severity: FindingSeverity;
  finding_type: FindingType;
  title: string;
  description: string;
  timestamp: string;
  source_signal: string;
  confidence?: number | null;
  related_address?: string | null;
  related_tx_hash?: string | null;
  related_vasp?: string | null;
  evidence_refs: EvidenceReference[];
  status: FindingStatus;
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  review_notes?: string | null;
  graph_node_id?: string | null;
  graph_edge_id?: string | null;
}

export interface FindingListResponse {
  case_id: string;
  trace_id?: string | null;
  total: number;
  open_count: number;
  reviewed_count: number;
  dismissed_count: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  info_count: number;
  findings: ForensicFindingItem[];
}

export interface FindingReviewPayload {
  status: FindingStatus;
  notes?: string;
  reviewed_by?: string;
}
