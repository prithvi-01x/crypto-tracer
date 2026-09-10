import React, { useState, useEffect } from 'react';
import {
  FileText,
  FileCheck,
  Download,
  AlertTriangle,
  RefreshCw,
  Building2,
  CheckCircle2,
  FileLock,
  Copy,
  Check,
  Network,
  ShieldCheck,
  ArrowRight
} from 'lucide-react';
import type { ReportItem } from '../../types/reports';
import type { CaseItem } from '../../types/case';
import { generateEvidenceDossier, generateBNSS94Draft, getCaseReports } from '../../api/reports';

interface ReportsViewProps {
  caseData: CaseItem | null;
  traceId?: string | null;
  onNavigateToGraph?: () => void;
  onNavigateToEvidence?: () => void;
}

export const ReportsView: React.FC<ReportsViewProps> = ({ 
  caseData, 
  traceId,
  onNavigateToGraph,
  onNavigateToEvidence
}) => {
  const [dossierStatus, setDossierStatus] = useState<'IDLE' | 'GENERATING' | 'READY'>('IDLE');
  const [draftStatus, setDraftStatus] = useState<'IDLE' | 'GENERATING' | 'READY'>('IDLE');
  const [dossierReport, setDossierReport] = useState<ReportItem | null>(null);
  const [draftReport, setDraftReport] = useState<ReportItem | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  const effectiveTraceId = traceId || caseData?.traces?.[0]?.trace_id || caseData?.traces?.[0]?.id;

  // On mount or case change, load existing reports
  useEffect(() => {
    if (!caseData?.id) return;
    async function loadReports() {
      try {
        const reports = await getCaseReports(caseData.id);
        const dossier = reports.find(r => r.report_type === 'EVIDENCE_DOSSIER');
        const draft = reports.find(r => r.report_type === 'SECTION_94_BNSS');
        if (dossier) {
          setDossierReport(dossier);
          setDossierStatus('READY');
        }
        if (draft) {
          setDraftReport(draft);
          setDraftStatus('READY');
        }
      } catch (err) {
        console.warn('Could not preload existing reports:', err);
      }
    }
    loadReports();
  }, [caseData?.id]);

  const handleGenerateDossier = async () => {
    if (!caseData?.id || !effectiveTraceId) {
      setErrorMessage("No active trace found for this case. Please run a trace first.");
      return;
    }
    setErrorMessage(null);
    setDossierStatus('GENERATING');
    try {
      const res = await generateEvidenceDossier(caseData.id, {
        trace_id: effectiveTraceId,
        investigator_name: 'IO Raman Kumar',
        investigator_rank: 'Inspector of Police (Cyber Crime)',
        police_station: 'Delhi Police Cyber Cell (IFSO)',
        include_graph_snapshot: true,
        notes: `Forensic audit record compiled under Section 63 BSA for FIR ${caseData.fir_number}.`,
      });
      setDossierReport(res);
      setDossierStatus('READY');
    } catch (err: any) {
      console.error('Evidence dossier generation failed:', err);
      setErrorMessage(err.message || 'Failed to generate Evidence Dossier');
      setDossierStatus('IDLE');
    }
  };

  const handleGenerateDraft = async () => {
    if (!caseData?.id || !effectiveTraceId) {
      setErrorMessage("No active trace found for this case. Please run a trace first.");
      return;
    }
    setErrorMessage(null);
    setDraftStatus('GENERATING');
    try {
      const res = await generateBNSS94Draft(caseData.id, {
        trace_id: effectiveTraceId,
        investigator_name: 'IO Raman Kumar',
        investigator_rank: 'Inspector of Police (Cyber Crime)',
        police_station: 'Delhi Police Cyber Cell (IFSO)',
        target_vasp: 'Binance',
        urgency_hours: 48,
        compliance_email: 'compliance-inquiry@binance.com',
        notes: `Statutory order for subscriber identification and transaction records.`,
      });
      setDraftReport(res);
      setDraftStatus('READY');
    } catch (err: any) {
      console.error('BNSS 94 draft generation failed:', err);
      setErrorMessage(err.message || 'Failed to generate Section 94 BNSS draft');
      setDraftStatus('IDLE');
    }
  };

  const handleDownload = (report: ReportItem | null, fallbackName: string) => {
    if (!report?.download_url) return;
    const a = document.createElement('a');
    a.href = report.download_url;
    a.download = report.file_name || fallbackName;
    a.target = '_blank';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(text);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  if (!caseData) {
    return (
      <div className="p-8 text-center text-surface-500 text-xs">
        No case selected. Please select a case from the register.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Notice Banner when trace is absent */}
      {!effectiveTraceId && (
        <div className="p-4 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800/60 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs">
          <div className="flex items-start gap-2.5">
            <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
            <div className="text-amber-800 dark:text-amber-300">
              <span className="font-bold block mb-0.5">Active Multi-Hop Trace Required</span>
              <span>Statutory Evidence Dossiers and Section 94 BNSS orders require on-chain multi-hop trace data.</span>
            </div>
          </div>
          {onNavigateToGraph && (
            <button
              onClick={onNavigateToGraph}
              className="px-3 py-1.5 rounded-lg bg-brand-blue hover:bg-brand-hover text-white font-bold text-xs shrink-0 cursor-pointer shadow-xs inline-flex items-center gap-1.5"
            >
              <Network className="h-3.5 w-3.5" />
              <span>Launch Trace on Graph</span>
            </button>
          )}
        </div>
      )}

      {errorMessage && (
        <div className="bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 px-4 py-3 rounded-xl text-xs flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 shrink-0 text-red-500" />
          <span>{errorMessage}</span>
        </div>
      )}

      <div className="flex flex-col lg:flex-row gap-6">
        {/* Left Column: Output Generation */}
        <div className="w-full lg:w-[58%] space-y-5">
          
          {/* Evidence Dossier Box */}
          <div className="bg-surface-default dark:bg-surface-100 border border-surface-200 dark:border-surface-300 rounded-xl p-5 shadow-xs space-y-4">
             <div className="flex items-start justify-between">
               <div className="flex items-center gap-3">
                 <div className="h-10 w-10 bg-brand-light dark:bg-brand-blue/15 rounded-lg border border-brand-blue/30 flex items-center justify-center text-brand-blue dark:text-blue-400 shrink-0">
                   <FileLock className="h-5 w-5" />
                 </div>
                 <div>
                   <h3 className="text-sm font-bold text-surface-800 dark:text-surface-100 uppercase tracking-wider">
                     Complete Evidence Dossier (PDF)
                   </h3>
                   <p className="text-xs text-surface-500 dark:text-surface-400 mt-0.5">
                     Comprehensive forensic audit record under Section 63 BSA.
                   </p>
                 </div>
               </div>
               
               {dossierStatus === 'READY' && (
                 <span className="px-2 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 text-[11px] font-bold flex items-center gap-1">
                   <CheckCircle2 className="h-3.5 w-3.5" /> Ready
                 </span>
               )}
             </div>

             <div className="space-y-2.5 text-xs text-surface-700 dark:text-surface-200 bg-surface-50 dark:bg-surface-200/40 p-3.5 rounded-lg border border-surface-200 dark:border-surface-300">
               <div className="grid grid-cols-2 gap-3">
                  <div>
                    <span className="text-[10px] uppercase font-bold text-surface-500 block">Contains</span> 
                    <span>Trace DAG, Provenance Hashes</span>
                  </div>
                  <div>
                    <span className="text-[10px] uppercase font-bold text-surface-500 block">Admissibility</span> 
                    <span>Section 63 BSA Hash Chain</span>
                  </div>
               </div>
               {dossierReport && (
                 <div className="pt-2.5 border-t border-surface-200 dark:border-surface-300 font-mono text-[11px] text-surface-600 dark:text-surface-300 flex items-center justify-between">
                   <span className="truncate" title={dossierReport.content_hash}>
                     SHA-256: {dossierReport.content_hash}
                   </span>
                   <button 
                     onClick={() => copyToClipboard(dossierReport.content_hash)}
                     className="ml-2 text-surface-400 hover:text-brand-blue cursor-pointer shrink-0"
                     title="Copy hash"
                   >
                     {copiedHash === dossierReport.content_hash ? (
                       <Check className="h-3.5 w-3.5 text-emerald-600" />
                     ) : (
                       <Copy className="h-3.5 w-3.5" />
                     )}
                   </button>
                 </div>
               )}
             </div>

             <div className="flex items-center gap-2.5 pt-1">
               {dossierStatus === 'IDLE' && (
                 <button 
                   onClick={handleGenerateDossier} 
                   disabled={!effectiveTraceId}
                   className="flex-1 py-2.5 px-3 rounded-lg bg-brand-blue hover:bg-brand-hover disabled:opacity-50 text-white text-xs font-bold transition cursor-pointer shadow-xs"
                 >
                   Generate Evidence Dossier
                 </button>
               )}
               {dossierStatus === 'GENERATING' && (
                 <button disabled className="flex-1 py-2.5 px-3 rounded-lg bg-brand-light dark:bg-brand-blue/15 text-brand-blue dark:text-blue-400 text-xs font-bold flex items-center justify-center gap-2 cursor-wait">
                   <RefreshCw className="h-3.5 w-3.5 animate-spin" /> Compiling Cryptographic Proofs...
                 </button>
               )}
               {dossierStatus === 'READY' && (
                 <>
                   <button 
                     onClick={() => handleDownload(dossierReport, `Dossier_${caseData.fir_number}.pdf`)}
                     className="flex-1 py-2.5 px-3 rounded-lg bg-brand-blue hover:bg-brand-hover text-white text-xs font-bold transition flex items-center justify-center gap-2 cursor-pointer shadow-xs"
                   >
                     <Download className="h-3.5 w-3.5" /> Download PDF Dossier
                   </button>
                   <button 
                     onClick={() => setDossierStatus('IDLE')} 
                     className="px-3 py-2.5 rounded-lg border border-surface-300 dark:border-surface-300 bg-surface-default dark:bg-surface-100 hover:bg-surface-50 dark:hover:bg-surface-200 text-surface-700 dark:text-surface-200 text-xs font-semibold transition cursor-pointer"
                   >
                     Regenerate
                   </button>
                 </>
               )}
             </div>
          </div>

          {/* Section 94 BNSS Legal Draft Box */}
          <div className="bg-surface-default dark:bg-surface-100 border border-surface-200 dark:border-surface-300 rounded-xl p-5 shadow-xs space-y-4">
             <div className="flex items-start justify-between">
               <div className="flex items-center gap-3">
                 <div className="h-10 w-10 bg-amber-50 dark:bg-amber-950/40 rounded-lg border border-amber-200 dark:border-amber-800 flex items-center justify-center text-amber-600 dark:text-amber-400 shrink-0">
                   <FileText className="h-5 w-5" />
                 </div>
                 <div>
                   <h3 className="text-sm font-bold text-surface-800 dark:text-surface-100 uppercase tracking-wider">
                     Draft Section 94 BNSS Order
                   </h3>
                   <p className="text-xs text-surface-500 dark:text-surface-400 mt-0.5">
                     Record production request for attributed VASP.
                   </p>
                 </div>
               </div>
               
               {draftStatus === 'READY' && (
                 <span className="px-2 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 text-[11px] font-bold flex items-center gap-1">
                   <CheckCircle2 className="h-3.5 w-3.5" /> Ready
                 </span>
               )}
             </div>

             <div className="bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800/60 rounded-lg p-3 flex gap-2.5 text-xs text-amber-800 dark:text-amber-300">
               <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
               <p className="font-normal leading-relaxed">
                 <strong className="font-semibold">DRAFT — FOR OFFICER REVIEW:</strong> This statutory order requires review and physical/digital signature by the Investigating Officer before dispatch to VASP Legal Compliance.
               </p>
             </div>

             <div className="flex items-center gap-2.5 pt-1">
               {draftStatus === 'IDLE' && (
                 <button 
                   onClick={handleGenerateDraft} 
                   disabled={!effectiveTraceId}
                   className="flex-1 py-2.5 px-3 rounded-lg bg-brand-blue hover:bg-brand-hover disabled:opacity-50 text-white text-xs font-bold transition cursor-pointer shadow-xs"
                 >
                   Draft Section 94 BNSS Request
                 </button>
               )}
               {draftStatus === 'GENERATING' && (
                 <button disabled className="flex-1 py-2.5 px-3 rounded-lg bg-brand-light dark:bg-brand-blue/15 text-brand-blue dark:text-blue-400 text-xs font-bold flex items-center justify-center gap-2 cursor-wait">
                   <RefreshCw className="h-3.5 w-3.5 animate-spin" /> Drafting Legal Request...
                 </button>
               )}
               {draftStatus === 'READY' && (
                 <>
                   <button 
                     onClick={() => handleDownload(draftReport, `Draft_BNSS94_${caseData.fir_number}.pdf`)}
                     className="flex-1 py-2.5 px-3 rounded-lg bg-brand-blue hover:bg-brand-hover text-white text-xs font-bold transition flex items-center justify-center gap-2 cursor-pointer shadow-xs"
                   >
                     <Download className="h-3.5 w-3.5" /> Download Section 94 Notice
                   </button>
                   <button 
                     onClick={() => setDraftStatus('IDLE')} 
                     className="px-3 py-2.5 rounded-lg border border-surface-300 dark:border-surface-300 bg-surface-default dark:bg-surface-100 hover:bg-surface-50 dark:hover:bg-surface-200 text-surface-700 dark:text-surface-200 text-xs font-semibold transition cursor-pointer"
                   >
                     Re-Draft
                   </button>
                 </>
               )}
             </div>
          </div>

          {/* Quick Cross-Feature Links */}
          <div className="flex items-center gap-3 pt-2">
            {onNavigateToGraph && (
              <button
                onClick={onNavigateToGraph}
                className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-surface-100 hover:bg-surface-200 dark:bg-surface-200 dark:hover:bg-surface-300 text-surface-800 dark:text-surface-100 text-xs font-bold transition border border-surface-200 dark:border-surface-300 cursor-pointer shadow-xs"
              >
                <Network className="h-3.5 w-3.5 text-brand-blue dark:text-blue-400" />
                <span>Inspect Trace Graph</span>
              </button>
            )}
            {onNavigateToEvidence && (
              <button
                onClick={onNavigateToEvidence}
                className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-surface-100 hover:bg-surface-200 dark:bg-surface-200 dark:hover:bg-surface-300 text-surface-800 dark:text-surface-100 text-xs font-bold transition border border-surface-200 dark:border-surface-300 cursor-pointer shadow-xs"
              >
                <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" />
                <span>Evidence Vault</span>
              </button>
            )}
          </div>
        </div>

        {/* Right Column: Preview / Notice Information */}
        <div className="w-full lg:w-[42%]">
          <div className="bg-surface-default dark:bg-surface-100 border border-surface-200 dark:border-surface-300 rounded-xl flex flex-col shadow-xs max-h-[600px] overflow-hidden">
            <div className="p-3.5 border-b border-surface-200 dark:border-surface-300 bg-surface-50 dark:bg-surface-200/40 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Building2 className="h-4 w-4 text-brand-blue dark:text-blue-400" />
                <h3 className="text-xs font-bold text-surface-800 dark:text-surface-100 uppercase tracking-wider">
                  Statutory Notice Preview
                </h3>
              </div>
              <span className="text-[10px] font-mono text-surface-500">
                FIR: {caseData.fir_number}
              </span>
            </div>
            
            <div className="p-5 flex-1 overflow-y-auto font-serif text-xs text-surface-800 dark:text-surface-200 leading-relaxed bg-[#fdfdfc] dark:bg-surface-200/20 shadow-inner">
              {draftStatus === 'READY' ? (
                <div className="space-y-3.5">
                  <div className="text-center font-bold mb-4">
                    <p className="text-xs uppercase tracking-wider font-sans text-surface-900 dark:text-white">
                      ORDER UNDER SECTION 94 OF THE BHARATIYA NAGARIK SURAKSHA SANHITA, 2023
                    </p>
                    <p className="text-[10px] text-amber-700 dark:text-amber-400 mt-1 font-mono">
                      [DRAFT — FOR LAW ENFORCEMENT OFFICER REVIEW ONLY]
                    </p>
                  </div>
                  <p><strong>To:</strong><br/>The Nodal / Legal Compliance Officer<br/>BINANCE CUSTODIAL SERVICES</p>
                  <p><strong>Subject:</strong> Requisition of subscriber identity, KYC dossiers, ledger records, and counterparty metadata in connection with FIR No. <strong>{caseData?.fir_number || 'FIR-2026-DEL-CY-0812'}</strong>.</p>
                  <p>WHEREAS, it has been made to appear before the undersigned Investigating Officer that the production of electronic transaction logs and user accounts is vital for investigation of financial cyber fraud offenses.</p>
                  <p>AND WHEREAS, multi-hop blockchain tracing established an evidentiary link to deposit consolidation infrastructure operated by your exchange.</p>
                  <p>YOU ARE HEREBY REQUISITIONED under Section 94 of BNSS, 2023, to produce the requested documents within 48 hours of receipt.</p>
                  <div className="mt-4 pt-3 border-t border-surface-200 dark:border-surface-300 text-[10px] italic text-surface-500 font-mono">
                    Document ID: {draftReport?.id || 'PENDING'} &bull; Hash: {draftReport?.content_hash ? `${draftReport.content_hash.substring(0, 16)}...` : 'Generating...'}
                  </div>
                </div>
              ) : (
                <div className="flex h-48 flex-col items-center justify-center text-surface-400 font-sans p-6">
                  <FileCheck className="h-8 w-8 mb-2 opacity-25" />
                  <p className="text-center text-xs">Generate draft to preview official statutory record production notice.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

