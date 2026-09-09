import React, { useState } from 'react';
import { 
  Building2, 
  ShieldCheck, 
  AlertTriangle, 
  ChevronDown, 
  ChevronUp, 
  FileText, 
  Shield, 
  ArrowRight,
  Zap,
  Info
} from 'lucide-react';
import type { TraceAttributionReport, CandidateAttribution } from '../../types/graph';

interface VaspAttributionBannerProps {
  attribution: TraceAttributionReport | null;
  loading?: boolean;
  onNavigateToEvidence?: () => void;
  onOpenReportModal?: () => void;
  executionMode?: 'DEMO' | 'LIVE' | string;
}

export const VaspAttributionBanner: React.FC<VaspAttributionBannerProps> = ({
  attribution,
  loading = false,
  onNavigateToEvidence,
  onOpenReportModal,
  executionMode = 'DEMO',
}) => {
  const [expanded, setExpanded] = useState(false);

  if (loading) {
    return (
      <div className="mx-4 mt-3 p-3 bg-police-900/90 border border-police-800 rounded-xl flex items-center gap-3 animate-pulse">
        <div className="h-9 w-9 rounded-lg bg-police-800" />
        <div className="space-y-1.5 flex-1">
          <div className="h-3.5 bg-police-800 rounded w-1/3" />
          <div className="h-2.5 bg-police-800/60 rounded w-1/2" />
        </div>
      </div>
    );
  }

  const bestCandidate: CandidateAttribution | undefined = attribution?.best_candidate || attribution?.candidates?.[0];

  if (!attribution || !bestCandidate) {
    return null;
  }

  const isDemo = executionMode === 'DEMO';
  const confidencePct = bestCandidate.confidence_percentage ?? Math.round(bestCandidate.confidence * 100);
  const confidenceBand = bestCandidate.confidence_band || (confidencePct >= 80 ? 'HIGH' : confidencePct >= 60 ? 'MODERATE' : 'LOW');
  
  const bandBadgeColor = 
    confidenceBand === 'VERY HIGH' || confidenceBand === 'HIGH'
      ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
      : confidenceBand === 'MODERATE'
      ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
      : 'bg-slate-500/20 text-slate-300 border-slate-500/40';

  return (
    <div className="mx-4 mt-3 bg-police-900/95 border border-police-700/80 rounded-xl shadow-xl overflow-hidden backdrop-blur-md transition-all">
      {/* Main Attribution Bar */}
      <div className="p-3.5 flex flex-wrap items-center justify-between gap-3 bg-gradient-to-r from-blue-950/40 via-police-900 to-police-900">
        <div className="flex items-center gap-3 min-w-0">
          <div className="h-10 w-10 rounded-xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center shrink-0 shadow-inner">
            <Building2 className="h-5 w-5 text-amber-400" />
          </div>

          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                Attributed VASP Hypothesis:
              </span>
              <span className="text-base font-extrabold text-white tracking-tight flex items-center gap-1.5">
                {bestCandidate.vasp_name}
                <ShieldCheck className="h-4 w-4 text-emerald-400 shrink-0" />
              </span>
              <span className={`px-2 py-0.5 text-[10px] font-mono font-bold rounded border ${bandBadgeColor}`}>
                {confidencePct}% {confidenceBand}
              </span>
              {isDemo && (
                <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-amber-500/15 text-amber-300 border border-amber-500/30 flex items-center gap-1">
                  <Zap className="h-3 w-3 text-amber-400" />
                  DEMO FIXTURE
                </span>
              )}
            </div>

            <div className="flex items-center gap-2 text-xs text-slate-400 mt-0.5 truncate">
              <span>Candidate Deposit Wallet:</span>
              <span className="font-mono text-slate-200 text-[11px] bg-police-800/80 px-1.5 py-0.5 rounded border border-police-700 truncate max-w-[280px]">
                {bestCandidate.candidate_address}
              </span>
              <span className="text-slate-500 hidden sm:inline">•</span>
              <span className="text-slate-400 text-[11px] hidden sm:inline italic">
                Investigative finding under Section 94 BNSS
              </span>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => setExpanded(!expanded)}
            className="px-2.5 py-1.5 text-xs text-slate-300 bg-police-800 hover:bg-police-700 border border-police-700 rounded-lg transition flex items-center gap-1.5"
          >
            <Info className="h-3.5 w-3.5 text-blue-400" />
            <span>Score Factors</span>
            {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          </button>

          {onNavigateToEvidence && (
            <button
              onClick={onNavigateToEvidence}
              className="px-3 py-1.5 text-xs font-semibold text-slate-200 bg-police-800 hover:bg-police-700 border border-police-600 rounded-lg transition flex items-center gap-1.5"
              title="Inspect Section 65B/63 BSA Verifiable Evidence DAG"
            >
              <Shield className="h-3.5 w-3.5 text-emerald-400" />
              <span>Evidence DAG</span>
              <ArrowRight className="h-3 w-3 text-slate-400" />
            </button>
          )}

          {onOpenReportModal && (
            <button
              onClick={onOpenReportModal}
              className="px-3 py-1.5 text-xs font-bold text-police-950 bg-gradient-to-r from-amber-400 to-amber-300 hover:from-amber-300 hover:to-amber-200 rounded-lg shadow-md transition flex items-center gap-1.5"
              title="Draft Legal Section 94 BNSS Order for Binance"
            >
              <FileText className="h-3.5 w-3.5 text-police-950" />
              <span>Draft Sec 94 BNSS</span>
            </button>
          )}
        </div>
      </div>

      {/* Factor Breakdown Pills / Details (Collapsible) */}
      {expanded && (
        <div className="border-t border-police-800 bg-police-950/60 p-3.5 text-xs space-y-3 animate-in fade-in duration-150">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-2.5">
            {/* Direct Tag / Downstream Match */}
            <div className="p-2.5 rounded-lg bg-police-900 border border-police-800 space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-[10px] uppercase font-bold text-slate-400">Target / Downstream</span>
                <span className="font-mono font-bold text-emerald-400">
                  {bestCandidate.factors?.downstream_vasp_match != null 
                    ? `${(bestCandidate.factors.downstream_vasp_match * 100).toFixed(0)}%` 
                    : `${((bestCandidate.factors?.direct_tag || 0) * 100).toFixed(0)}%`}
                </span>
              </div>
              <p className="text-[11px] text-slate-300 leading-tight">
                {bestCandidate.explanations?.downstream_vasp_match || bestCandidate.explanations?.direct_tag || 'Consolidation matches verified registry.'}
              </p>
            </div>

            {/* Sweep Score */}
            <div className="p-2.5 rounded-lg bg-police-900 border border-police-800 space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-[10px] uppercase font-bold text-slate-400">Sweep Consolidation</span>
                <span className="font-mono font-bold text-blue-400">
                  {((bestCandidate.factors?.sweep || 0) * 100).toFixed(1)}%
                </span>
              </div>
              <p className="text-[11px] text-slate-300 leading-tight">
                {bestCandidate.explanations?.sweep || 'Automated outgoing sweep to exchange hot wallet.'}
              </p>
            </div>

            {/* Fan-in Score */}
            <div className="p-2.5 rounded-lg bg-police-900 border border-police-800 space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-[10px] uppercase font-bold text-slate-400">Fan-In Convergence</span>
                <span className="font-mono font-bold text-purple-400">
                  {((bestCandidate.factors?.fan_in || 0) * 100).toFixed(0)}%
                </span>
              </div>
              <p className="text-[11px] text-slate-300 leading-tight">
                {bestCandidate.explanations?.fan_in || 'Multiple upstream deposit sources converge.'}
              </p>
            </div>

            {/* Temporal Score */}
            <div className="p-2.5 rounded-lg bg-police-900 border border-police-800 space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-[10px] uppercase font-bold text-slate-400">Temporal Delay</span>
                <span className="font-mono font-bold text-amber-400">
                  {((bestCandidate.factors?.temporal || 0) * 100).toFixed(0)}%
                </span>
              </div>
              <p className="text-[11px] text-slate-300 leading-tight">
                {bestCandidate.explanations?.temporal || 'Automated deposit-to-sweep delay under 1 hour.'}
              </p>
            </div>
          </div>

          {/* Evidence bullet points */}
          {bestCandidate.evidence_bullet_points && bestCandidate.evidence_bullet_points.length > 0 && (
            <div className="p-2.5 bg-police-900/80 border border-police-800 rounded-lg">
              <div className="text-[10px] uppercase font-bold text-slate-400 mb-1.5">
                Verifiable Factual Points (Section 63 BSA Hash Chain):
              </div>
              <ul className="list-disc list-inside space-y-1 text-[11px] text-slate-300">
                {bestCandidate.evidence_bullet_points.map((pt, idx) => (
                  <li key={idx} className="font-mono text-[11px]">{pt}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Disclaimer */}
          <div className="text-[10px] text-slate-500 italic flex items-center gap-1.5">
            <AlertTriangle className="h-3.5 w-3.5 text-amber-400 shrink-0" />
            <span>
              {attribution.disclaimer || 'Attribution represents an investigative hypothesis based on deterministic heuristics and verifiable on-chain facts. It does not constitute conclusive legal proof.'}
            </span>
          </div>
        </div>
      )}
    </div>
  );
};
