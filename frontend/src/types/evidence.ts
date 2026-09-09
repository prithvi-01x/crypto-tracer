export type EvidenceClassification = 'OBSERVED' | 'DERIVED' | 'INFERRED' | 'HUMAN_ACTION';

export type AuditEventType =
  | 'CASE_OPENED'
  | 'TRACE_STARTED'
  | 'TRANSACTION_VIEWED'
  | 'ATTRIBUTION_VIEWED'
  | 'EVIDENCE_REVIEWED'
  | 'ATTRIBUTION_ACCEPTED'
  | 'ATTRIBUTION_REJECTED'
  | 'REPORT_GENERATED';

export interface EvidenceItem {
  id: string;
  case_id: string;
  trace_id?: string | null;
  evidence_type: string;
  classification: EvidenceClassification;
  title: string;
  description?: string | null;
  source: string;
  source_reference?: string | null;
  payload: Record<string, any>;
  parent_evidence_ids: string[];
  content_hash: string;
  engine_version: string;
  configuration_snapshot?: Record<string, any> | null;
  collected_at: string;
  analysis_timestamp: string;
  created_at: string;
}

export interface EvidenceChain {
  trace_id?: string | null;
  case_id: string;
  total_evidence_count: number;
  observed_count: number;
  derived_count: number;
  inferred_count: number;
  human_action_count: number;
  items: EvidenceItem[];
}

export interface AuditEvent {
  id: string;
  case_id: string;
  trace_id?: string | null;
  actor_id: string;
  event_type: AuditEventType | string;
  action_summary: string;
  metadata: Record<string, any>;
  content_hash: string;
  created_at: string;
}

export interface AttributionReviewRequest {
  actor_id?: string;
  decision: 'ACCEPT' | 'REJECT';
  notes?: string;
  trace_id?: string;
}

export interface AttributionReviewResponse {
  status: string;
  candidate_address: string;
  decision: string;
  evidence_id: string;
  audit_event_id: string;
  reviewed_at: string;
}
