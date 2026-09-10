import React from 'react';
import { 
  GitFork, 
  Layers, 
  ShieldAlert, 
  FilterX, 
  Timer, 
  CheckCircle2, 
  Sparkles,
  ExternalLink
} from 'lucide-react';
import type { GraphMeta } from '../../types/graph';

interface TraceStatsBarProps {
  meta: GraphMeta | null;
  onOpenPruning: () => void;
  prunedCount: number;
}

export const TraceStatsBar: React.FC<TraceStatsBarProps> = ({ meta, onOpenPruning, prunedCount }) => {
  if (!meta) return null;

  return (
    <div className="bg-surface-default dark:bg-surface-100 border border-surface-200 dark:border-surface-300 rounded-lg px-3 py-1.5 shadow-xs transition-colors shrink-0">
      <div className="flex flex-wrap items-center justify-between gap-2.5">
        {/* Metric Cards Group */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {/* Engine Mode */}
          <div className={`flex items-center gap-2 px-2.5 py-1 rounded-md border ${
            meta.execution_mode === 'LIVE'
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-700 dark:text-emerald-400'
              : 'bg-amber-500/10 border-amber-500/30 text-amber-800 dark:text-amber-300'
          }`}>
            <div className={`h-2 w-2 rounded-full shrink-0 ${meta.execution_mode === 'LIVE' ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'}`} />
            <div>
              <span className="text-[9px] uppercase font-bold tracking-wider opacity-75 block leading-none mb-0.5">Engine Mode</span>
              <span className="font-extrabold font-mono text-xs whitespace-nowrap leading-none">
                {meta.execution_mode === 'LIVE' ? 'LIVE TRON RPC' : 'DEMO REPLAY FIXTURE'}
              </span>
            </div>
          </div>

          {/* Hops */}
          <div className="flex items-center gap-2 px-2.5 py-1 rounded-md bg-surface-50 dark:bg-surface-200/60 border border-surface-200 dark:border-surface-300">
            <Layers className="h-3.5 w-3.5 text-brand-blue dark:text-blue-400 shrink-0" />
            <div>
              <span className="text-[9px] uppercase font-bold tracking-wider text-surface-500 block leading-none mb-0.5">Traversal Depth</span>
              <span className="font-extrabold font-mono text-xs text-brand-blue dark:text-blue-400 leading-none">
                Hop {meta.hops_reached} / {meta.max_hops_configured}
              </span>
            </div>
          </div>

          {/* Raw Transfers */}
          <div className="flex items-center gap-2 px-2.5 py-1 rounded-md bg-surface-50 dark:bg-surface-200/60 border border-surface-200 dark:border-surface-300">
            <GitFork className="h-3.5 w-3.5 text-surface-400 shrink-0" />
            <div>
              <span className="text-[9px] uppercase font-bold tracking-wider text-surface-500 block leading-none mb-0.5">Raw Fetched</span>
              <span className="font-bold font-mono text-xs text-surface-800 dark:text-surface-100 leading-none">{meta.raw_transfers_fetched_count} txs</span>
            </div>
          </div>

          {/* Traversal Relevant */}
          <div className="flex items-center gap-2 px-2.5 py-1 rounded-md bg-surface-50 dark:bg-surface-200/60 border border-surface-200 dark:border-surface-300">
            <Sparkles className="h-3.5 w-3.5 text-amber-500 shrink-0" />
            <div>
              <span className="text-[9px] uppercase font-bold tracking-wider text-surface-500 block leading-none mb-0.5">Relevant Txs</span>
              <span className="font-extrabold font-mono text-xs text-amber-600 dark:text-amber-400 leading-none">{meta.traversal_relevant_transfers_count}</span>
            </div>
          </div>

          {/* Graph Edges & Nodes */}
          <div className="flex items-center gap-2 px-2.5 py-1 rounded-md bg-surface-50 dark:bg-surface-200/60 border border-surface-200 dark:border-surface-300">
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
            <div>
              <span className="text-[9px] uppercase font-bold tracking-wider text-surface-500 block leading-none mb-0.5">Active Topology</span>
              <span className="font-extrabold font-mono text-xs text-emerald-600 dark:text-emerald-400 leading-none">
                {meta.total_nodes} nodes • {meta.total_edges} edges
              </span>
            </div>
          </div>

          {/* Noise Pruned Count (Clickable) */}
          <button
            onClick={onOpenPruning}
            className="flex items-center gap-2 px-2.5 py-1 rounded-md bg-purple-500/10 border border-purple-500/30 hover:bg-purple-500/20 text-left transition group cursor-pointer"
            title="Click to view forensic pruning audit"
          >
            <FilterX className="h-3.5 w-3.5 text-purple-600 dark:text-purple-400 shrink-0 group-hover:scale-110 transition" />
            <div>
              <span className="text-[9px] uppercase font-bold tracking-wider text-purple-700 dark:text-purple-300 flex items-center gap-1 leading-none mb-0.5">
                Noise Pruned
                <ExternalLink className="h-2.5 w-2.5 opacity-70" />
              </span>
              <span className="font-extrabold font-mono text-xs text-purple-800 dark:text-purple-200 leading-none">
                {prunedCount} transfers (&lt; ${meta.min_relevant_usd.toFixed(2)})
              </span>
            </div>
          </button>
        </div>

        {/* Execution Duration & Bounds Notice */}
        <div className="flex items-center gap-2.5 text-xs text-surface-500">
          {meta.bounds_hit && (
            <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-500/30 font-bold text-[11px]">
              <ShieldAlert className="h-3 w-3 text-amber-600" />
              Bounds Hit
            </span>
          )}
          <div className="flex items-center gap-1 font-mono text-xs">
            <Timer className="h-3.5 w-3.5 text-surface-400" />
            <span>{meta.duration_ms} ms</span>
          </div>
        </div>
      </div>
    </div>
  );
};
