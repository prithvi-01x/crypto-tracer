import React, { useState, useEffect } from 'react';
import { 
  ArrowLeft, 
  FileText, 
  Copy, 
  Check, 
  GitBranch,
  Play,
  Layers,
  ChevronDown,
  ChevronUp,
  Loader2,
  ShieldCheck,
  AlertTriangle
} from 'lucide-react';
import type { CaseItem } from '../../types/case';
import type { InvestigationGraph, TraceStatus, GraphNode, GraphEdge } from '../../types/graph';
import { getCaseById } from '../../api/cases';
import { getTracesByCase, getTraceGraph, startTrace } from '../../api/traces';
import { InvestigationGraphCanvas } from '../graph/InvestigationGraphCanvas';
import { TraceStatsBar } from '../graph/TraceStatsBar';
import { GraphDetailDrawer } from '../graph/GraphDetailDrawer';
import { PruningDrawer } from '../graph/PruningDrawer';
import { TraceLauncherModal } from '../graph/TraceLauncherModal';
import { EvidenceWorkstation } from '../evidence/EvidenceWorkstation';
import { ReportExportModal } from '../reports/ReportExportModal';

interface CaseDetailsViewProps {
  caseId: string;
  onBack: () => void;
}

export const CaseDetailsView: React.FC<CaseDetailsViewProps> = ({ caseId, onBack }) => {
  const [caseData, setCaseData] = useState<CaseItem | null>(null);
  const [traces, setTraces] = useState<TraceStatus[]>([]);
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const [graph, setGraph] = useState<InvestigationGraph | null>(null);

  // Selections
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null);

  // Drawers & Modals
  const [isPruningOpen, setIsPruningOpen] = useState(false);
  const [isLauncherOpen, setIsLauncherOpen] = useState(false);
  const [showCaseMetadata, setShowCaseMetadata] = useState(false);
  const [isReportModalOpen, setIsReportModalOpen] = useState(false);

  // Workstation Mode
  const [activeTab, setActiveTab] = useState<'graph' | 'evidence'>('graph');

  // Loading & Errors
  const [loading, setLoading] = useState(true);
  const [graphLoading, setGraphLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // Load Case & its Traces
  useEffect(() => {
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [caseRes, tracesRes] = await Promise.all([
          getCaseById(caseId),
          getTracesByCase(caseId),
        ]);
        setCaseData(caseRes);
        setTraces(tracesRes);

        // Auto-select the first completed trace if exists
        if (tracesRes.length > 0) {
          const defaultTrace = tracesRes.find(t => t.status === 'COMPLETED') || tracesRes[0];
          setSelectedTraceId(defaultTrace.trace_id);
        }
      } catch (err: any) {
        setError(err.message || 'Failed to load case data');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [caseId]);

  // Load Graph when selectedTraceId changes
  useEffect(() => {
    if (!selectedTraceId) {
      setGraph(null);
      return;
    }

    async function fetchGraph() {
      setGraphLoading(true);
      setSelectedNode(null);
      setSelectedEdge(null);
      try {
        const graphData = await getTraceGraph(selectedTraceId!);
        setGraph(graphData);
      } catch (err: any) {
        console.error('Error fetching graph:', err);
      } finally {
        setGraphLoading(false);
      }
    }

    fetchGraph();
  }, [selectedTraceId]);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleTraceStarted = async (newTraceId: string) => {
    try {
      const refreshedTraces = await getTracesByCase(caseId);
      setTraces(refreshedTraces);
      setSelectedTraceId(newTraceId);
    } catch (e) {
      console.error('Error refreshing traces:', e);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center p-20 space-y-3">
        <Loader2 className="h-8 w-8 text-blue-500 animate-spin" />
        <p className="text-xs text-slate-400">Loading case records & transaction graph from PostgreSQL...</p>
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

  const selectedTrace = traces.find(t => t.trace_id === selectedTraceId);

  return (
    <div className="space-y-4">
      {/* Top Breadcrumb & Workstation Bar */}
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
          <span className="text-slate-600">/</span>
          <span className="text-xs font-semibold text-blue-400 flex items-center gap-1">
            <GitBranch className="h-3.5 w-3.5" />
            Graph Workstation
          </span>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2.5">
          <button
            onClick={() => setShowCaseMetadata(!showCaseMetadata)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-police-800 hover:bg-police-700 border border-police-700 text-xs font-medium text-slate-300 transition"
          >
            <FileText className="h-3.5 w-3.5 text-amber-400" />
            <span>{showCaseMetadata ? 'Hide Case Details' : 'View Case Details'}</span>
            {showCaseMetadata ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          </button>

          <button
            onClick={() => setIsReportModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-police-800 hover:bg-police-700 border border-police-700 text-xs font-medium text-slate-300 hover:text-white transition cursor-pointer"
          >
            <FileText className="h-3.5 w-3.5 text-blue-400" />
            <span>Generate Reports & Legal Notice</span>
          </button>

          <button
            onClick={() => setIsLauncherOpen(true)}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs transition shadow-md shadow-blue-500/20 cursor-pointer"
          >
            <Play className="h-3.5 w-3.5" />
            <span>New Multi-Hop Trace</span>
          </button>
        </div>
      </div>

      {/* Collapsible Case Intake Details Panel */}
      {showCaseMetadata && (
        <div className="p-5 rounded-xl bg-police-800/90 border border-police-700/80 shadow-lg space-y-4 animate-in fade-in duration-150">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-xs">
            <div>
              <span className="text-[10px] text-slate-400 uppercase font-semibold block">FIR Number</span>
              <span className="font-bold text-white text-sm mt-0.5 block">{caseData.fir_number}</span>
            </div>
            <div>
              <span className="text-[10px] text-slate-400 uppercase font-semibold block">Complainant / Victim</span>
              <span className="font-medium text-slate-200 mt-0.5 block">{caseData.victim_reference || 'N/A'}</span>
            </div>
            <div>
              <span className="text-[10px] text-slate-400 uppercase font-semibold block">1930 Portal Ref</span>
              <span className="font-mono text-slate-200 mt-0.5 block">{caseData.ack_number || 'N/A'}</span>
            </div>
            <div>
              <span className="text-[10px] text-slate-400 uppercase font-semibold block">Reported Loss</span>
              <span className="font-bold text-emerald-400 font-mono text-sm mt-0.5 block">{formattedLoss}</span>
            </div>
          </div>

          <div className="pt-3 border-t border-police-700/60 grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <div>
              <span className="text-[10px] text-slate-400 uppercase font-semibold block mb-1">Suspect Unhosted Wallet</span>
              <div className="p-2 rounded bg-police-900 border border-police-700/70 flex items-center justify-between gap-2 font-mono text-xs text-emerald-300">
                <span className="truncate">{caseData.suspect_wallet || 'No wallet registered at intake'}</span>
                {caseData.suspect_wallet && (
                  <button
                    onClick={() => copyToClipboard(caseData.suspect_wallet!)}
                    className="p-1 text-slate-400 hover:text-white transition"
                    title="Copy Address"
                  >
                    {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                  </button>
                )}
              </div>
            </div>
            <div>
              <span className="text-[10px] text-slate-400 uppercase font-semibold block mb-1">Investigation Notes</span>
              <div className="p-2 rounded bg-police-900/80 border border-police-700/50 text-slate-300 text-[11px] leading-relaxed">
                {caseData.notes || 'No preliminary notes recorded for this FIR intake.'}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Trace Selector & Execution Status Header */}
      <div className="bg-police-800/80 border border-police-700/80 rounded-xl p-3 space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
              <Layers className="h-4 w-4 text-blue-400" />
              Active Trace Run:
            </span>

            {traces.length === 0 ? (
              <span className="text-xs text-slate-400 italic">No traces run yet for this case.</span>
            ) : (
              <select
                value={selectedTraceId || ''}
                onChange={(e) => setSelectedTraceId(e.target.value)}
                className="px-3 py-1.5 rounded-lg bg-police-900 border border-police-700 text-xs font-mono text-slate-200 focus:outline-none focus:border-blue-500"
              >
                {traces.map((t, idx) => (
                  <option key={t.trace_id} value={t.trace_id}>
                    Run #{traces.length - idx}: {t.input_value.slice(0, 8)}... (Hop {t.max_hops}, {t.node_count} nodes, {t.edge_count} edges, {t.pruned_count} pruned) - {t.status} {t.is_partial ? '[PARTIAL]' : ''}
                  </option>
                ))}
              </select>
            )}
          </div>

          {selectedTrace && (
            <div className="flex items-center gap-2 text-xs">
              <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider border ${
                selectedTrace.status === 'COMPLETED'
                  ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                  : selectedTrace.status === 'PARTIAL'
                  ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                  : selectedTrace.status === 'FAILED'
                  ? 'bg-red-500/20 text-red-300 border-red-500/30'
                  : 'bg-blue-500/20 text-blue-300 border-blue-500/30'
              }`}>
                {selectedTrace.status}
              </span>

              {selectedTrace.boundary_code && (
                <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-amber-950/60 text-amber-400 border border-amber-700/50">
                  {selectedTrace.boundary_code}
                </span>
              )}

              <span className="text-slate-400 text-[11px] ml-1">
                Executed: {selectedTrace.completed_at ? new Date(selectedTrace.completed_at).toLocaleTimeString() : 'In Progress'}
              </span>
            </div>
          )}
        </div>

        {selectedTrace && (selectedTrace.status === 'PARTIAL' || selectedTrace.boundary_code) && selectedTrace.investigator_summary && (
          <div className="text-xs bg-amber-500/10 border border-amber-500/20 rounded-lg p-2.5 text-amber-300 flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold block text-[11px] uppercase tracking-wide">
                Boundary / Partial Investigation Notice:
              </span>
              <span className="text-slate-300 text-[11px] leading-relaxed">
                {selectedTrace.investigator_summary}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Workstation Mode Switcher */}
      <div className="flex items-center gap-2 border-b border-police-800 pb-2">
        <button
          onClick={() => setActiveTab('graph')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition cursor-pointer ${
            activeTab === 'graph'
              ? 'bg-blue-600 text-white shadow-md shadow-blue-500/20'
              : 'bg-police-800/80 text-slate-300 hover:text-white hover:bg-police-700'
          }`}
        >
          <GitBranch className="h-4 w-4" />
          <span>Transaction Graph Canvas</span>
        </button>

        <button
          onClick={() => setActiveTab('evidence')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition cursor-pointer ${
            activeTab === 'evidence'
              ? 'bg-blue-600 text-white shadow-md shadow-blue-500/20'
              : 'bg-police-800/80 text-slate-300 hover:text-white hover:bg-police-700'
          }`}
        >
          <ShieldCheck className="h-4 w-4 text-emerald-400" />
          <span>Evidence & Provenance</span>
          <span className="px-1.5 py-0.2 rounded text-[10px] font-mono bg-police-950/80 text-slate-300 border border-police-750">
            Section 63 BNSS
          </span>
        </button>
      </div>

      {activeTab === 'evidence' ? (
        <EvidenceWorkstation
          caseId={caseData.id}
          traceId={selectedTraceId}
          firNumber={caseData.fir_number}
        />
      ) : (
        <>
          {/* Trace Statistics Overview Bar */}
          {graph && (
            <TraceStatsBar
              meta={graph.meta}
              onOpenPruning={() => setIsPruningOpen(true)}
              prunedCount={graph.pruned_records.length}
            />
          )}

          {/* Investigation Graph Workstation Area */}
          <div className="relative flex w-full gap-4">
            {graphLoading ? (
              <div className="flex-1 h-[600px] bg-police-950/80 border border-police-700/80 rounded-xl flex flex-col items-center justify-center space-y-3">
                <Loader2 className="h-8 w-8 text-blue-400 animate-spin" />
                <p className="text-xs text-slate-400">Rendering multi-hop transaction graph...</p>
              </div>
            ) : traces.length === 0 ? (
              <div className="flex-1 h-[520px] bg-police-950/60 border border-police-700/60 rounded-xl flex flex-col items-center justify-center p-8 text-center space-y-4">
                <div className="h-16 w-16 rounded-2xl bg-blue-600/10 border border-blue-500/30 flex items-center justify-center">
                  <GitBranch className="h-8 w-8 text-blue-400" />
                </div>
                <div className="space-y-1.5 max-w-md">
                  <h3 className="text-base font-bold text-white">No Blockchain Traces Yet</h3>
                  <p className="text-xs text-slate-400 leading-relaxed">
                    Begin tracing from suspect wallet <span className="font-mono text-emerald-300">{caseData.suspect_wallet || 'unspecified'}</span> across multi-hop TRC-20 USDT transactions to reveal intermediate hops and destination endpoints.
                  </p>
                </div>
                <button
                  onClick={() => setIsLauncherOpen(true)}
                  className="px-5 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs transition shadow-lg shadow-blue-500/20 flex items-center gap-2 cursor-pointer"
                >
                  <Play className="h-4 w-4" />
                  Initiate Multi-Hop Trace
                </button>
              </div>
            ) : (
              <>
                {/* Cytoscape Graph Canvas */}
                <InvestigationGraphCanvas
                  graph={graph}
                  selectedNode={selectedNode}
                  selectedEdge={selectedEdge}
                  onSelectNode={(node) => {
                    setSelectedNode(node);
                    setSelectedEdge(null);
                  }}
                  onSelectEdge={(edge) => {
                    setSelectedEdge(edge);
                    setSelectedNode(null);
                  }}
                />

                {/* Docked Detail Drawer */}
                {(selectedNode || selectedEdge) && (
                  <GraphDetailDrawer
                    selectedNode={selectedNode}
                    selectedEdge={selectedEdge}
                    onClose={() => {
                      setSelectedNode(null);
                      setSelectedEdge(null);
                    }}
                  />
                )}
              </>
            )}
          </div>

          {/* Forensic Pruning Drawer */}
          <PruningDrawer
            isOpen={isPruningOpen}
            onClose={() => setIsPruningOpen(false)}
            records={graph?.pruned_records || []}
            minThreshold={graph?.meta.min_relevant_usd || 1.0}
          />
        </>
      )}

      {/* Multi-Hop Trace Launcher Modal */}
      <TraceLauncherModal
        isOpen={isLauncherOpen}
        onClose={() => setIsLauncherOpen(false)}
        caseId={caseData.id}
        defaultWallet={caseData.suspect_wallet}
        onTraceStarted={handleTraceStarted}
        startTraceFn={startTrace}
      />

      {/* Forensic Report & Legal Notice Generator Modal */}
      <ReportExportModal
        isOpen={isReportModalOpen}
        onClose={() => setIsReportModalOpen(false)}
        caseId={caseData.id}
        traceId={selectedTraceId}
        firNumber={caseData.fir_number}
        suspectWallet={caseData.suspect_wallet}
      />
    </div>
  );
};
