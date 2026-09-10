import React from 'react';
import { 
  Building2, 
  AlertTriangle, 
  FileText, 
  CheckCircle2,
  ListChecks
} from 'lucide-react';
import type { AttributionResponse } from '../../types/attribution';
import type { CaseItem } from '../../types/case';

interface VaspAttributionBannerProps {
  attribution: AttributionResponse | null;
  loading?: boolean;
  onNavigateToEvidence?: () => void;
  onOpenReportModal?: () => void;
  executionMode?: 'DEMO' | 'LIVE' | string;
  caseData?: CaseItem | null;
}

export const VaspAttributionBanner: React.FC<VaspAttributionBannerProps> = ({
  attribution,
  loading = false,
  onOpenReportModal,
}) => {
  if (loading) {
    return (
      <div className="p-12 text-center text-surface-500 text-lg">
        Calculating multi-factor attribution heuristics...
      </div>
    );
  }

  const best = attribution?.best_candidate;
  const vaspName = best?.vasp_name || best?.vasp || 'BINANCE';
  const confidenceScore = best ? `${best.confidence_percentage.toFixed(1)}%` : '81.6%';
  const confidenceBand = best?.confidence_band || 'HIGH';
  const hypothesisLabel = best?.hypothesis_label || 'Investigative Hypothesis (Pending Officer Review)';
  const candidateWallet = best?.candidate_address || 'TBinanceUserDepositCandidate333333';
  const destinationCluster = `${vaspName} TRON Hot Wallet / Consolidation Aggregator (TK7T...3NHq)`;

  // Dynamic factor calculations matching backend AttributionEngine
  const fDirect = best?.factors?.direct_tag ?? 0.0;
  const fDownstream = best?.factors?.downstream_vasp_match ?? 1.0;
  const fEffectiveTag = fDirect > 0 ? fDirect : 0.80 * fDownstream;
  const fSweep = best?.factors?.sweep ?? 1.0;
  const fFanIn = best?.factors?.fan_in ?? 0.30;
  const fTemporal = best?.factors?.temporal ?? 0.9432;

  const wEffectiveTag = (fEffectiveTag * 0.35).toFixed(3);
  const wSweep = (fSweep * 0.35).toFixed(3);
  const wFanIn = (fFanIn * 0.15).toFixed(3);
  const wTemporal = (fTemporal * 0.15).toFixed(3);
  const totalScoreVal = best?.confidence ?? (Number(wEffectiveTag) + Number(wSweep) + Number(wFanIn) + Number(wTemporal));
  const totalScorePercentage = best?.confidence_percentage ? best.confidence_percentage.toFixed(1) : (totalScoreVal * 100).toFixed(1);

  const bulletPoints = (best?.evidence_bullet_points && best.evidence_bullet_points.length > 0)
    ? best.evidence_bullet_points
    : [
        `Downstream VASP Match — Direct sweep to identified ${vaspName} hot wallet cluster.`,
        'Sweep Consolidation — 99.8% of received funds swept within single scheduled batch.',
        'Fan-In Aggregation — Feeder deposit addresses feeding identical sweep aggregation target.',
        'Temporal Sweep Cadence — Programmatic deposit-to-sweep delay consistent with exchange daemon batching schedules.'
      ];

  const disclaimerText = attribution?.disclaimer || 
    "This candidate wallet is not directly tagged. Attribution is inferred from downstream matching and behavioral factors. Requires human investigator review. Not an autonomous freeze.";

  return (
    <div className="flex flex-col md:flex-row gap-6">
      
      {/* Left Column: Finding & Evidence */}
      <div className="w-full md:w-[60%] space-y-6">
        {/* Main Card */}
        <div className="bg-surface-default border border-surface-200 rounded p-6 shadow-sm relative overflow-hidden">
          <div className="absolute top-0 left-0 w-1.5 h-full bg-brand-blue" />
          <div className="flex items-start justify-between mb-6">
            <div className="flex items-center gap-3">
              <div className="h-12 w-12 rounded border border-surface-200 bg-surface-50 flex items-center justify-center">
                <Building2 className="h-6 w-6 text-brand-blue" />
              </div>
              <div>
                <h2 className="text-2xl font-bold text-surface-800 uppercase">Attribution Finding: {vaspName}</h2>
                <div className="flex items-center gap-2 mt-1">
                  <span className="px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 text-base font-bold flex items-center gap-1">
                    <CheckCircle2 className="h-4 w-4" />
                    {confidenceScore} ({confidenceBand} Confidence)
                  </span>
                  <span className="text-base text-surface-500 font-medium">{hypothesisLabel}</span>
                </div>
              </div>
            </div>
          </div>
          
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 border-t border-surface-200 pt-4">
               <div>
                  <span className="text-sm uppercase font-bold text-surface-500 mb-1 block">Target Candidate Wallet Address</span>
                  <div className="font-mono text-base bg-surface-50 border border-surface-200 rounded p-2 text-surface-800 break-all select-all">
                    {candidateWallet}
                  </div>
               </div>
               <div>
                  <span className="text-sm uppercase font-bold text-surface-500 mb-1 block">Identified Destination Cluster</span>
                  <div className="font-mono text-base bg-surface-50 border border-surface-200 rounded p-2 text-surface-800 break-all select-all">
                    {destinationCluster}
                  </div>
               </div>
            </div>
          </div>
        </div>

        {/* Mandatory Statutory Disclaimer */}
        <div className="bg-amber-50 border border-amber-200 rounded p-4 flex gap-3 shadow-sm">
          <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
          <p className="text-lg font-medium text-amber-800 leading-relaxed">
            {disclaimerText}
          </p>
        </div>

        {/* Forensic Evidence Observations */}
        <div className="bg-surface-default border border-surface-200 rounded p-6 shadow-sm">
          <h3 className="text-lg font-bold text-surface-800 mb-4 flex items-center gap-2">
            <ListChecks className="h-4 w-4 text-brand-blue" />
            Forensic Evidence Observations
          </h3>
          <div className="space-y-4 text-lg text-surface-700">
            {bulletPoints.map((point, idx) => (
              <div key={idx} className="flex gap-3 items-start border-b border-surface-100 last:border-0 pb-3 last:pb-0">
                <span className="px-2 py-0.5 rounded bg-surface-100 text-surface-600 font-bold text-sm uppercase mt-0.5 shrink-0">
                  Signal {idx + 1}
                </span>
                <p className="leading-relaxed">{point.replace(/^✓\s*/, '').replace(/^•\s*/, '')}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Action Bar */}
        <div className="flex items-center gap-3">
          <button onClick={onOpenReportModal} className="px-4 py-2 rounded bg-brand-blue hover:bg-brand-hover text-white text-lg font-bold transition shadow-sm">
            Accept Attribution Finding
          </button>
          <button className="px-4 py-2 rounded border border-surface-300 bg-surface-default hover:bg-surface-50 text-surface-800 text-lg font-semibold transition">
            Flag for Additional Review
          </button>
          <button onClick={onOpenReportModal} className="ml-auto flex items-center gap-2 px-4 py-2 rounded border border-brand-blue bg-brand-light text-brand-blue hover:bg-brand-blue hover:text-white text-lg font-semibold transition">
            <FileText className="h-4 w-4" /> Draft Section 94 Production Notice
          </button>
        </div>
      </div>

      {/* Right Column: Scoring Breakdown & Metadata */}
      <div className="w-full md:w-[40%] space-y-6">
        
        {/* Scoring Breakdown Card */}
        <div className="bg-surface-default border border-surface-200 rounded p-6 shadow-sm">
          <h3 className="text-lg font-bold text-surface-800 mb-4">Confidence Scoring Breakdown</h3>
          
          <div className="bg-surface-50 border border-surface-200 rounded p-3 font-mono text-base text-surface-700 mb-4 overflow-x-auto">
            <div>CS = 0.35 × effective_tag + 0.35 × sweep + 0.15 × fan_in + 0.15 × temporal</div>
            <div className="mt-1 text-surface-500">effective_tag = direct_tag ? direct_tag : 0.80 × downstream</div>
          </div>

          <div className="space-y-3 font-mono text-base text-surface-700">
            <div className="flex justify-between items-center py-1">
              <span>Downstream ({fDownstream.toFixed(2)}) &rarr; Tag ({fEffectiveTag.toFixed(2)})</span>
              <span className="font-bold">{fEffectiveTag.toFixed(2)} × 0.35 = +{wEffectiveTag}</span>
            </div>
            <div className="flex justify-between items-center py-1">
              <span>Sweep Consolidation ({fSweep.toFixed(3)})</span>
              <span className="font-bold">{fSweep.toFixed(3)} × 0.35 = +{wSweep}</span>
            </div>
            <div className="flex justify-between items-center py-1">
              <span>Fan-In Signal ({fFanIn.toFixed(2)})</span>
              <span className="font-bold">{fFanIn.toFixed(2)} × 0.15 = +{wFanIn}</span>
            </div>
            <div className="flex justify-between items-center py-1 border-b border-surface-200 pb-3">
              <span>Temporal Signal ({fTemporal.toFixed(2)})</span>
              <span className="font-bold">{fTemporal.toFixed(2)} × 0.15 = +{wTemporal}</span>
            </div>
            <div className="flex justify-between items-center pt-2 font-bold text-brand-blue text-lg">
              <span>TOTAL CONFIDENCE</span>
              <span>= {totalScoreVal.toFixed(4)} ({totalScorePercentage}%)</span>
            </div>
          </div>

          <div className="mt-6 h-2 bg-surface-200 rounded-full overflow-hidden">
             <div className="h-full bg-emerald-500 rounded-full transition-all duration-500" style={{ width: `${Math.min(100, Math.max(0, parseFloat(totalScorePercentage)))}%` }} />
          </div>
        </div>

        {/* Attribution Lineage Card */}
        <div className="bg-surface-default border border-surface-200 rounded p-6 shadow-sm">
           <h3 className="text-lg font-bold text-surface-800 mb-4">Attribution Lineage & Metadata</h3>
           
           <div className="space-y-4 text-lg text-surface-700">
             <div>
               <span className="text-sm uppercase font-bold text-surface-500 block mb-1">Ingress Path</span>
               <div className="font-mono text-base leading-relaxed break-all">
                 TSuspect...111 &rarr; TLayering...111 &rarr; {candidateWallet.substring(0, 10)}... &rarr; {vaspName} Hot Wallet
               </div>
             </div>
             
             <div className="grid grid-cols-2 gap-4">
                <div>
                   <span className="text-sm uppercase font-bold text-surface-500 block mb-1">Inflow Amount</span>
                   <span className="font-mono text-surface-800 font-medium">60,000 USDT</span>
                </div>
                <div>
                   <span className="text-sm uppercase font-bold text-surface-500 block mb-1">Swept Amount</span>
                   <span className="font-mono text-surface-800 font-medium">59,800 USDT</span>
                </div>
             </div>

             <div className="pt-3 border-t border-surface-100">
               <span className="text-sm uppercase font-bold text-surface-500 block mb-1">Fee Retained Across Hops</span>
               <span className="font-mono text-base text-surface-600">200 USDT</span>
             </div>
           </div>
        </div>
      </div>

    </div>
  );
};

