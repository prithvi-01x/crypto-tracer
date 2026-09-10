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
    <div className="bg-police-800/90 border border-police-700/80 rounded-xl p-3.5 shadow-md">
      <div className="flex flex-wrap items-center justify-between gap-4">
        {/* Metric Cards Group */}
        <div className="flex flex-wrap items-center gap-2 sm:gap-4 text-base">
          {/* Hops */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-police-900/80 border border-police-700/60">
            <Layers className="h-4 w-4 text-brand-blue shrink-0" />
            <div>
              <span className="text-sm uppercase font-medium text-surface-400 block leading-tight">Traversal Depth</span>
              <span className="font-bold font-mono text-surface-200">
                Hop {meta.hops_reached} / {meta.max_hops_configured}
              </span>
            </div>
          </div>

          {/* Raw Transfers */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-police-900/80 border border-police-700/60">
            <GitFork className="h-4 w-4 text-surface-400 shrink-0" />
            <div>
              <span className="text-sm uppercase font-medium text-surface-400 block leading-tight">Raw Fetched</span>
              <span className="font-bold font-mono text-surface-200">{meta.raw_transfers_fetched_count} txs</span>
            </div>
          </div>

          {/* Traversal Relevant */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-police-900/80 border border-police-700/60">
            <Sparkles className="h-4 w-4 text-amber-400 shrink-0" />
            <div>
              <span className="text-sm uppercase font-medium text-surface-400 block leading-tight">Relevant Txs</span>
              <span className="font-bold font-mono text-amber-300">{meta.traversal_relevant_transfers_count}</span>
            </div>
          </div>

          {/* Graph Edges & Nodes */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-police-900/80 border border-police-700/60">
            <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
            <div>
              <span className="text-sm uppercase font-medium text-surface-400 block leading-tight">Active Graph</span>
              <span className="font-bold font-mono text-emerald-300">
                {meta.total_nodes} nodes • {meta.total_edges} edges
              </span>
            </div>
          </div>

          {/* Noise Pruned Count (Clickable) */}
          <button
            onClick={onOpenPruning}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-purple-950/40 border border-purple-800/60 hover:bg-purple-900/40 text-left transition group cursor-pointer"
            title="Click to view forensic pruning audit"
          >
            <FilterX className="h-4 w-4 text-purple-400 shrink-0 group-hover:scale-110 transition" />
            <div>
              <span className="text-sm uppercase font-medium text-purple-300 flex items-center gap-1 leading-tight">
                Noise Pruned
                <ExternalLink className="h-2.5 w-2.5 opacity-70" />
              </span>
              <span className="font-bold font-mono text-purple-200">
                {prunedCount} transfers (&lt; ${meta.min_relevant_usd.toFixed(2)})
              </span>
            </div>
          </button>
        </div>

        {/* Execution Duration & Bounds Notice */}
        <div className="flex items-center gap-3 text-base text-surface-400">
          {meta.bounds_hit && (
            <span className="flex items-center gap-1 text-base px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
              <ShieldAlert className="h-4 w-4" />
              Safety Bounds Enforced
            </span>
          )}
          <div className="flex items-center gap-1 font-mono text-base">
            <Timer className="h-4 w-4 text-surface-500" />
            <span>{meta.duration_ms} ms</span>
          </div>
        </div>
      </div>
    </div>
  );
};
