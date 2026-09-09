import React, { useState } from 'react';
import { 
  X, 
  Layers, 
  Filter, 
  Play, 
  Loader2, 
  AlertCircle,
  Sparkles,
  Zap,
  Globe
} from 'lucide-react';
import type { TraceCreateInput } from '../../types/graph';

const CANONICAL_DEMO_WALLET = 'TSuspectScamRootWallet111111111111';

interface TraceLauncherModalProps {
  isOpen: boolean;
  onClose: () => void;
  caseId: string;
  defaultWallet?: string | null;
  onTraceStarted: (traceId: string) => void;
  startTraceFn: (input: TraceCreateInput) => Promise<{ trace_id: string }>;
}

export const TraceLauncherModal: React.FC<TraceLauncherModalProps> = ({
  isOpen,
  onClose,
  caseId,
  defaultWallet,
  onTraceStarted,
  startTraceFn,
}) => {
  const [wallet, setWallet] = useState(defaultWallet || '');
  const [maxHops, setMaxHops] = useState<number>(4);
  const [minRelevantUsd, setMinRelevantUsd] = useState<number>(1.0);
  const [executionMode, setExecutionMode] = useState<'DEMO' | 'LIVE'>('DEMO');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleUseCanonicalDemo = () => {
    setWallet(CANONICAL_DEMO_WALLET);
    setMaxHops(4);
    setMinRelevantUsd(1.0);
    setExecutionMode('DEMO');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!wallet.trim()) {
      setError('Please provide a suspect TRON wallet address.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const res = await startTraceFn({
        case_id: caseId,
        chain: 'TRON',
        input_type: 'address',
        input: wallet.trim(),
        asset: 'TRC20:USDT',
        max_hops: maxHops,
        min_relevant_usd: minRelevantUsd,
        execution_mode: executionMode,
      });

      onTraceStarted(res.trace_id);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to start blockchain trace');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="w-full max-w-lg bg-police-900 border border-police-700 rounded-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="p-5 border-b border-police-800 bg-police-800/60 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center">
              <Play className="h-4 w-4 text-blue-400" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white uppercase tracking-wider">
                Initiate Multi-Hop Trace
              </h2>
              <p className="text-xs text-slate-400">
                Execute BFS traversal with forensic relevance pruning
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={loading}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-police-800 transition disabled:opacity-50"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="m-4 p-3 rounded-lg bg-red-950/60 border border-red-800 text-red-200 text-xs flex items-center gap-2">
            <AlertCircle className="h-4 w-4 text-red-400 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-5 space-y-4 text-xs">
          {/* Canonical Scenario Quick Load Banner */}
          <div className="p-3 bg-gradient-to-r from-amber-500/10 via-amber-500/5 to-transparent border border-amber-500/30 rounded-xl flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="p-1.5 rounded-lg bg-amber-500/20 text-amber-400">
                <Sparkles className="h-4 w-4" />
              </div>
              <div>
                <div className="font-semibold text-amber-300 text-[11px]">SIH Canonical Demo Scenario</div>
                <div className="text-[10px] text-slate-400">4-hop TRC-20 USDT scam flow $\rightarrow$ Binance consolidation</div>
              </div>
            </div>
            <button
              type="button"
              onClick={handleUseCanonicalDemo}
              className="px-2.5 py-1 text-[11px] font-semibold bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 rounded-lg transition"
            >
              Autofill Scenario
            </button>
          </div>

          {/* Execution Mode Selector */}
          <div className="space-y-1.5">
            <label className="block text-slate-300 font-semibold uppercase text-[10px] tracking-wider">
              Execution Mode
            </label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setExecutionMode('DEMO')}
                className={`p-2.5 rounded-lg border text-left transition flex items-start gap-2 ${
                  executionMode === 'DEMO'
                    ? 'bg-amber-500/15 border-amber-500/60 text-amber-200 ring-1 ring-amber-500/40'
                    : 'bg-police-800/60 border-police-700 text-slate-400 hover:text-slate-200'
                }`}
              >
                <Zap className={`h-4 w-4 mt-0.5 shrink-0 ${executionMode === 'DEMO' ? 'text-amber-400' : 'text-slate-500'}`} />
                <div>
                  <div className="font-bold text-[11px] text-slate-200">⚡ Demo / Replay Mode</div>
                  <div className="text-[10px] text-slate-400">Deterministic fixtures, zero latency, offline-resilient</div>
                </div>
              </button>

              <button
                type="button"
                onClick={() => setExecutionMode('LIVE')}
                className={`p-2.5 rounded-lg border text-left transition flex items-start gap-2 ${
                  executionMode === 'LIVE'
                    ? 'bg-emerald-500/15 border-emerald-500/60 text-emerald-200 ring-1 ring-emerald-500/40'
                    : 'bg-police-800/60 border-police-700 text-slate-400 hover:text-slate-200'
                }`}
              >
                <Globe className={`h-4 w-4 mt-0.5 shrink-0 ${executionMode === 'LIVE' ? 'text-emerald-400' : 'text-slate-500'}`} />
                <div>
                  <div className="font-bold text-[11px] text-slate-200">🌐 Live TRON RPC</div>
                  <div className="text-[10px] text-slate-400">Live TronGrid API, real on-chain transaction data</div>
                </div>
              </button>
            </div>
          </div>

          {/* Target Address */}
          <div className="space-y-1.5">
            <label className="block text-slate-300 font-semibold uppercase text-[10px] tracking-wider">
              Suspect TRON Address (Base58Check) <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              required
              value={wallet}
              onChange={(e) => setWallet(e.target.value)}
              placeholder="e.g. TYDZSxdBzWnCuB4jF3K6j5X3qW7b9X1234"
              className="w-full px-3 py-2 bg-police-800 border border-police-700 rounded-lg text-slate-100 font-mono placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* Chain & Asset */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="block text-slate-400 font-semibold uppercase text-[10px] tracking-wider">
                Blockchain
              </label>
              <input
                type="text"
                disabled
                value="TRON Mainnet"
                className="w-full px-3 py-2 bg-police-950/80 border border-police-800 rounded-lg text-slate-400 font-medium cursor-not-allowed"
              />
            </div>
            <div className="space-y-1.5">
              <label className="block text-slate-400 font-semibold uppercase text-[10px] tracking-wider">
                Target Token
              </label>
              <input
                type="text"
                disabled
                value="TRC-20 Tether (USDT)"
                className="w-full px-3 py-2 bg-police-950/80 border border-police-800 rounded-lg text-slate-400 font-medium cursor-not-allowed"
              />
            </div>
          </div>

          {/* Max Hops Depth */}
          <div className="space-y-1.5">
            <div className="flex justify-between items-center">
              <label className="text-slate-300 font-semibold uppercase text-[10px] tracking-wider flex items-center gap-1.5">
                <Layers className="h-3.5 w-3.5 text-blue-400" />
                Maximum Traversal Depth (Hops)
              </label>
              <span className="font-mono font-bold text-blue-400">{maxHops} Hops</span>
            </div>
            <input
              type="range"
              min="1"
              max="6"
              step="1"
              value={maxHops}
              onChange={(e) => setMaxHops(parseInt(e.target.value))}
              className="w-full accent-blue-500 cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-slate-500">
              <span>Hop 1 (Direct)</span>
              <span>Hop 4 (Standard)</span>
              <span>Hop 6 (Deep)</span>
            </div>
          </div>

          {/* Relevance Pruning Threshold */}
          <div className="space-y-1.5">
            <div className="flex justify-between items-center">
              <label className="text-slate-300 font-semibold uppercase text-[10px] tracking-wider flex items-center gap-1.5">
                <Filter className="h-3.5 w-3.5 text-purple-400" />
                Minimum Relevant Transfer (Dust Threshold)
              </label>
              <span className="font-mono font-bold text-purple-400">${minRelevantUsd.toFixed(2)} USDT</span>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min="0"
                step="0.1"
                value={minRelevantUsd}
                onChange={(e) => setMinRelevantUsd(parseFloat(e.target.value) || 0)}
                className="w-full px-3 py-2 bg-police-800 border border-police-700 rounded-lg text-slate-100 font-mono focus:outline-none focus:border-purple-500"
              />
              <span className="text-slate-400 font-semibold">USD</span>
            </div>
            <p className="text-[10px] text-slate-500">
              Transfers below this threshold will be pruned as DUST and logged for forensic audit.
            </p>
          </div>

          {/* Footer Actions */}
          <div className="pt-3 border-t border-police-800 flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 rounded-lg bg-police-800 hover:bg-police-700 text-slate-300 transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-5 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-bold transition flex items-center gap-2 shadow-lg shadow-blue-500/20 disabled:opacity-50"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Tracing Blockchain...
                </>
              ) : (
                <>
                  <Play className="h-4 w-4" />
                  Execute Trace
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
