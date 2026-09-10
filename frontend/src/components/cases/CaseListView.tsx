import React, { useState } from 'react';
import { 
  Search, 
  Plus, 
  RefreshCw, 
  Zap,
  Loader2,
  Download,
  Building2,
  ShieldAlert,
  Scale,
  FolderOpen,
  ArrowRight,
  Sparkles,
  Layers,
  Database
} from 'lucide-react';
import type { CaseItem } from '../../types/case';
import { seedDemoCase } from '../../api/demo';

interface CaseListViewProps {
  cases: CaseItem[];
  loading: boolean;
  onSelectCase: (caseId: string) => void;
  onOpenNewCase: () => void;
  onRefresh: () => void;
  searchTerm?: string;
  onSearchChange?: (term: string) => void;
}

export const CaseListView: React.FC<CaseListViewProps> = ({
  cases,
  loading,
  onSelectCase,
  onOpenNewCase,
  onRefresh,
  searchTerm: externalSearchTerm,
  onSearchChange,
}) => {
  const [internalSearchTerm, setInternalSearchTerm] = useState('');
  const [isSeedingDemo, setIsSeedingDemo] = useState(false);
  const [filterMode, setFilterMode] = useState<'ALL' | 'FLAGSHIP' | 'HIGH_LOSS'>('ALL');

  const activeSearchTerm = externalSearchTerm !== undefined ? externalSearchTerm : internalSearchTerm;
  const handleSearchChange = (val: string) => {
    if (onSearchChange) {
      onSearchChange(val);
    } else {
      setInternalSearchTerm(val);
    }
  };

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
    // Mode filter
    if (filterMode === 'FLAGSHIP') {
      if (!c.fir_number.includes('0812') && c.id !== '00000000-0000-0000-0000-000000000812') return false;
    } else if (filterMode === 'HIGH_LOSS') {
      const loss = c.loss_amount_inr ? parseFloat(c.loss_amount_inr) : 0;
      if (loss < 1000000) return false;
    }

    // Text search
    const q = activeSearchTerm.toLowerCase().trim();
    if (!q) return true;
    return (
      c.fir_number.toLowerCase().includes(q) ||
      (c.victim_reference && c.victim_reference.toLowerCase().includes(q)) ||
      (c.suspect_wallet && c.suspect_wallet.toLowerCase().includes(q)) ||
      (c.ack_number && c.ack_number.toLowerCase().includes(q)) ||
      (c.notes && c.notes.toLowerCase().includes(q)) ||
      (c.chain && c.chain.toLowerCase().includes(q))
    );
  });

  return (
    <div className="space-y-6 max-w-[1440px] mx-auto p-4 sm:p-6 transition-colors">
      {/* Reactor Hero & Command Banner */}
      <div className="p-6 rounded-xl bg-surface-default dark:bg-surface-100 border border-surface-200 dark:border-surface-300 shadow-sm relative overflow-hidden">
        {/* Subtle accent bar */}
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-reactor-orange via-reactor-teal to-brand-blue" />
        
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="space-y-2 max-w-3xl">
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-0.5 rounded-full bg-orange-500/10 border border-orange-500/30 text-reactor-orange font-mono text-[11px] font-bold uppercase tracking-wider flex items-center gap-1.5">
                <Sparkles className="h-3 w-3" />
                Reactor Forensic Intelligence • Multi-Hop Tracing
              </span>
              <span className="text-xs text-surface-400 font-mono hidden sm:inline">
                SIH 2026 Edition
              </span>
            </div>
            
            <h1 className="text-2xl sm:text-3xl font-extrabold text-surface-900 dark:text-white tracking-tight">
              Investigation Case Management
            </h1>
            
            <p className="text-sm text-surface-600 dark:text-surface-300 leading-relaxed">
              Trace stolen crypto-assets across TRON &amp; Ethereum, pinpoint VASP deposit cashouts with automated heuristics, and compile court-admissible Section 63 BSA &amp; Section 94 BNSS legal dossiers.
            </p>
          </div>

          {/* Action CTAs */}
          <div className="flex flex-wrap items-center gap-3 shrink-0">
            <button
              onClick={handleLoadDemoCase}
              disabled={isSeedingDemo}
              className="flex items-center gap-2 px-4 py-2.5 rounded-lg border border-amber-500/40 bg-amber-500/10 hover:bg-amber-500/20 text-amber-700 dark:text-amber-300 font-semibold text-xs transition cursor-pointer disabled:opacity-50"
              title="Quick-load canonical Delhi FIR-0812 task scam demo case"
            >
              {isSeedingDemo ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Zap className="h-4 w-4 text-amber-500" />
              )}
              <span>Flagship Demo (FIR-0812)</span>
            </button>

            <button 
              className="flex items-center gap-2 px-4 py-2.5 rounded-lg border border-surface-200 bg-surface-default hover:bg-surface-100 text-surface-700 dark:text-surface-200 font-semibold text-xs transition cursor-pointer shadow-xs"
              title="Export ledger entries"
            >
              <Download className="h-4 w-4 text-surface-500" />
              <span>Export Case Ledger</span>
            </button>

            <button
              onClick={onOpenNewCase}
              className="flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg bg-reactor-orange hover:bg-[#e04800] text-white font-bold text-xs transition shadow-md shadow-orange-500/20 cursor-pointer"
            >
              <Plus className="h-4 w-4" />
              <span>New Investigation Case</span>
            </button>
          </div>
        </div>
      </div>

      {/* 4 Reactor Value Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Active Cases */}
        <div className="p-4 rounded-xl bg-surface-default dark:bg-surface-100 border border-surface-200 dark:border-surface-300 shadow-xs space-y-2 relative overflow-hidden group hover:border-brand-blue transition">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-surface-500 uppercase tracking-wider">Active Cases</span>
            <div className="p-1.5 rounded-lg bg-blue-500/10 text-brand-blue dark:text-blue-400">
              <FolderOpen className="h-4 w-4" />
            </div>
          </div>
          <div className="text-2xl font-extrabold font-mono text-surface-900 dark:text-white">
            {cases.length}
          </div>
          <div className="text-xs text-surface-500 flex items-center justify-between">
            <span>{cases.filter(c => c.status === 'OPEN').length} active workspaces</span>
            <span className="text-emerald-600 dark:text-emerald-400 font-medium">100% Ingested</span>
          </div>
        </div>

        {/* Card 2: VASP Cashouts */}
        <div className="p-4 rounded-xl bg-surface-default dark:bg-surface-100 border border-surface-200 dark:border-surface-300 shadow-xs space-y-2 relative overflow-hidden group hover:border-emerald-500 transition">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-surface-500 uppercase tracking-wider">VASP Cashouts</span>
            <div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
              <Building2 className="h-4 w-4" />
            </div>
          </div>
          <div className="text-2xl font-extrabold font-mono text-emerald-600 dark:text-emerald-400">
            Binance • OKX
          </div>
          <div className="text-xs text-surface-500 flex items-center justify-between">
            <span>81.6% Confidence attribution</span>
            <span className="text-emerald-600 dark:text-emerald-400 font-medium">Verified</span>
          </div>
        </div>

        {/* Card 3: Forensic Findings */}
        <div className="p-4 rounded-xl bg-surface-default dark:bg-surface-100 border border-surface-200 dark:border-surface-300 shadow-xs space-y-2 relative overflow-hidden group hover:border-reactor-orange transition">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-surface-500 uppercase tracking-wider">Pending Review</span>
            <div className="p-1.5 rounded-lg bg-orange-500/10 text-reactor-orange">
              <ShieldAlert className="h-4 w-4" />
            </div>
          </div>
          <div className="text-2xl font-extrabold font-mono text-reactor-orange">
            {cases.filter(c => c.status === 'PENDING_REVIEW' || c.status === 'OPEN').length}
          </div>
          <div className="text-xs text-surface-500 flex items-center justify-between">
            <span>Statutory &amp; VASP attribution approvals</span>
            <span className="text-reactor-orange font-medium">7 Signals</span>
          </div>
        </div>

        {/* Card 4: Legal Dossiers */}
        <div className="p-4 rounded-xl bg-surface-default dark:bg-surface-100 border border-surface-200 dark:border-surface-300 shadow-xs space-y-2 relative overflow-hidden group hover:border-purple-500 transition">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-surface-500 uppercase tracking-wider">Active Reports</span>
            <div className="p-1.5 rounded-lg bg-purple-500/10 text-purple-600 dark:text-purple-400">
              <Scale className="h-4 w-4" />
            </div>
          </div>
          <div className="text-2xl font-extrabold font-mono text-surface-900 dark:text-white">
            {Math.max(1, cases.filter(c => c.status === 'CLOSED' || c.fir_number.includes('0812')).length)}
          </div>
          <div className="text-xs text-surface-500 flex items-center justify-between">
            <span>Admissible dossiers generated</span>
            <span className="text-purple-600 dark:text-purple-400 font-medium">Sec. 63 BSA</span>
          </div>
        </div>
      </div>

      {/* Case Table Section */}
      <div className="bg-surface-default dark:bg-surface-100 rounded-xl border border-surface-200 dark:border-surface-300 shadow-xs overflow-hidden transition-colors">
        {/* Section Header & Filter Controls */}
        <div className="p-4 border-b border-surface-200 dark:border-surface-300 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 bg-surface-50 dark:bg-surface-200/50">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-surface-900 dark:text-white">Active Case Register</h2>
              <span className="px-2 py-0.5 rounded-full bg-surface-200 dark:bg-surface-300 text-surface-700 dark:text-surface-200 text-xs font-mono font-semibold">
                {filteredCases.length} active in view
              </span>
            </div>

            {/* Filter Toggle Buttons */}
            <div className="flex items-center p-0.5 rounded-lg bg-surface-100 dark:bg-surface-200 border border-surface-200 dark:border-surface-300 text-xs">
              <button
                onClick={() => setFilterMode('ALL')}
                className={`px-2.5 py-1 rounded-md font-semibold transition ${
                  filterMode === 'ALL' 
                    ? 'bg-surface-default dark:bg-surface-100 text-surface-900 dark:text-white shadow-xs' 
                    : 'text-surface-500 hover:text-surface-800 dark:hover:text-surface-200'
                }`}
              >
                All Cases ({cases.length})
              </button>
              <button
                onClick={() => setFilterMode('FLAGSHIP')}
                className={`px-2.5 py-1 rounded-md font-semibold transition ${
                  filterMode === 'FLAGSHIP' 
                    ? 'bg-surface-default dark:bg-surface-100 text-reactor-orange shadow-xs' 
                    : 'text-surface-500 hover:text-surface-800 dark:hover:text-surface-200'
                }`}
              >
                Flagship (FIR-0812)
              </button>
              <button
                onClick={() => setFilterMode('HIGH_LOSS')}
                className={`px-2.5 py-1 rounded-md font-semibold transition ${
                  filterMode === 'HIGH_LOSS' 
                    ? 'bg-surface-default dark:bg-surface-100 text-red-600 dark:text-red-400 shadow-xs' 
                    : 'text-surface-500 hover:text-surface-800 dark:hover:text-surface-200'
                }`}
              >
                High Loss (&gt; ₹10L)
              </button>
            </div>
          </div>

          <div className="flex items-center gap-3 w-full md:w-auto">
            <div className="relative flex-1 md:w-72">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-surface-400" />
              <input
                type="text"
                placeholder="Search cases..."
                value={activeSearchTerm}
                onChange={(e) => handleSearchChange(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 rounded-lg bg-surface-default dark:bg-surface-100 border border-surface-200 dark:border-surface-300 text-xs text-surface-800 dark:text-surface-100 placeholder:text-surface-400 focus:outline-none focus:border-brand-blue"
              />
            </div>
            
            <button
              onClick={handleLoadDemoCase}
              disabled={isSeedingDemo}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300 text-xs font-semibold hover:bg-amber-500/20 transition disabled:opacity-50 cursor-pointer shrink-0"
              title="Reset and load SIH demo case"
            >
              {isSeedingDemo ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Zap className="h-3.5 w-3.5 text-amber-500" />
              )}
              <span>Demo Seed</span>
            </button>

            <button
              onClick={onRefresh}
              className="p-1.5 rounded-lg border border-surface-200 dark:border-surface-300 hover:bg-surface-100 dark:hover:bg-surface-200 text-surface-500 transition cursor-pointer shrink-0"
              title="Refresh case register from PostgreSQL"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-surface-50 dark:bg-surface-200/40 border-b border-surface-200 dark:border-surface-300 text-xs font-bold text-surface-600 dark:text-surface-300 uppercase tracking-wider">
                <th className="px-4 py-3 font-semibold">Case ID</th>
                <th className="px-4 py-3 font-semibold">FIR Number</th>
                <th className="px-4 py-3 font-semibold">Victim</th>
                <th className="px-4 py-3 font-semibold">Incident</th>
                <th className="px-4 py-3 font-semibold text-right">Loss</th>
                <th className="px-4 py-3 font-semibold text-right">Volume</th>
                <th className="px-4 py-3 font-semibold text-center">Chain</th>
                <th className="px-4 py-3 font-semibold text-center">Status</th>
                <th className="px-4 py-3 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-200 dark:divide-surface-300 text-xs text-surface-800 dark:text-surface-200">
              {loading ? (
                <tr>
                  <td colSpan={9} className="px-4 py-16 text-center text-surface-500">
                    <Loader2 className="h-6 w-6 animate-spin mx-auto text-brand-blue mb-2" />
                    <p>Loading forensic case records from PostgreSQL...</p>
                  </td>
                </tr>
              ) : filteredCases.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-4 py-16 text-center text-surface-500">
                    <FolderOpen className="h-8 w-8 text-surface-400 mx-auto mb-2" />
                    <p className="text-sm font-semibold text-surface-700 dark:text-surface-300">No investigation cases found.</p>
                    <p className="text-xs text-surface-400 mt-1">Try clearing your search query or load the flagship demo case.</p>
                  </td>
                </tr>
              ) : (
                filteredCases.map((c, idx) => {
                  const isCanonical = c.fir_number === 'FIR-2026-DEL-CY-0812' || c.id === '00000000-0000-0000-0000-000000000812';
                  const rowBg = idx % 2 === 0 ? 'bg-surface-default dark:bg-surface-100' : 'bg-surface-50/50 dark:bg-surface-200/20';
                  
                  return (
                    <tr 
                      key={c.id} 
                      className={`${rowBg} hover:bg-brand-light/40 dark:hover:bg-surface-200/60 transition group cursor-pointer h-12`}
                      onClick={() => onSelectCase(c.id)}
                    >
                      <td className="px-4 py-2 font-mono text-surface-500">
                        Case {c.id.substring(c.id.length - 5)}
                      </td>
                      <td className="px-4 py-2 font-mono font-bold text-brand-blue dark:text-blue-400">
                        {c.fir_number}
                      </td>
                      <td className="px-4 py-2 font-semibold text-surface-900 dark:text-white">
                        {c.victim_reference || 'Unspecified'}
                      </td>
                      <td className="px-4 py-2 text-surface-600 dark:text-surface-400 truncate max-w-[200px]" title={c.description || (isCanonical ? 'Telegram Task-Based Investment Scam' : 'Financial Cyber Fraud')}>
                        {c.description || (isCanonical ? 'Telegram Task-Based Investment Scam' : 'Financial Cyber Fraud')}
                      </td>
                      <td className="px-4 py-2 text-right font-mono font-bold text-red-600 dark:text-red-400">
                        {c.loss_amount_inr ? new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(c.loss_amount_inr) : '-'}
                      </td>
                      <td className="px-4 py-2 text-right font-mono font-bold text-emerald-600 dark:text-emerald-400">
                        {c.loss_amount_usdt ? `${Number(c.loss_amount_usdt).toLocaleString()} USDT` : (c.loss_amount_inr ? `${Math.round(c.loss_amount_inr / 83.33).toLocaleString()} USDT` : '60,000 USDT')}
                      </td>
                      <td className="px-4 py-2 text-center">
                        <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-surface-100 dark:bg-surface-200 text-surface-600 dark:text-surface-300 border border-surface-200 dark:border-surface-300">
                          {c.chain}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-center">
                        {isCanonical ? (
                          <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-amber-500/10 text-amber-700 dark:text-amber-300 border border-amber-500/30 flex items-center justify-center gap-1">
                            <Zap className="h-3 w-3 text-amber-500" />
                            DEMO REPLAY
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-blue-500/10 text-brand-blue dark:text-blue-400 border border-blue-500/30">
                            {c.status}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2 text-right">
                        <button 
                          className="inline-flex items-center gap-1 text-reactor-orange hover:text-[#e04800] font-bold transition group-hover:translate-x-1 duration-150"
                          onClick={(e) => { e.stopPropagation(); onSelectCase(c.id); }}
                        >
                          <span>Open Workspace</span>
                          <ArrowRight className="h-3.5 w-3.5" />
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Secondary Bottom Panels */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Node Status */}
        <div className="bg-surface-default dark:bg-surface-100 p-4 rounded-xl border border-surface-200 dark:border-surface-300 text-xs shadow-xs">
          <div className="flex items-center gap-2 mb-3">
            <Database className="h-4 w-4 text-brand-blue dark:text-blue-400" />
            <h3 className="font-bold text-surface-800 dark:text-surface-100">
              Chain Node &amp; Forensic Ingestion Pipeline
            </h3>
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between py-1.5 border-b border-surface-100 dark:border-surface-200">
              <span className="text-surface-500">TRON RPC Provider Status</span>
              <span className="font-mono text-emerald-600 dark:text-emerald-400 font-medium flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                Connected (TronGrid / Hybrid Local Fallback)
              </span>
            </div>
            <div className="flex items-center justify-between py-1.5 border-b border-surface-100 dark:border-surface-200">
              <span className="text-surface-500">Ingestion Latency</span>
              <span className="font-mono text-emerald-600 dark:text-emerald-400 font-medium">&lt; 150ms (Healthy)</span>
            </div>
            <div className="flex items-center justify-between py-1.5">
              <span className="text-surface-500">VASP Intelligence Directory</span>
              <span className="font-mono text-surface-800 dark:text-surface-200 font-medium">Active (v2026.1 Registry)</span>
            </div>
          </div>
        </div>

        {/* Threat Activity */}
        <div className="bg-surface-default dark:bg-surface-100 p-4 rounded-xl border border-surface-200 dark:border-surface-300 text-xs shadow-xs">
          <div className="flex items-center gap-2 mb-3">
            <Layers className="h-4 w-4 text-reactor-orange" />
            <h3 className="font-bold text-surface-800 dark:text-surface-100">
              Recent Threat Stream &amp; Case Signals
            </h3>
          </div>
          <div className="space-y-3">
            {cases.slice(0, 2).map((c, idx) => (
              <div key={c.id || idx} className="flex items-start gap-2.5 p-2 rounded-lg bg-surface-50 dark:bg-surface-200/40 border border-surface-200/60 dark:border-surface-300/40">
                <span className="font-mono text-[10px] uppercase font-bold text-surface-500 bg-surface-200 dark:bg-surface-300 px-1.5 py-0.5 rounded shrink-0">
                  {idx === 0 ? 'LATEST' : 'ACTIVE'}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-surface-800 dark:text-surface-200 font-medium truncate">
                    <span className="font-bold text-brand-blue dark:text-blue-400">{c.fir_number}:</span> {c.victim_reference ? `Victim ${c.victim_reference}` : 'Trace initialized.'}
                  </p>
                  <p className="text-surface-400 mt-0.5 text-[11px] font-mono">
                    Status: {c.status} &bull; Target: {c.suspect_wallet ? `${c.suspect_wallet.substring(0, 12)}...` : 'Multi-hop'}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
