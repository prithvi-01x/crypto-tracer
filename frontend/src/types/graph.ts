export interface GraphNode {
  id: string;
  address: string;
  chain: string;
  node_type: 'suspect' | 'intermediate' | 'endpoint' | string;
  hop: number;
  total_received: number | string;
  total_sent: number | string;
  transaction_count: number;
  first_seen?: string | null;
  last_seen?: string | null;
}

export interface GraphEdge {
  id: string;
  tx_hash: string;
  from_address: string;
  to_address: string;
  amount: number | string;
  amount_raw: number;
  asset: string;
  timestamp: string;
  block_number?: number | null;
  hop: number;
  source: string;
  relevance_score?: number | string;
  pruned?: boolean;
}

export interface PrunedRecord {
  tx_hash: string;
  from_address: string;
  to_address: string;
  amount: number | string;
  asset: string;
  hop: number;
  reason: string;
  threshold: number | string;
  timestamp: string;
  source: string;
}

export interface GraphMeta {
  source_wallet: string;
  max_hops: number;
  max_hops_configured: number;
  hops_reached: number;
  total_nodes: number;
  total_edges: number;
  visited_count: number;
  raw_transfers_fetched_count: number;
  traversal_relevant_transfers_count: number;
  edges_included_count: number;
  pruned_transfers_count: number;
  pruned_nodes: number;
  min_relevant_usd: number;
  max_branches_per_node: number;
  duration_ms: number;
  bounds_hit: boolean;
  boundary_reached?: string | null;
  is_partial?: boolean;
  investigator_explanation?: string | null;
}

export interface InvestigationGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  pruned_records: PrunedRecord[];
  meta: GraphMeta;
  boundary?: Record<string, any> | null;
}

export interface TraceCreateInput {
  case_id: string;
  chain?: string;
  input_type?: string;
  input: string;
  asset?: string;
  max_hops?: number;
  min_relevant_usd?: number;
}

export interface TraceStatus {
  trace_id: string;
  case_id: string;
  status: 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'PARTIAL' | 'FAILED' | string;
  chain: string;
  input_value: string;
  asset: string;
  max_hops: number;
  duration_ms?: number | null;
  node_count: number;
  edge_count: number;
  pruned_count: number;
  nodes?: number | null;
  edges?: number | null;
  pruned_nodes?: number | null;
  raw_transfers_count?: number;
  relevant_transfers_count?: number;
  boundary_code?: string | null;
  investigator_summary?: string | null;
  is_partial?: boolean;
  started_at?: string | null;
  completed_at?: string | null;
}
