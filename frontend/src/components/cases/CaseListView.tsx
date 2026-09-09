import { useState } from 'react';
import { 
  Search, 
  Plus, 
  FileText, 
  Wallet, 
  Coins, 
  Calendar, 
  ArrowRight, 
  TrendingUp, 
  ShieldAlert, 
  RefreshCw, 
  Database,
  Zap,
  Loader2
} from 'lucide-react';
import type { CaseItem } from '../../types/case';
import { seedDemoCase } from '../../api/demo';

interface CaseListViewProps {
  cases: CaseItem[];
  loading: boolean;
  onSelectCase: (caseId: string) => void;
  onOpenNewCase: () => void;
  onRefresh: () => void;
}

export const CaseListView: React.FC<CaseListViewProps> = ({
  cases,
  loading,
  onSelectCase,
  onOpenNewCase,
  onRefresh,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [isSeedingDemo, setIsSeedingDemo] = useState(false);

  const handleLoadDemoCase = async () => {
    setIsSeedingDemo(true);
    try {
      const res = await seedDemoCase();
      await onRefresh();
      if (res.case_id) {
        onSelectCase(res.case_id);
      }
    } catch (err) {
      console.error('Failed to seed demo case:', err);
    } finally {
      setIsSeedingDemo(false);
    }
  };

  const filteredCases = cases.filter((c) => {
    const q = searchTerm.toLowerCase();
    return (
      c.fir_number.toLowerCase().includes(q) ||
      (c.victim_reference && c.victim_reference.toLowerCase().includes(q)) ||
      (c.suspect_wallet && c.suspect_wallet.toLowerCase().includes(q)) ||
      (c.ack_number && c.ack_number.toLowerCase().includes(q))
    );
  });

  const totalLoss = cases.reduce((sum, c) => sum + (c.loss_amount_inr || 0), 0);
  const ackCount = cases.filter((c) => !!c.ack_number).length;

  return (
    <div className="space-y-6">
      {/* 4 Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-police-800/80 border border-police-700/70">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Active Cases</span>
            <FileText className="h-4 w-4 text-blue-400" />
          </div>
          <div className="text-2xl font-bold text-white font-mono">{cases.length}</div>
          <div className="text-[11px] text-slate-400 mt-1 flex items-center gap-1">
            <Database className="h-3 w-3 text-emerald-400" /> Stored in PostgreSQL
          </div>
        </div>

        <div className="p-4 rounded-xl bg-police-800/80 border border-police-700/70">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Reported Loss</span>
            <TrendingUp className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-emerald-400 font-mono">
            {new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(totalLoss)}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Total Complainant Defrauded</div>
        </div>

        <div className="p-4 rounded-xl bg-police-800/80 border border-police-700/70">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">1930 Portal Refs</span>
            <ShieldAlert className="h-4 w-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-amber-300 font-mono">{ackCount}</div>
          <div className="text-[11px] text-slate-400 mt-1">Cross-Referenced Incidents</div>
        </div>

        <div className="p-4 rounded-xl bg-police-800/80 border border-police-700/70">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Primary Vector</span>
            <Coins className="h-4 w-4 text-purple-400" />
          </div>
          <div className="text-sm font-bold text-white mt-1">TRON / TRC20:USDT</div>
          <div className="text-[11px] text-slate-400 mt-1">SIH P0 Blockchain Focus</div>
        </div>
      </div>

      {/* Action Header & Search */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 p-4 rounded-xl bg-police-800/50 border border-police-700/60">
        <div className="relative w-full sm:w-80">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search FIR, victim, wallet, or 1930..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 rounded-lg bg-police-900 border border-police-700 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          {/* SIH Demo Seed / Reset Button for Evaluators */}
          <button
            onClick={handleLoadDemoCase}
            disabled={isSeedingDemo}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 border border-amber-500/40 text-xs font-bold transition shadow-sm cursor-pointer disabled:opacity-50"
            title="Reset and load the canonical 4-hop TRON/USDT SIH demo case"
          >
            {isSeedingDemo ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin text-amber-400" />
                <span>Seeding Demo...</span>
              </>
            ) : (
              <>
                <Zap className="h-3.5 w-3.5 text-amber-400" />
                <span>⚡ Load SIH Demo Case</span>
              </>
            )}
          </button>

          <button
            onClick={onRefresh}
            className="p-2 rounded-lg bg-police-900 border border-police-700 hover:bg-police-800 text-slate-400 hover:text-white transition"
            title="Refresh Cases"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={onOpenNewCase}
            className="flex-1 sm:flex-initial flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-xs font-bold text-white shadow-lg shadow-blue-500/20 transition"
          >
            <Plus className="h-4 w-4" />
            New Investigation
          </button>
        </div>
      </div>

      {/* Cases List */}
      <div className="space-y-3">
        {loading ? (
          <div className="p-12 text-center text-xs text-slate-400">Loading cases from PostgreSQL...</div>
        ) : filteredCases.length === 0 ? (
          <div className="p-12 text-center rounded-xl bg-police-800/40 border border-police-700/60 space-y-3">
            <p className="text-xs text-slate-400">No investigation cases found.</p>
            <button
              onClick={onOpenNewCase}
              className="px-4 py-2 text-xs font-semibold rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition"
            >
              Register First Case
            </button>
          </div>
        ) : (
          filteredCases.map((c) => {
            const isCanonical = c.fir_number === 'FIR-2026-DEL-CY-0812' || c.id === '00000000-0000-0000-0000-000000000812';
            return (
            <div
              key={c.id}
              onClick={() => onSelectCase(c.id)}
              className={`p-4 rounded-xl border transition cursor-pointer flex flex-col md:flex-row md:items-center justify-between gap-4 group ${
                isCanonical 
                  ? 'bg-police-800/90 hover:bg-police-800 border-amber-500/40 hover:border-amber-500/60 shadow-lg shadow-amber-500/5' 
                  : 'bg-police-800/70 hover:bg-police-800 border-police-700/70 hover:border-police-600'
              }`}
            >
              <div className="space-y-1.5 flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-bold text-white group-hover:text-blue-400 transition font-mono">
                    FIR #{c.fir_number}
                  </span>
                  {isCanonical && (
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40 flex items-center gap-1">
                      <Zap className="h-3 w-3 text-amber-400" />
                      SIH CANONICAL DEMO
                    </span>
                  )}
                  <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                    {c.status}
                  </span>
                  {c.ack_number && (
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-police-700/80 text-slate-300 border border-police-600">
                      1930: {c.ack_number}
                    </span>
                  )}
                  <span className="px-2 py-0.5 rounded text-[10px] bg-police-900 text-slate-400 font-mono">
                    {c.chain} • {c.asset}
                  </span>
                </div>

                <div className="text-xs text-slate-300 flex items-center gap-2 flex-wrap">
                  <span className="font-semibold text-slate-200">
                    {c.victim_reference || 'Complainant Unspecified'}
                  </span>
                  <span className="text-slate-600">•</span>
                  <span className="text-emerald-400 font-mono font-semibold">
                    {c.loss_amount_inr !== null
                      ? new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(c.loss_amount_inr)
                      : 'Amount Unspecified'}
                  </span>
                </div>

                {c.suspect_wallet && (
                  <div className="text-[11px] font-mono text-slate-400 flex items-center gap-1 truncate">
                    <Wallet className="h-3 w-3 text-slate-500 shrink-0" />
                    <span className="text-slate-500">Target:</span>
                    <span className="text-slate-300 truncate">{c.suspect_wallet}</span>
                  </div>
                )}
              </div>

              <div className="flex items-center justify-between md:justify-end gap-4 shrink-0 pt-2 md:pt-0 border-t md:border-t-0 border-police-700/50">
                <span className="text-[11px] text-slate-500 flex items-center gap-1 font-mono">
                  <Calendar className="h-3 w-3" />
                  {new Date(c.created_at).toLocaleDateString()}
                </span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelectCase(c.id);
                  }}
                  className="flex items-center gap-1 px-3 py-1.5 text-xs font-semibold rounded-lg bg-police-700 group-hover:bg-blue-600 text-white transition"
                >
                  Inspect Case
                  <ArrowRight className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          );
        })
      )}
      </div>
    </div>
  );
};
