export interface CaseItem {
  id: string;
  fir_number: string;
  victim_reference: string | null;
  loss_amount_inr: number | null;
  ack_number: string | null;
  suspect_wallet: string | null;
  chain: string;
  asset: string;
  notes: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  trace_count: number;
}

export interface CaseCreateInput {
  fir_number: string;
  victim_reference?: string;
  loss_amount_inr?: number;
  ack_number?: string;
  suspect_wallet?: string;
  chain?: string;
  asset?: string;
  notes?: string;
}

export interface CaseListResponse {
  total: number;
  cases: CaseItem[];
}
