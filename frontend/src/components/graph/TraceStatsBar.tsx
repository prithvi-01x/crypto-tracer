import React from 'react';
import { 
  GitFork, 
  Layers, 
  ShieldAlert, 
  FilterX, 
  Timer, 
  CheckCircle2, 
  Sparkles,
  ExternalLink,
  Zap,
  Globe
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
        <div className="flex flex-wrap items-center gap-2 sm:gap-4 text-xs">
          {/* Hops */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-police-900/80 border border-police-700/60">
            <Layers className="h-4 w-4 text-blue-400 shrink-0" />
            <div>
              <span className="text-[10px] uppercase font-medium text-slate-400 block leading-tight">Traversal Depth</span>
              <span className="font-bold font-mono text-slate-200">
                Hop {meta.hops_reached} / {meta.max_hops_configured}
              </span>
            </div>
          </div>

          {/* Raw Transfers */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-police-900/80 border border-police-700/60">
            <GitFork className="h-4 w-4 text-slate-400 shrink-0" />
            <div>
              <span className="text-[10px] uppercase font-medium text-slate-400 block leading-tight">Raw Fetched</span>
              <span className="font-bold font-mono text-slate-200">{meta.raw_transfers_fetched_count} txs</span>
            </div>
          </div>

          {/* Traversal Relevant */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-police-900/80 border border-police-700/60">
            <Sparkles className="h-4 w-4 text-amber-400 shrink-0" />
            <div>
              <span className="text-[10px] uppercase font-medium text-slate-400 block leading-tight">Relevant Txs</span>
              <span className="font-bold font-mono text-amber-300">{meta.traversal_relevant_transfers_count}</span>
            </div>
          </div>

          {/* Graph Edges & Nodes */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-police-900/80 border border-police-700/60">
            <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
            <div>
              <span className="text-[10px] uppercase font-medium text-slate-400 block leading-tight">Active Graph</span>
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
              <span className="text-[10px] uppercase font-medium text-purple-300 flex items-center gap-1 leading-tight">
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
        <div className="flex items-center gap-3 text-xs text-slate-400">
          {meta.execution_mode === 'DEMO' ? (
            <span className="flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-lg bg-amber-500/15 text-amber-300 border border-amber-500/40 font-bold">
              <Zap className="h-3 w-3 text-amber-400" />
              DEMO REPLAY
            </span>
          ) : meta.execution_mode === 'LIVE' ? (
            <span className="flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-lg bg-emerald-500/15 text-emerald-300 border border-emerald-500/40 font-bold">
              <Globe className="h-3 w-3 text-emerald-400" />
              LIVE TRON
            </span>
          ) : null}
          {meta.is_partial && (
            <span className="flex items-center gap-1 text-[11px] px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
              <ShieldAlert className="h-3 w-3 text-amber-400" />
              Partial Trace {meta.boundary_reached ? `[${meta.boundary_reached}]` : ''}
            </span>
          )}
          {meta.bounds_hit && !meta.is_partial && (
            <span className="flex items-center gap-1 text-[11px] px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
              <ShieldAlert className="h-3 w-3" />
              Safety Bounds Enforced
            </span>
          )}
          <div className="flex items-center gap-1 font-mono text-[11px]">
            <Timer className="h-3.5 w-3.5 text-slate-500" />
            <span>{meta.duration_ms} ms</span>
          </div>
        </div>
      </div>
    </div>
  );
};
