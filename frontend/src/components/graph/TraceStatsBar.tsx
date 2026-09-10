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
    <div className="bg-surface-default dark:bg-surface-100 border border-surface-200 dark:border-surface-300 rounded-lg p-2.5 shadow-sm transition-colors">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* Metric Cards Group */}
        <div className="flex flex-wrap items-center gap-2 sm:gap-3 text-xs">
          {/* Hops */}
          <div className="flex items-center gap-2 px-2.5 py-1.5 rounded bg-surface-50 dark:bg-surface-200/60 border border-surface-200 dark:border-surface-300">
            <Layers className="h-3.5 w-3.5 text-brand-blue dark:text-blue-400 shrink-0" />
            <div>
              <span className="text-[10px] uppercase font-semibold text-surface-500 block leading-tight">Traversal Depth</span>
              <span className="font-bold font-mono text-surface-800 dark:text-surface-100">
                Hop {meta.hops_reached} / {meta.max_hops_configured}
              </span>
            </div>
          </div>

          {/* Raw Transfers */}
          <div className="flex items-center gap-2 px-2.5 py-1.5 rounded bg-surface-50 dark:bg-surface-200/60 border border-surface-200 dark:border-surface-300">
            <GitFork className="h-3.5 w-3.5 text-surface-400 shrink-0" />
            <div>
              <span className="text-[10px] uppercase font-semibold text-surface-500 block leading-tight">Raw Fetched</span>
              <span className="font-bold font-mono text-surface-800 dark:text-surface-100">{meta.raw_transfers_fetched_count} txs</span>
            </div>
          </div>

          {/* Traversal Relevant */}
          <div className="flex items-center gap-2 px-2.5 py-1.5 rounded bg-surface-50 dark:bg-surface-200/60 border border-surface-200 dark:border-surface-300">
            <Sparkles className="h-3.5 w-3.5 text-amber-500 shrink-0" />
            <div>
              <span className="text-[10px] uppercase font-semibold text-surface-500 block leading-tight">Relevant Txs</span>
              <span className="font-bold font-mono text-amber-600 dark:text-amber-400">{meta.traversal_relevant_transfers_count}</span>
            </div>
          </div>

          {/* Graph Edges & Nodes */}
          <div className="flex items-center gap-2 px-2.5 py-1.5 rounded bg-surface-50 dark:bg-surface-200/60 border border-surface-200 dark:border-surface-300">
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
            <div>
              <span className="text-[10px] uppercase font-semibold text-surface-500 block leading-tight">Active Topology</span>
              <span className="font-bold font-mono text-emerald-600 dark:text-emerald-400">
                {meta.total_nodes} nodes • {meta.total_edges} edges
              </span>
            </div>
          </div>

          {/* Noise Pruned Count (Clickable) */}
          <button
            onClick={onOpenPruning}
            className="flex items-center gap-2 px-2.5 py-1.5 rounded bg-purple-500/10 border border-purple-500/30 hover:bg-purple-500/20 text-left transition group cursor-pointer"
            title="Click to view forensic pruning audit"
          >
            <FilterX className="h-3.5 w-3.5 text-purple-600 dark:text-purple-400 shrink-0 group-hover:scale-110 transition" />
            <div>
              <span className="text-[10px] uppercase font-semibold text-purple-700 dark:text-purple-300 flex items-center gap-1 leading-tight">
                Noise Pruned
                <ExternalLink className="h-2.5 w-2.5 opacity-70" />
              </span>
              <span className="font-bold font-mono text-purple-800 dark:text-purple-200">
                {prunedCount} transfers (&lt; ${meta.min_relevant_usd.toFixed(2)})
              </span>
            </div>
          </button>
        </div>

        {/* Execution Duration & Bounds Notice */}
        <div className="flex items-center gap-3 text-xs text-surface-500">
          {meta.bounds_hit && (
            <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-500/30 font-medium">
              <ShieldAlert className="h-3.5 w-3.5 text-amber-600" />
              Safety Bounds Enforced
            </span>
          )}
          <div className="flex items-center gap-1 font-mono">
            <Timer className="h-3.5 w-3.5 text-surface-400" />
            <span>{meta.duration_ms} ms</span>
          </div>
        </div>
      </div>
    </div>
  );
};
