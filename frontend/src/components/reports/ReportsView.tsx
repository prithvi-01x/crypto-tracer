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
  Check
} from 'lucide-react';
import type { ReportItem } from '../../types/reports';
import { generateEvidenceDossier, generateBNSS94Draft, getCaseReports } from '../../api/reports';

interface ReportsViewProps {
  caseData: any;
  traceId?: string | null;
}

export const ReportsView: React.FC<ReportsViewProps> = ({ caseData, traceId }) => {
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
    if (!effectiveTraceId) {
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
    if (!effectiveTraceId) {
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

  return (
    <div className="flex flex-col md:flex-row gap-6">
      
      {/* Left Column: Output Generation */}
      <div className="w-full md:w-[60%] space-y-6">
        
        {errorMessage && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded text-base flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 shrink-0 text-red-600" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Evidence Dossier Box */}
        <div className="bg-surface-default border border-surface-200 rounded p-6 shadow-sm">
           <div className="flex items-start justify-between mb-4">
             <div className="flex items-center gap-3">
               <div className="h-10 w-10 bg-brand-light rounded border border-brand-blue/30 flex items-center justify-center text-brand-blue">
                 <FileLock className="h-5 w-5" />
               </div>
               <div>
                 <h3 className="text-xl font-bold text-surface-800">Complete Evidence Dossier (PDF)</h3>
                 <p className="text-base text-surface-500 mt-0.5">Comprehensive forensic log under Section 63 BSA.</p>
               </div>
             </div>
             
             {dossierStatus === 'READY' && (
               <span className="px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 text-base font-bold flex items-center gap-1.5">
                 <CheckCircle2 className="h-4 w-4" /> Ready for Download
               </span>
             )}
           </div>

           <div className="space-y-3 mb-6 text-base text-surface-700 bg-surface-50 p-4 rounded border border-surface-200">
             <div className="grid grid-cols-2 gap-4">
                <div><span className="text-xs uppercase font-bold text-surface-500 block">Contains</span> Trace DAG, Provenance Hashes</div>
                <div><span className="text-xs uppercase font-bold text-surface-500 block">Admissibility</span> Section 63 BSA Hash Chain</div>
             </div>
             {dossierReport && (
               <div className="pt-3 border-t border-surface-200 font-mono text-xs text-surface-600 flex items-center justify-between">
                 <span className="truncate" title={dossierReport.content_hash}>
                   DOCUMENT HASH (SHA-256): {dossierReport.content_hash}
                 </span>
                 <button 
                   onClick={() => copyToClipboard(dossierReport.content_hash)}
                   className="ml-2 text-surface-400 hover:text-brand-blue shrink-0"
                   title="Copy hash"
                 >
                   {copiedHash === dossierReport.content_hash ? (
                     <Check className="h-4 w-4 text-emerald-600" />
                   ) : (
                     <Copy className="h-4 w-4" />
                   )}
                 </button>
               </div>
             )}
           </div>

           <div className="flex items-center gap-3">
             {dossierStatus === 'IDLE' && (
               <button onClick={handleGenerateDossier} className="flex-1 py-2.5 rounded bg-brand-blue hover:bg-brand-hover text-white text-lg font-bold transition">
                 Generate Evidence Dossier
               </button>
             )}
             {dossierStatus === 'GENERATING' && (
               <button disabled className="flex-1 py-2.5 rounded bg-brand-light text-brand-blue text-lg font-bold flex items-center justify-center gap-2 cursor-wait">
                 <RefreshCw className="h-4 w-4 animate-spin" /> Compiling Cryptographic Proofs...
               </button>
             )}
             {dossierStatus === 'READY' && (
               <>
                 <button 
                   onClick={() => handleDownload(dossierReport, `Dossier_${caseData.fir_number}.pdf`)}
                   className="flex-1 py-2.5 rounded bg-brand-blue hover:bg-brand-hover text-white text-lg font-bold transition flex items-center justify-center gap-2"
                 >
                   <Download className="h-4 w-4" /> Download PDF Dossier
                 </button>
                 <button onClick={() => setDossierStatus('IDLE')} className="px-4 py-2.5 rounded border border-surface-300 bg-surface-default hover:bg-surface-50 text-surface-700 text-lg font-semibold transition">
                   Regenerate
                 </button>
               </>
             )}
           </div>
        </div>

        {/* Section 94 BNSS Legal Draft Box */}
        <div className="bg-surface-default border border-surface-200 rounded p-6 shadow-sm">
           <div className="flex items-start justify-between mb-4">
             <div className="flex items-center gap-3">
               <div className="h-10 w-10 bg-amber-50 rounded border border-amber-200 flex items-center justify-center text-amber-600">
                 <FileText className="h-5 w-5" />
               </div>
               <div>
                 <h3 className="text-xl font-bold text-surface-800">Draft Section 94 BNSS Order</h3>
                 <p className="text-base text-surface-500 mt-0.5">Record production request for attributed VASP.</p>
               </div>
             </div>
             
             {draftStatus === 'READY' && (
               <span className="px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 text-base font-bold flex items-center gap-1.5">
                 <CheckCircle2 className="h-4 w-4" /> Ready for Review
               </span>
             )}
           </div>

           <div className="bg-amber-50 border border-amber-200 rounded p-3 mb-6 flex gap-3 text-base text-amber-800">
             <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
             <p className="font-medium leading-relaxed">
               DRAFT — FOR OFFICER REVIEW. This document requires final review and physical/digital signature by the Investigating Officer before dispatch to VASP Legal Compliance.
             </p>
           </div>

           <div className="flex items-center gap-3">
             {draftStatus === 'IDLE' && (
               <button onClick={handleGenerateDraft} className="flex-1 py-2.5 rounded bg-brand-blue hover:bg-brand-hover text-white text-lg font-bold transition">
                 Draft Section 94 BNSS Request
               </button>
             )}
             {draftStatus === 'GENERATING' && (
               <button disabled className="flex-1 py-2.5 rounded bg-brand-light text-brand-blue text-lg font-bold flex items-center justify-center gap-2 cursor-wait">
                 <RefreshCw className="h-4 w-4 animate-spin" /> Drafting Legal Request...
               </button>
             )}
             {draftStatus === 'READY' && (
               <>
                 <button 
                   onClick={() => handleDownload(draftReport, `Draft_BNSS94_${caseData.fir_number}.pdf`)}
                   className="flex-1 py-2.5 rounded bg-brand-blue hover:bg-brand-hover text-white text-lg font-bold transition flex items-center justify-center gap-2"
                 >
                   <Download className="h-4 w-4" /> Download Section 94 Notice
                 </button>
                 <button onClick={() => setDraftStatus('IDLE')} className="px-4 py-2.5 rounded border border-surface-300 bg-surface-default hover:bg-surface-50 text-surface-700 text-lg font-semibold transition">
                   Re-Draft
                 </button>
               </>
             )}
           </div>
        </div>

      </div>

      {/* Right Column: Preview / Notice Information */}
      <div className="w-full md:w-[40%]">
        <div className="bg-surface-default border border-surface-200 rounded flex flex-col shadow-sm h-full max-h-[calc(100vh-220px)] overflow-hidden">
          <div className="p-4 border-b border-surface-200 bg-surface-50 flex items-center gap-2">
            <Building2 className="h-4 w-4 text-surface-500" />
            <h3 className="text-lg font-bold text-surface-800">Notice Preview</h3>
          </div>
          
          <div className="p-6 flex-1 overflow-y-auto font-serif text-base text-surface-800 leading-relaxed bg-[#fdfdfc] shadow-inner">
            {draftStatus === 'READY' ? (
              <div className="space-y-4">
                <div className="text-center font-bold mb-6">
                  <p className="text-lg uppercase tracking-wide">ORDER UNDER SECTION 94 OF THE BHARATIYA NAGARIK SURAKSHA SANHITA, 2023</p>
                  <p className="text-xs text-amber-700 mt-1">[DRAFT — FOR LAW ENFORCEMENT OFFICER REVIEW ONLY]</p>
                </div>
                <p><strong>To:</strong><br/>The Nodal / Legal Compliance Officer<br/>BINANCE CUSTODIAL SERVICES</p>
                <p><strong>Subject:</strong> Requisition of subscriber identity, KYC dossiers, ledger records, and counterparty metadata in connection with FIR No. <strong>{caseData?.fir_number || 'FIR-2026-DEL-CY-0812'}</strong>.</p>
                <p>WHEREAS, it has been made to appear before the undersigned Investigating Officer that the production of electronic transaction logs and user accounts is vital for investigation of financial cyber fraud offenses.</p>
                <p>AND WHEREAS, multi-hop blockchain tracing established an evidentiary link to deposit consolidation infrastructure operated by your exchange.</p>
                <p>YOU ARE HEREBY REQUISITIONED under Section 94 of BNSS, 2023, to produce the requested documents within 48 hours of receipt.</p>
                <div className="mt-6 pt-4 border-t border-surface-200 text-xs italic text-surface-500">
                  Document ID: {draftReport?.id || 'PENDING'} &bull; Hash: {draftReport?.content_hash ? `${draftReport.content_hash.substring(0, 16)}...` : 'Generating...'}
                </div>
              </div>
            ) : (
              <div className="flex h-full flex-col items-center justify-center text-surface-400 font-sans p-8">
                <FileCheck className="h-10 w-10 mb-3 opacity-20" />
                <p className="text-center">Generate draft to preview official statutory record production notice.</p>
              </div>
            )}
          </div>
        </div>
      </div>
      
    </div>
  );
};

