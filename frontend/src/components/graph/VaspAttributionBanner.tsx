import React, { useState } from 'react';
import { 
  Building2, 
  AlertTriangle, 
  FileText, 
  CheckCircle2,
  ListChecks,
  Copy,
  Check,
  Network,
  ShieldCheck,
  ExternalLink,
  Info
} from 'lucide-react';
import type { AttributionResponse, AttributionCandidate } from '../../types/attribution';
import type { CaseItem } from '../../types/case';

interface VaspAttributionBannerProps {
  attribution: AttributionResponse | null;
  loading?: boolean;
  onNavigateToEvidence?: () => void;
  onNavigateToGraph?: (address?: string) => void;
  onOpenReportModal?: () => void;
  executionMode?: 'DEMO' | 'LIVE' | string;
  caseData?: CaseItem | null;
}

export const VaspAttributionBanner: React.FC<VaspAttributionBannerProps> = ({
  attribution,
  loading = false,
  onNavigateToEvidence,
  onNavigateToGraph,
  onOpenReportModal,
  executionMode = 'DEMO',
}) => {
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [selectedCandidateIndex, setSelectedCandidateIndex] = useState<number>(0);

  const copyToClipboard = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  if (loading) {
    return (
      <div className="p-12 text-center text-surface-500 text-sm flex flex-col items-center justify-center gap-3">
        <div className="h-6 w-6 border-2 border-brand-blue border-t-transparent rounded-full animate-spin" />
        <span>Evaluating multi-factor attribution heuristics from on-chain telemetry...</span>
      </div>
    );
  }

  const candidates = attribution?.candidates || [];
  const primaryCandidate: AttributionCandidate | null = 
    candidates[selectedCandidateIndex] || attribution?.best_candidate || candidates[0] || null;

  if (!attribution || !primaryCandidate) {
    return (
      <div className="rounded-xl border border-surface-200 dark:border-surface-300 bg-surface-default dark:bg-surface-100 p-8 text-center shadow-xs">
        <div className="mx-auto w-12 h-12 rounded-full bg-surface-100 dark:bg-surface-200 flex items-center justify-center text-surface-400 dark:text-surface-500 mb-3">
          <Building2 className="h-6 w-6" />
        </div>
        <h3 className="text-base font-bold text-surface-800 dark:text-surface-100 mb-1">
          Attribution Finding: No Attributed VASP Candidate Identified
        </h3>
        <p className="text-xs sm:text-sm text-surface-500 max-w-lg mx-auto mb-4">
          The forensic attribution engine has not identified any clustered exchange deposit addresses or tagged entities meeting the attribution threshold for this trace.
        </p>
        {onNavigateToGraph && (
          <button
            onClick={() => onNavigateToGraph()}
            className="px-4 py-2 rounded-lg bg-brand-blue hover:bg-brand-hover text-white text-xs font-bold transition shadow-xs cursor-pointer inline-flex items-center gap-1.5"
          >
            <Network className="h-3.5 w-3.5" />
            <span>Inspect Trace Graph</span>
          </button>
        )}
      </div>
    );
  }

  const best = primaryCandidate;
  const vaspName = best.vasp_name || best.vasp || 'UNSPECIFIED VASP';
  const confidenceScore = `${best.confidence_percentage.toFixed(1)}%`;
  const confidenceBand = best.confidence_band || 'HIGH';
  const hypothesisLabel = best.hypothesis_label || 'Investigative Hypothesis (Pending Officer Review)';
  const candidateWallet = best.candidate_address;

  // Dynamic factor calculations matching backend AttributionEngine
  const fDirect = best.factors?.direct_tag ?? 0.0;
  const fDownstream = best.factors?.downstream_vasp_match ?? 0.0;
  const fEffectiveTag = fDirect > 0 ? fDirect : 0.80 * fDownstream;
  const fSweep = best.factors?.sweep ?? 0.0;
  const fFanIn = best.factors?.fan_in ?? 0.0;
  const fTemporal = best.factors?.temporal ?? 0.0;

  const wEffectiveTag = (fEffectiveTag * 0.35).toFixed(3);
  const wSweep = (fSweep * 0.35).toFixed(3);
  const wFanIn = (fFanIn * 0.15).toFixed(3);
  const wTemporal = (fTemporal * 0.15).toFixed(3);
  const totalScoreVal = best.confidence ?? (Number(wEffectiveTag) + Number(wSweep) + Number(wFanIn) + Number(wTemporal));
  const totalScorePercentage = best.confidence_percentage ? best.confidence_percentage.toFixed(1) : (totalScoreVal * 100).toFixed(1);

  const bulletPoints = best.evidence_bullet_points || [];

  const disclaimerText = attribution.disclaimer || 
    "This candidate wallet is not directly tagged. Attribution is inferred from downstream matching and behavioral factors. Requires human investigator review. Not an autonomous freeze.";

  return (
    <div className="space-y-6">
      {/* Candidate Selector Tab if multiple candidates exist */}
      {candidates.length > 1 && (
        <div className="flex items-center gap-2 pb-2 border-b border-surface-200 dark:border-surface-300 overflow-x-auto">
          <span className="text-xs font-bold text-surface-500 uppercase tracking-wider shrink-0">
            Attribution Candidates ({candidates.length}):
          </span>
          {candidates.map((c, idx) => (
            <button
              key={c.candidate_address || idx}
              onClick={() => setSelectedCandidateIndex(idx)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer shrink-0 flex items-center gap-1.5 ${
                selectedCandidateIndex === idx
                  ? 'bg-brand-blue text-white shadow-xs font-bold'
                  : 'bg-surface-100 hover:bg-surface-200 dark:bg-surface-200 dark:hover:bg-surface-300 text-surface-700 dark:text-surface-200 border border-surface-200 dark:border-surface-300'
              }`}
            >
              <span>{c.vasp_name || c.vasp}</span>
              <span className="font-mono text-[11px] opacity-85">({c.confidence_percentage.toFixed(0)}%)</span>
            </button>
          ))}
        </div>
      )}

      <div className="flex flex-col lg:flex-row gap-6">
        {/* Left Column: Finding & Evidence */}
        <div className="w-full lg:w-[60%] space-y-5">
          {/* Main Finding Card */}
          <div className="bg-surface-default dark:bg-surface-100 border border-surface-200 dark:border-surface-300 rounded-xl p-5 shadow-xs relative overflow-hidden">
            <div className="absolute top-0 left-0 w-1.5 h-full bg-brand-blue" />
            
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="h-11 w-11 rounded-lg border border-surface-200 dark:border-surface-300 bg-surface-50 dark:bg-surface-200 flex items-center justify-center shrink-0">
                  <Building2 className="h-6 w-6 text-brand-blue dark:text-blue-400" />
                </div>
                <div>
                  <h2 className="text-xl font-extrabold text-surface-800 dark:text-surface-100 uppercase tracking-tight">
                    Attribution Finding: {vaspName}
                  </h2>
                  <div className="flex flex-wrap items-center gap-2 mt-1">
                    <span className="px-2 py-0.5 rounded bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 text-xs font-bold flex items-center gap-1">
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      {confidenceScore} ({confidenceBand} Confidence)
                    </span>
                    <span className="text-xs text-surface-500 dark:text-surface-400 font-medium">
                      {hypothesisLabel}
                    </span>
                    <span className={`px-2 py-0.5 rounded text-[11px] font-mono font-bold border ${
                      executionMode === 'LIVE'
                        ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border-emerald-300 dark:border-emerald-800'
                        : 'bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 border-amber-300 dark:border-amber-800'
                    }`}>
                      {executionMode === 'LIVE' ? 'LIVE ON-CHAIN RPC' : 'DEMO REPLAY FIXTURE'}
                    </span>
                  </div>
                </div>
              </div>
            </div>
            
            {/* Candidate Target Wallet & Actions */}
            <div className="border-t border-surface-200 dark:border-surface-300 pt-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs uppercase font-bold text-surface-500 tracking-wider">
                  Target Candidate Wallet Address
                </span>
                {onNavigateToGraph && (
                  <button
                    onClick={() => onNavigateToGraph(candidateWallet)}
                    className="text-xs text-brand-blue dark:text-blue-400 hover:underline font-bold inline-flex items-center gap-1 cursor-pointer"
                  >
                    <Network className="h-3.5 w-3.5" />
                    <span>Inspect on Graph &rarr;</span>
                  </button>
                )}
              </div>

              <div className="p-2.5 rounded-lg bg-surface-50 dark:bg-surface-200/50 border border-surface-200 dark:border-surface-300 flex items-center justify-between gap-2">
                <span className="font-mono text-xs sm:text-[13px] font-bold text-surface-800 dark:text-surface-100 break-all select-all">
                  {candidateWallet}
                </span>
                <div className="flex items-center gap-1.5 shrink-0">
                  <button
                    onClick={() => copyToClipboard(candidateWallet, 'candidate-wallet')}
                    className="p-1.5 rounded hover:bg-surface-200 dark:hover:bg-surface-300 text-surface-500 transition cursor-pointer"
                    title="Copy Address"
                  >
                    {copiedKey === 'candidate-wallet' ? (
                      <Check className="h-4 w-4 text-emerald-500" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    )}
                  </button>
                  <a
                    href={`https://tronscan.org/#/address/${candidateWallet}`}
                    target="_blank"
                    rel="noreferrer"
                    className="p-1.5 rounded hover:bg-surface-200 dark:hover:bg-surface-300 text-surface-500 transition"
                    title="View on TronScan"
                  >
                    <ExternalLink className="h-4 w-4" />
                  </a>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs pt-1">
                <div className="p-2 rounded bg-surface-50 dark:bg-surface-200/40 border border-surface-200 dark:border-surface-300">
                  <span className="text-[10px] text-surface-500 uppercase block font-medium">Clustered VASP ID</span>
                  <span className="font-mono font-bold text-surface-800 dark:text-surface-200">
                    {best.vasp_id || best.vasp}
                  </span>
                </div>
                <div className="p-2 rounded bg-surface-50 dark:bg-surface-200/40 border border-surface-200 dark:border-surface-300">
                  <span className="text-[10px] text-surface-500 uppercase block font-medium">Verification Status</span>
                  <span className="font-mono font-bold text-surface-800 dark:text-surface-200">
                    {best.verification_status || 'HEURISTIC'}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Statutory Disclaimer */}
          <div className="bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800/60 rounded-xl p-4 flex gap-3 shadow-xs">
            <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
            <div className="text-xs text-amber-800 dark:text-amber-300 leading-relaxed font-normal">
              <span className="font-bold block mb-0.5">Section 63 BSA & Statutory Intelligence Disclaimer:</span>
              {disclaimerText}
            </div>
          </div>

          {/* Forensic Evidence Observations */}
          <div className="bg-surface-default dark:bg-surface-100 border border-surface-200 dark:border-surface-300 rounded-xl p-5 shadow-xs space-y-3">
            <h3 className="text-sm font-bold text-surface-800 dark:text-surface-100 uppercase tracking-wider flex items-center gap-2">
              <ListChecks className="h-4 w-4 text-brand-blue dark:text-blue-400" />
              <span>Forensic Evidence Observations ({bulletPoints.length})</span>
            </h3>
            {bulletPoints.length > 0 ? (
              <div className="space-y-2.5">
                {bulletPoints.map((point, idx) => (
                  <div key={idx} className="flex gap-2.5 items-start p-2.5 rounded-lg bg-surface-50 dark:bg-surface-200/40 border border-surface-200 dark:border-surface-300 text-xs">
                    <span className="px-1.5 py-0.5 rounded bg-surface-200 dark:bg-surface-300 text-surface-700 dark:text-surface-200 font-bold text-[10px] uppercase shrink-0">
                      SIG {idx + 1}
                    </span>
                    <p className="text-surface-700 dark:text-surface-200 leading-relaxed font-normal">
                      {point.replace(/^[✓•\s]+/, '')}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-surface-500 italic">
                No explicit evidence observation bullets returned for this candidate.
              </p>
            )}
          </div>

          {/* Action Bar */}
          <div className="flex flex-wrap items-center gap-3 pt-1">
            {onNavigateToGraph && (
              <button 
                onClick={() => onNavigateToGraph(candidateWallet)} 
                className="px-3.5 py-2 rounded-lg bg-surface-100 hover:bg-surface-200 dark:bg-surface-200 dark:hover:bg-surface-300 text-surface-800 dark:text-surface-100 text-xs font-bold transition border border-surface-200 dark:border-surface-300 flex items-center gap-1.5 cursor-pointer shadow-xs"
              >
                <Network className="h-3.5 w-3.5 text-brand-blue dark:text-blue-400" />
                <span>View on Graph</span>
              </button>
            )}

            {onNavigateToEvidence && (
              <button 
                onClick={onNavigateToEvidence}
                className="px-3.5 py-2 rounded-lg bg-surface-100 hover:bg-surface-200 dark:bg-surface-200 dark:hover:bg-surface-300 text-surface-800 dark:text-surface-100 text-xs font-bold transition border border-surface-200 dark:border-surface-300 flex items-center gap-1.5 cursor-pointer shadow-xs"
              >
                <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" />
                <span>Evidence Vault</span>
              </button>
            )}

            {onOpenReportModal && (
              <button 
                onClick={onOpenReportModal} 
                className="ml-auto flex items-center gap-1.5 px-4 py-2 rounded-lg bg-brand-blue hover:bg-brand-hover text-white text-xs font-bold transition shadow-xs cursor-pointer"
              >
                <FileText className="h-3.5 w-3.5" />
                <span>Draft Section 94 Production Notice</span>
              </button>
            )}
          </div>
        </div>

        {/* Right Column: Scoring Breakdown & Factor Explanations */}
        <div className="w-full lg:w-[40%] space-y-5">
          {/* Scoring Breakdown Card */}
          <div className="bg-surface-default dark:bg-surface-100 border border-surface-200 dark:border-surface-300 rounded-xl p-5 shadow-xs space-y-4">
            <h3 className="text-sm font-bold text-surface-800 dark:text-surface-100 uppercase tracking-wider">
              Confidence Scoring Breakdown
            </h3>
            
            <div className="bg-surface-50 dark:bg-surface-200/50 border border-surface-200 dark:border-surface-300 rounded-lg p-2.5 font-mono text-[11px] text-surface-600 dark:text-surface-300 overflow-x-auto space-y-1">
              <div>CS = 0.35 × tag + 0.35 × sweep + 0.15 × fan_in + 0.15 × temporal</div>
              <div className="text-surface-400 dark:text-surface-500">tag = direct_tag ? direct_tag : 0.80 × downstream</div>
            </div>

            <div className="space-y-2.5 font-mono text-xs text-surface-700 dark:text-surface-200">
              <div className="flex justify-between items-center py-1 border-b border-surface-100 dark:border-surface-200">
                <span className="text-surface-500">Downstream &rarr; Tag ({fEffectiveTag.toFixed(2)})</span>
                <span className="font-bold text-surface-800 dark:text-surface-100">{fEffectiveTag.toFixed(2)} × 0.35 = +{wEffectiveTag}</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-surface-100 dark:border-surface-200">
                <span className="text-surface-500">Sweep Consolidation ({fSweep.toFixed(2)})</span>
                <span className="font-bold text-surface-800 dark:text-surface-100">{fSweep.toFixed(2)} × 0.35 = +{wSweep}</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-surface-100 dark:border-surface-200">
                <span className="text-surface-500">Fan-In Aggregation ({fFanIn.toFixed(2)})</span>
                <span className="font-bold text-surface-800 dark:text-surface-100">{fFanIn.toFixed(2)} × 0.15 = +{wFanIn}</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-surface-100 dark:border-surface-200">
                <span className="text-surface-500">Temporal Cadence ({fTemporal.toFixed(2)})</span>
                <span className="font-bold text-surface-800 dark:text-surface-100">{fTemporal.toFixed(2)} × 0.15 = +{wTemporal}</span>
              </div>
              <div className="flex justify-between items-center pt-2 font-bold text-brand-blue dark:text-blue-400 text-sm">
                <span>TOTAL CONFIDENCE</span>
                <span>= {totalScoreVal.toFixed(4)} ({totalScorePercentage}%)</span>
              </div>
            </div>

            <div className="h-2 bg-surface-200 dark:bg-surface-300 rounded-full overflow-hidden">
               <div 
                 className="h-full bg-emerald-500 rounded-full transition-all duration-500" 
                 style={{ width: `${Math.min(100, Math.max(0, parseFloat(totalScorePercentage)))}%` }} 
               />
            </div>
          </div>

          {/* Factor Explanations Card */}
          <div className="bg-surface-default dark:bg-surface-100 border border-surface-200 dark:border-surface-300 rounded-xl p-5 shadow-xs space-y-3">
            <h3 className="text-sm font-bold text-surface-800 dark:text-surface-100 uppercase tracking-wider flex items-center gap-1.5">
              <Info className="h-4 w-4 text-brand-blue dark:text-blue-400" />
              <span>Factor Explanations</span>
            </h3>
            
            <div className="space-y-2.5 text-xs">
              {best.explanations?.downstream_vasp_match && (
                <div className="p-2.5 rounded-lg bg-surface-50 dark:bg-surface-200/40 border border-surface-200 dark:border-surface-300">
                  <span className="text-[10px] text-surface-500 uppercase font-bold block mb-1">Downstream VASP Match</span>
                  <p className="text-surface-700 dark:text-surface-200 leading-relaxed font-normal">
                    {best.explanations.downstream_vasp_match}
                  </p>
                </div>
              )}

              {best.explanations?.sweep && (
                <div className="p-2.5 rounded-lg bg-surface-50 dark:bg-surface-200/40 border border-surface-200 dark:border-surface-300">
                  <span className="text-[10px] text-surface-500 uppercase font-bold block mb-1">Sweep Consolidation Behavior</span>
                  <p className="text-surface-700 dark:text-surface-200 leading-relaxed font-normal">
                    {best.explanations.sweep}
                  </p>
                </div>
              )}

              {best.explanations?.fan_in && (
                <div className="p-2.5 rounded-lg bg-surface-50 dark:bg-surface-200/40 border border-surface-200 dark:border-surface-300">
                  <span className="text-[10px] text-surface-500 uppercase font-bold block mb-1">Fan-In Topology</span>
                  <p className="text-surface-700 dark:text-surface-200 leading-relaxed font-normal">
                    {best.explanations.fan_in}
                  </p>
                </div>
              )}

              {best.explanations?.temporal && (
                <div className="p-2.5 rounded-lg bg-surface-50 dark:bg-surface-200/40 border border-surface-200 dark:border-surface-300">
                  <span className="text-[10px] text-surface-500 uppercase font-bold block mb-1">Temporal Sweep Cadence</span>
                  <p className="text-surface-700 dark:text-surface-200 leading-relaxed font-normal">
                    {best.explanations.temporal}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

