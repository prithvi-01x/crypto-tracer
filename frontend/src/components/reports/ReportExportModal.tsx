import React, { useState, useEffect } from 'react';
import {
  X,
  FileText,
  Download,
  ExternalLink,
  ShieldCheck,
  AlertTriangle,
  Copy,
  Check,
  Loader2,
  Hash,
  Scale,
  Sparkles,
  FolderOpen
} from 'lucide-react';
import type { ReportItem, ReportType } from '../../types/reports';
import {
  generateEvidenceDossier,
  generateBNSS94Draft,
  getCaseReports,
  getReportDownloadUrl,
} from '../../api/reports';

interface ReportExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  caseId: string;
  traceId: string | null;
  firNumber: string;
  suspectWallet?: string | null;
  defaultVasp?: string | null;
  candidateAddress?: string | null;
}

export const ReportExportModal: React.FC<ReportExportModalProps> = ({
  isOpen,
  onClose,
  caseId,
  traceId,
  firNumber,
  suspectWallet,
  defaultVasp,
  candidateAddress,
}) => {
  const [activeTab, setActiveTab] = useState<ReportType>('EVIDENCE_DOSSIER');
  const [existingReports, setExistingReports] = useState<ReportItem[]>([]);
  const [loadingReports, setLoadingReports] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [latestReport, setLatestReport] = useState<ReportItem | null>(null);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  // Form Fields
  const [investigatorName, setInvestigatorName] = useState('IO-Vikram-742');
  const [investigatorRank, setInvestigatorRank] = useState('Inspector of Police');
  const [policeStation, setPoliceStation] = useState('Cyber Crime Police Station, Central District');
  const [includeGraph, setIncludeGraph] = useState(true);
  const [courtJurisdiction, setCourtJurisdiction] = useState('Court of Chief Judicial Magistrate, Patiala House');
  const [urgencyHours, setUrgencyHours] = useState(48);
  const [notes, setNotes] = useState('');

  // Load existing reports
  useEffect(() => {
    if (!isOpen) return;

    async function loadReports() {
      setLoadingReports(true);
      try {
        const reports = await getCaseReports(caseId);
        setExistingReports(reports);
      } catch (e: any) {
        console.error('Failed to load existing reports:', e);
      } finally {
        setLoadingReports(false);
      }
    }

    loadReports();
  }, [isOpen, caseId]);

  if (!isOpen) return null;

  const handleCopyHash = (hash: string) => {
    navigator.clipboard.writeText(hash);
    setCopiedHash(hash);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  const handleGenerate = async () => {
    if (!traceId) {
      setError('Please select or complete a multi-hop trace before generating reports.');
      return;
    }

    setGenerating(true);
    setError(null);
    setLatestReport(null);

    try {
      let report: ReportItem;
      if (activeTab === 'EVIDENCE_DOSSIER') {
        report = await generateEvidenceDossier(caseId, {
          trace_id: traceId,
          investigator_name: investigatorName.trim(),
          investigator_rank: investigatorRank.trim(),
          police_station: policeStation.trim(),
          include_graph_snapshot: includeGraph,
          notes: notes.trim() || undefined,
        });
      } else {
        report = await generateBNSS94Draft(caseId, {
          trace_id: traceId,
          target_vasp: defaultVasp || undefined,
          candidate_address: candidateAddress || undefined,
          investigator_name: investigatorName.trim(),
          investigator_rank: investigatorRank.trim(),
          police_station: policeStation.trim(),
          court_jurisdiction: courtJurisdiction.trim(),
          urgency_hours: Number(urgencyHours) || 48,
          notes: notes.trim() || undefined,
        });
      }

      setLatestReport(report);
      setExistingReports((prev) => [report, ...prev]);
    } catch (err: any) {
      setError(err.message || 'Report generation failed');
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="w-full max-w-4xl max-h-[90vh] flex flex-col rounded-2xl bg-police-900 border border-police-700 shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-police-800 bg-police-850 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg bg-blue-500/10 border border-blue-500/30 flex items-center justify-center text-brand-blue">
              <FileText className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-bold text-white tracking-wide">Forensic Report & Legal Notice Generator</h3>
                <span className="px-2 py-0.5 rounded text-sm font-mono bg-police-800 text-surface-300 border border-police-700">
                  {firNumber}
                </span>
              </div>
              <p className="text-base text-surface-400">
                Generate Section 63 BSA Evidence Dossiers and Section 94 BNSS Notices
                {suspectWallet && <span className="font-mono text-surface-300"> | Suspect: {suspectWallet.slice(0, 10)}...</span>}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-surface-400 hover:text-white hover:bg-police-800 transition"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Report Type Selector Tabs */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Tab 1: Evidence Dossier */}
            <div
              onClick={() => setActiveTab('EVIDENCE_DOSSIER')}
              className={`p-4 rounded-xl border transition cursor-pointer flex flex-col justify-between space-y-3 ${
                activeTab === 'EVIDENCE_DOSSIER'
                  ? 'bg-blue-950/40 border-brand-blue shadow-lg shadow-blue-500/10 ring-1 ring-blue-500/50'
                  : 'bg-police-850/70 border-police-700/80 hover:border-slate-600'
              }`}
            >
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-base font-bold text-brand-blue uppercase tracking-wider">
                    <ShieldCheck className="h-4 w-4" />
                    <span>Evidence Dossier (PDF)</span>
                  </div>
                  <span className="px-2 py-0.5 rounded text-sm font-mono bg-blue-500/20 text-blue-300 border border-blue-500/30">
                    Section 63 BSA
                  </span>
                </div>
                <h4 className="text-base font-bold text-white">Admissible Electronic Evidence Package</h4>
                <p className="text-base text-surface-400 leading-relaxed">
                  Full cryptographic dossier containing transaction graph snapshot, hop-by-hop ledger,
                  sweep & temporal scoring metrics, accepted attribution hypothesis, and SHA-256 seal.
                </p>
              </div>
              <div className="text-sm text-surface-500 flex items-center gap-1 font-mono">
                <span>Output: Multi-Page Legal PDF</span>
              </div>
            </div>

            {/* Tab 2: Draft Section 94 BNSS */}
            <div
              onClick={() => setActiveTab('SECTION_94_BNSS')}
              className={`p-4 rounded-xl border transition cursor-pointer flex flex-col justify-between space-y-3 ${
                activeTab === 'SECTION_94_BNSS'
                  ? 'bg-amber-950/40 border-amber-500 shadow-lg shadow-amber-500/10 ring-1 ring-amber-500/50'
                  : 'bg-police-850/70 border-police-700/80 hover:border-slate-600'
              }`}
            >
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-base font-bold text-amber-400 uppercase tracking-wider">
                    <Scale className="h-4 w-4" />
                    <span>Draft Section 94 BNSS Notice</span>
                  </div>
                  <span className="px-2 py-0.5 rounded text-sm font-mono bg-amber-500/20 text-amber-300 border border-amber-500/30">
                    Officer Review
                  </span>
                </div>
                <h4 className="text-base font-bold text-white">Record-Production Requisition (VASP)</h4>
                <p className="text-base text-surface-400 leading-relaxed">
                  Official draft notice under Section 94 BNSS (formerly 91 CrPC) requiring target VASP
                  to furnish subscriber KYC, comprehensive account ledgers, P2P records, and IP audit trails.
                </p>
              </div>
              <div className="text-sm text-surface-500 flex items-center gap-1 font-mono">
                <span>Output: Legal Requisition Notice</span>
              </div>
            </div>
          </div>

          {/* Statutory Notice Banner */}
          {activeTab === 'SECTION_94_BNSS' && (
            <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-start gap-3 text-base text-amber-200">
              <AlertTriangle className="h-5 w-5 text-amber-400 shrink-0 mt-0.5" />
              <div className="space-y-1 leading-relaxed">
                <span className="font-bold text-amber-300">Mandatory Statutory Notice:</span>
                <p className="text-base text-amber-200/90">
                  This requisition is generated as a <strong>DRAFT FOR OFFICER REVIEW ONLY</strong>.
                  The software does not autonomously freeze exchange accounts or transmit legal notices.
                  The Investigating Officer must inspect the findings and formally sign the notice before service.
                </p>
              </div>
            </div>
          )}

          {/* Form Configuration Inputs */}
          <div className="p-4 rounded-xl bg-police-850/80 border border-police-700/80 space-y-4">
            <h4 className="text-base font-bold uppercase tracking-wider text-surface-300 flex items-center gap-1.5">
              <span>Investigating Officer & Jurisdiction Configuration</span>
            </h4>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-base">
              <div>
                <label className="text-sm text-surface-400 uppercase font-semibold block mb-1">
                  Investigating Officer (IO)
                </label>
                <input
                  type="text"
                  value={investigatorName}
                  onChange={(e) => setInvestigatorName(e.target.value)}
                  className="w-full px-3 py-1.5 rounded-lg bg-police-950 border border-police-700 text-base font-mono text-surface-200 focus:outline-none focus:border-brand-blue"
                />
              </div>

              <div>
                <label className="text-sm text-surface-400 uppercase font-semibold block mb-1">
                  Rank / Designation
                </label>
                <input
                  type="text"
                  value={investigatorRank}
                  onChange={(e) => setInvestigatorRank(e.target.value)}
                  className="w-full px-3 py-1.5 rounded-lg bg-police-950 border border-police-700 text-base text-surface-200 focus:outline-none focus:border-brand-blue"
                />
              </div>

              <div>
                <label className="text-sm text-surface-400 uppercase font-semibold block mb-1">
                  Originating Police Station
                </label>
                <input
                  type="text"
                  value={policeStation}
                  onChange={(e) => setPoliceStation(e.target.value)}
                  className="w-full px-3 py-1.5 rounded-lg bg-police-950 border border-police-700 text-base text-surface-200 focus:outline-none focus:border-brand-blue"
                />
              </div>
            </div>

            {/* Specific fields for Section 94 */}
            {activeTab === 'SECTION_94_BNSS' && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-base pt-2 border-t border-police-750">
                <div>
                  <label className="text-sm text-surface-400 uppercase font-semibold block mb-1">
                    Designated Court Jurisdiction
                  </label>
                  <input
                    type="text"
                    value={courtJurisdiction}
                    onChange={(e) => setCourtJurisdiction(e.target.value)}
                    className="w-full px-3 py-1.5 rounded-lg bg-police-950 border border-police-700 text-base text-surface-200 focus:outline-none focus:border-brand-blue"
                  />
                </div>
                <div>
                  <label className="text-sm text-surface-400 uppercase font-semibold block mb-1">
                    Response Turnaround Time (Hours)
                  </label>
                  <input
                    type="number"
                    value={urgencyHours}
                    onChange={(e) => setUrgencyHours(Number(e.target.value))}
                    className="w-full px-3 py-1.5 rounded-lg bg-police-950 border border-police-700 text-base text-surface-200 focus:outline-none focus:border-brand-blue"
                  />
                </div>
              </div>
            )}

            {/* Checkbox for Graph in Dossier */}
            {activeTab === 'EVIDENCE_DOSSIER' && (
              <div className="flex items-center gap-2 pt-2 border-t border-police-750">
                <input
                  type="checkbox"
                  id="includeGraphSnapshot"
                  checked={includeGraph}
                  onChange={(e) => setIncludeGraph(e.target.checked)}
                  className="h-4 w-4 rounded border-police-700 bg-police-950 text-brand-blue focus:ring-0 cursor-pointer"
                />
                <label htmlFor="includeGraphSnapshot" className="text-base text-surface-300 cursor-pointer">
                  Embed visual multi-hop transaction graph diagram in document
                </label>
              </div>
            )}

            {/* Optional Notes */}
            <div>
              <label className="text-sm text-surface-400 uppercase font-semibold block mb-1">
                Supplementary Case Notes / Context
              </label>
              <input
                type="text"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="E.g. Task-based phishing scam; suspect unhosted wallet identified via victim bank statement."
                className="w-full px-3 py-1.5 rounded-lg bg-police-950 border border-police-700 text-base text-surface-200 focus:outline-none focus:border-brand-blue"
              />
            </div>

            {error && (
              <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-base text-red-300">
                {error}
              </div>
            )}

            <div className="flex items-center justify-end pt-2">
              <button
                onClick={handleGenerate}
                disabled={generating}
                className="px-6 py-2.5 rounded-lg bg-brand-blue hover:bg-brand-hover text-white font-bold text-base transition shadow-lg shadow-blue-500/20 flex items-center gap-2 cursor-pointer disabled:opacity-50"
              >
                {generating ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Sparkles className="h-4 w-4" />
                )}
                <span>
                  {generating
                    ? 'Compiling ReportLab PDF...'
                    : activeTab === 'EVIDENCE_DOSSIER'
                    ? 'Generate Evidence Dossier (PDF)'
                    : 'Generate Draft Section 94 Notice (PDF)'}
                </span>
              </button>
            </div>
          </div>

          {/* Success Banner / Download Box for Freshly Generated Report */}
          {latestReport && (
            <div className="p-4 rounded-xl bg-emerald-950/40 border border-emerald-500/40 shadow-xl space-y-3 animate-in fade-in duration-200">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <div className="h-8 w-8 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
                    <Check className="h-4 w-4" />
                  </div>
                  <div>
                    <h4 className="text-base font-bold text-white">Report Successfully Generated</h4>
                    <span className="text-base font-mono text-emerald-300">{latestReport.file_name}</span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <a
                    href={getReportDownloadUrl(latestReport.id)}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-police-800 hover:bg-police-700 text-base text-surface-200 transition"
                  >
                    <ExternalLink className="h-4 w-4 text-brand-blue" />
                    <span>Open in Tab</span>
                  </a>

                  <a
                    href={getReportDownloadUrl(latestReport.id)}
                    download
                    className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-base font-bold text-white transition shadow-md shadow-emerald-500/20"
                  >
                    <Download className="h-4 w-4" />
                    <span>Download PDF</span>
                  </a>
                </div>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-emerald-800/40 text-base">
                <div className="flex items-center gap-2 text-surface-400">
                  <span>Size: <strong className="text-surface-200">{(latestReport.file_size_bytes / 1024).toFixed(1)} KB</strong></span>
                  <span>•</span>
                  <span>Generated: <strong className="text-surface-200">{new Date(latestReport.created_at).toLocaleTimeString()}</strong></span>
                </div>

                {/* SHA-256 Content Hash */}
                <div className="flex items-center gap-1.5 font-mono text-sm bg-police-950 px-2.5 py-0.5 rounded border border-police-800 text-surface-400">
                  <Hash className="h-4 w-4 text-brand-blue" />
                  <span className="truncate max-w-[200px]" title={latestReport.content_hash}>
                    {latestReport.content_hash.slice(0, 16)}...{latestReport.content_hash.slice(-8)}
                  </span>
                  <button
                    onClick={() => handleCopyHash(latestReport.content_hash)}
                    className="text-surface-400 hover:text-white transition"
                    title="Copy SHA-256 Hash"
                  >
                    {copiedHash === latestReport.content_hash ? (
                      <Check className="h-4 w-4 text-emerald-400" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    )}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Previously Generated Reports List */}
          <div className="space-y-3 pt-2">
            <div className="flex items-center justify-between">
              <h4 className="text-base font-bold uppercase tracking-wider text-surface-400 flex items-center gap-1.5">
                <FolderOpen className="h-4 w-4" />
                Previously Generated Case Reports ({existingReports.length})
              </h4>
            </div>

            {loadingReports ? (
              <div className="p-6 text-center text-base text-surface-500 flex items-center justify-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin text-brand-blue" />
                <span>Loading report history...</span>
              </div>
            ) : existingReports.length === 0 ? (
              <div className="p-8 rounded-xl bg-police-850/40 border border-police-750 text-center text-base text-surface-500">
                No PDF reports generated yet for this case. Use the panel above to generate your first document.
              </div>
            ) : (
              <div className="space-y-2">
                {existingReports.map((r) => (
                  <div
                    key={r.id}
                    className="p-3 rounded-xl bg-police-850 border border-police-700 hover:border-police-600 transition flex items-center justify-between gap-3 text-base"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-0.5 rounded-full text-sm font-semibold ${
                          r.report_type === 'EVIDENCE_DOSSIER'
                            ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                            : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                        }`}>
                          {r.report_type.replace('_', ' ')}
                        </span>
                        <span className="font-bold text-white">{r.title}</span>
                      </div>
                      <div className="flex items-center gap-3 text-base text-surface-400 font-mono">
                        <span>{r.file_name}</span>
                        <span>•</span>
                        <span>{(r.file_size_bytes / 1024).toFixed(1)} KB</span>
                        <span>•</span>
                        <span>{new Date(r.created_at).toLocaleString()}</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <a
                        href={getReportDownloadUrl(r.id)}
                        download
                        className="p-1.5 rounded-lg bg-police-800 hover:bg-police-750 text-surface-300 hover:text-white transition"
                        title="Download PDF"
                      >
                        <Download className="h-4 w-4" />
                      </a>
                      <a
                        href={getReportDownloadUrl(r.id)}
                        target="_blank"
                        rel="noreferrer"
                        className="p-1.5 rounded-lg bg-police-800 hover:bg-police-750 text-surface-300 hover:text-white transition"
                        title="Open in Tab"
                      >
                        <ExternalLink className="h-4 w-4" />
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-police-800 bg-police-950/60 flex items-center justify-between text-base text-surface-400">
          <span>All generated records include deterministic cryptographic digests under Section 63 BSA.</span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-police-800 hover:bg-police-700 text-surface-200 font-medium transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
