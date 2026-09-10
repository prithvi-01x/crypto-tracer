export interface AttributionFactors {
  direct_tag: number;
  downstream_vasp_match: number;
  sweep: number;
  fan_in: number;
  temporal: number;
}

export interface AttributionExplanations {
  direct_tag: string;
  downstream_vasp_match: string;
  sweep: string;
  fan_in: string;
  temporal: string;
}

export interface AttributionCandidate {
  candidate_address: string;
  vasp: string;
  vasp_name: string;
  vasp_id: string;
  hypothesis_label: string;
  confidence: number;
  confidence_percentage: number;
  confidence_band: 'LOW' | 'MODERATE' | 'HIGH' | 'VERY HIGH' | string;
  verification_status: 'VERIFIED' | 'UNVERIFIED' | 'HEURISTIC' | string;
  entity_category?: string;
  is_low_confidence?: boolean;
  factors: AttributionFactors;
  explanations: AttributionExplanations;
  evidence_bullet_points: string[];
}

export interface AttributionResponse {
  trace_id: string;
  engine_version: string;
  disclaimer: string;
  evaluated_at: string;
  candidates: AttributionCandidate[];
  best_candidate?: AttributionCandidate | null;
  meta?: Record<string, unknown>;
}
