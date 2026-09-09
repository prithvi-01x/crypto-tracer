import React, { useState, useEffect } from 'react';
import { 
  ArrowLeft, 
  Wallet, 
  Coins, 
  Calendar, 
  User, 
  FileText, 
  Copy, 
  Check, 
  Database,
  GitBranch,
  Layers
} from 'lucide-react';
import type { CaseItem } from '../../types/case';
import { getCaseById } from '../../api/cases';

interface CaseDetailsViewProps {
  caseId: string;
  onBack: () => void;
}

export const CaseDetailsView: React.FC<CaseDetailsViewProps> = ({ caseId, onBack }) => {
  const [caseData, setCaseData] = useState<CaseItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await getCaseById(caseId);
        setCaseData(data);
      } catch (err: any) {
        setError(err.message || 'Failed to load case details');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [caseId]);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center p-16 space-y-3">
        <div className="h-8 w-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-xs text-slate-400">Loading case records from PostgreSQL...</p>
      </div>
    );
  }

  if (error || !caseData) {
    return (
      <div className="p-6 rounded-xl bg-police-800 border border-police-700 space-y-4">
        <div className="text-red-400 text-sm font-semibold">Error Loading Investigation</div>
        <p className="text-xs text-slate-300">{error || 'Case not found'}</p>
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-police-700 hover:bg-police-600 text-xs text-white"
        >
          <ArrowLeft className="h-4 w-4" /> Back to Case List
        </button>
      </div>
    );
  }

  const formattedLoss = caseData.loss_amount_inr !== null
    ? new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 }).format(caseData.loss_amount_inr)
    : 'Not Recorded';

  return (
    <div className="space-y-6">
      {/* Top Breadcrumb & Actions */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-police-800 hover:bg-police-700 border border-police-700 text-xs font-semibold text-slate-300 hover:text-white transition"
          >
            <ArrowLeft className="h-4 w-4" />
            Dashboard
          </button>
          <span className="text-slate-600">/</span>
          <span className="text-xs font-mono text-slate-400">Case #{caseData.fir_number}</span>
        </div>

        <div className="flex items-center gap-2">
          <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
            {caseData.status}
          </span>
          <span className="px-2.5 py-1 rounded-full text-xs font-mono bg-police-800 text-slate-300 border border-police-700">
            UUID: {caseData.id.slice(0, 8)}...
          </span>
        </div>
      </div>

      {/* Case Header Card */}
      <div className="p-6 rounded-xl bg-police-800/80 border border-police-700/80 shadow-lg">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-xl font-bold text-white tracking-wide">
                FIR No. {caseData.fir_number}
              </h1>
              {caseData.ack_number && (
                <span className="px-2 py-0.5 text-xs font-mono font-medium rounded bg-blue-500/20 text-blue-300 border border-blue-500/30">
                  Ref: {caseData.ack_number}
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400 mt-1 flex items-center gap-4">
              <span className="flex items-center gap-1">
                <Calendar className="h-3.5 w-3.5 text-slate-500" />
                Registered: {new Date(caseData.created_at).toLocaleString()}
              </span>
              <span className="flex items-center gap-1">
                <Database className="h-3.5 w-3.5 text-emerald-500" />
                PostgreSQL Verified
              </span>
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="text-right">
              <div className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">Reported Loss</div>
              <div className="text-lg font-bold text-emerald-400 font-mono">{formattedLoss}</div>
            </div>
          </div>
        </div>
      </div>

      {/* 2-Column Metadata Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column: Complainant & Financials */}
        <div className="space-y-6">
          <div className="p-5 rounded-xl bg-police-800/60 border border-police-700/70 space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
              <User className="h-4 w-4 text-blue-400" />
              Complainant & Case Metadata
            </h3>

            <div className="grid grid-cols-2 gap-4 text-xs">
              <div>
                <div className="text-slate-400">Victim Reference / Name</div>
                <div className="font-semibold text-white mt-0.5">
                  {caseData.victim_reference || 'Unspecified'}
                </div>
              </div>
              <div>
                <div className="text-slate-400">1930 Portal Ref</div>
                <div className="font-mono text-slate-200 mt-0.5">
                  {caseData.ack_number || 'N/A'}
                </div>
              </div>
              <div>
                <div className="text-slate-400">Case Status</div>
                <div className="font-semibold text-emerald-300 mt-0.5">{caseData.status}</div>
              </div>
              <div>
                <div className="text-slate-400">Active Traces</div>
                <div className="font-semibold text-white mt-0.5">{caseData.trace_count} Linked</div>
              </div>
            </div>
          </div>

          {/* Investigation Notes */}
          <div className="p-5 rounded-xl bg-police-800/60 border border-police-700/70 space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
              <FileText className="h-4 w-4 text-amber-400" />
              Preliminary Investigation Synopsis
            </h3>
            <div className="p-3 rounded-lg bg-police-900/80 border border-police-700/50 text-xs text-slate-300 leading-relaxed font-sans">
              {caseData.notes || 'No preliminary notes recorded for this FIR intake.'}
            </div>
          </div>
        </div>

        {/* Right Column: Suspect Wallet & Blockchain Target */}
        <div className="space-y-6">
          <div className="p-5 rounded-xl bg-police-800/60 border border-police-700/70 space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
              <Wallet className="h-4 w-4 text-emerald-400" />
              Cryptocurrency Target Specification
            </h3>

            <div className="space-y-3">
              <div>
                <div className="text-xs text-slate-400 mb-1">Suspect Unhosted Address / TxID</div>
                <div className="p-3 rounded-lg bg-police-900 border border-police-700/80 flex items-center justify-between gap-2">
                  <span className="font-mono text-xs text-emerald-300 break-all select-all">
                    {caseData.suspect_wallet || 'No wallet address supplied at intake'}
                  </span>
                  {caseData.suspect_wallet && (
                    <button
                      onClick={() => copyToClipboard(caseData.suspect_wallet!)}
                      className="p-1.5 rounded-md hover:bg-police-800 text-slate-400 hover:text-white transition shrink-0"
                      title="Copy Address"
                    >
                      {copied ? <Check className="h-4 w-4 text-emerald-400" /> : <Copy className="h-4 w-4" />}
                    </button>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 text-xs pt-2">
                <div>
                  <div className="text-slate-400">Target Blockchain</div>
                  <div className="font-semibold text-white mt-0.5 flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full bg-red-500" />
                    {caseData.chain} Mainnet
                  </div>
                </div>
                <div>
                  <div className="text-slate-400">Tracked Asset Standard</div>
                  <div className="font-semibold text-white mt-0.5 flex items-center gap-1.5">
                    <Coins className="h-3.5 w-3.5 text-emerald-400" />
                    {caseData.asset}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Phase 2 Pipeline Readiness Banner */}
          <div className="p-5 rounded-xl bg-police-800/60 border border-police-700/70 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
                <GitBranch className="h-4 w-4 text-purple-400" />
                Pipeline Execution Status
              </h3>
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-police-700 text-slate-300">
                Phase 1 Active
              </span>
            </div>

            <p className="text-xs text-slate-400 leading-relaxed">
              Case record is durably stored in PostgreSQL. In <strong>Phase 2 (TRON Data Ingestion)</strong>, this suspect wallet will connect to the official TronGrid REST API adapter to pull and normalize TRC-20 USDT transfer records.
            </p>

            <div className="pt-2">
              <button
                disabled
                className="w-full py-2.5 px-4 rounded-lg bg-police-700/50 border border-police-600/40 text-xs font-semibold text-slate-400 cursor-not-allowed flex items-center justify-center gap-2"
              >
                <Layers className="h-4 w-4 text-slate-500" />
                Initiate Blockchain Trace (Queued for Phase 2)
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
