import React, { useState, useEffect, useCallback } from 'react';
import { 
  ArrowLeft, 
  Download,
  PlusCircle,
  ShieldAlert,
  Layers,
  FileText,
  User,
  Coins
} from 'lucide-react';
import type { CaseItem } from '../../types/case';
import type { InvestigationGraph, TraceStatus, GraphNode, GraphEdge } from '../../types/graph';
import type { AttributionResponse } from '../../types/attribution';
import type { ForensicFindingItem } from '../../types/findings';
import { getCaseById } from '../../api/cases';
import { getTracesByCase, getTraceGraph, getTraceAttribution } from '../../api/traces';
import { getCaseFindings } from '../../api/findings';
import { InvestigationGraphCanvas } from '../graph/InvestigationGraphCanvas';
import { GraphDetailDrawer } from '../graph/GraphDetailDrawer';
import { TraceStatsBar } from '../graph/TraceStatsBar';
import { PruningDrawer } from '../graph/PruningDrawer';
import { EvidenceWorkstation } from '../evidence/EvidenceWorkstation';
import { VaspAttributionBanner } from '../graph/VaspAttributionBanner';
import { ReportsView } from '../reports/ReportsView';
import { ReportExportModal } from '../reports/ReportExportModal';
import { ForensicFindingsPanel } from '../findings/ForensicFindingsPanel';
import { CaseNotesModal } from './CaseNotesModal';

interface CaseDetailsViewProps {
  caseId: string;
  onBack: () => void;
}

export const CaseDetailsView: React.FC<CaseDetailsViewProps> = ({ caseId, onBack }) => {
  const [caseData, setCaseData] = useState<CaseItem | null>(null);
  const [_traces, setTraces] = useState<TraceStatus[]>([]);
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const [graph, setGraph] = useState<InvestigationGraph | null>(null);
  const [attribution, setAttribution] = useState<AttributionResponse | null>(null);
  const [findings, setFindings] = useState<ForensicFindingItem[]>([]);
  const [findingsLoading, setFindingsLoading] = useState<boolean>(false);
  const [showFindingsDrawer, setShowFindingsDrawer] = useState<boolean>(false);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(null);
  
  // Modals
  const [isNotesModalOpen, setIsNotesModalOpen] = useState<boolean>(false);
  const [isExportModalOpen, setIsExportModalOpen] = useState<boolean>(false);
  const [isPruningOpen, setIsPruningOpen] = useState<boolean>(false);

  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null);

  const [activeTab, setActiveTab] = useState<'graph' | 'attribution' | 'evidence' | 'reports' | 'findings'>('graph');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const [caseRes, tracesRes] = await Promise.all([
          getCaseById(caseId),
          getTracesByCase(caseId),
        ]);
        setCaseData(caseRes);
        setTraces(tracesRes);
        if (tracesRes.length > 0) {
          setSelectedTraceId(tracesRes[0].trace_id);
        }
      } catch (err: any) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [caseId]);

  const loadFindings = useCallback(async () => {
    setFindingsLoading(true);
    try {
      const res = await getCaseFindings(caseId);
      setFindings(res.findings);
    } catch (err) {
      console.error('Failed to load findings:', err);
    } finally {
      setFindingsLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    loadFindings();
  }, [loadFindings, selectedTraceId]);

  useEffect(() => {
    if (!selectedTraceId) return;
    async function fetchDetails() {
      try {
        const [graphRes, attrRes] = await Promise.allSettled([
          getTraceGraph(selectedTraceId!),
          getTraceAttribution(selectedTraceId!),
        ]);
        if (graphRes.status === 'fulfilled') setGraph(graphRes.value);
        if (attrRes.status === 'fulfilled') setAttribution(attrRes.value);
        loadFindings();
      } catch (err) {
        console.error(err);
      }
    }
    fetchDetails();
  }, [selectedTraceId, loadFindings]);

  const handleViewOnGraph = (addressOrId: string) => {
    setActiveTab('graph');
    setShowFindingsDrawer(false);
    if (graph && graph.nodes) {
      const node = graph.nodes.find(n => n.address === addressOrId || n.id === addressOrId);
      if (node) {
        setSelectedNode(node);
        setSelectedEdge(null);
      }
    }
  };

  const handleViewEvidence = (evidenceId: string) => {
    setSelectedEvidenceId(evidenceId);
    setActiveTab('evidence');
  };

  if (loading || !caseData) {
    return (
      <div className="flex items-center justify-center p-20">
        <p className="text-surface-500 text-lg">Loading case record...</p>
      </div>
    );
  }

  const openAlertsCount = findings.filter(f => f.status === 'OPEN').length;

  return (
    <div className="min-h-screen bg-surface-50 flex flex-col transition-colors">
      {/* Reactor Command Header */}
      <div className="bg-surface-default border-b border-surface-200 px-6 py-2.5 sticky top-[61px] z-30 shadow-xs transition-colors">
        <div className="max-w-[1440px] mx-auto flex flex-col md:flex-row items-center justify-between gap-3">
          {/* Left Metadata Strip */}
          <div className="flex items-center gap-3 text-xs w-full md:w-auto overflow-x-auto pb-1 md:pb-0">
            <button 
              onClick={onBack} 
              className="text-surface-500 hover:text-brand-blue flex items-center gap-1 font-medium transition cursor-pointer shrink-0"
              title="Return to case list"
            >
              <ArrowLeft className="h-3.5 w-3.5" /> Cases
            </button>
            <div className="w-px h-3.5 bg-surface-200 shrink-0" />
            
            {/* FIR Pill */}
            <div className="flex items-center gap-1.5 whitespace-nowrap shrink-0">
              <span className="font-mono text-surface-500 bg-surface-100 px-2 py-0.5 rounded text-[11px] border border-surface-200">
                Case {caseData.id.substring(caseData.id.length - 5)}
              </span>
              <span className="font-mono font-bold text-brand-blue dark:text-blue-400">{caseData.fir_number}</span>
            </div>
            
            <div className="w-px h-3.5 bg-surface-200 shrink-0" />

            {/* Victim Pill */}
            <div className="flex items-center gap-1 text-surface-700 dark:text-surface-300 whitespace-nowrap shrink-0">
              <User className="h-3.5 w-3.5 text-surface-400" />
              <span className="font-medium">
                {caseData.victim_reference ? caseData.victim_reference.split('(')[0].trim() : 'Ramesh Kumar'}
              </span>
            </div>
            
            <div className="w-px h-3.5 bg-surface-200 shrink-0" />

            {/* Notes preview pill */}
            <button
              onClick={() => setIsNotesModalOpen(true)}
              className="text-left text-surface-500 hover:text-brand-blue dark:hover:text-blue-400 truncate max-w-[180px] transition cursor-pointer shrink-0"
              title={caseData.notes ? `${caseData.notes}\n\n(Click to view / edit notes)` : 'No notes recorded. Click to add.'}
            >
              <span className="italic">
                {caseData.notes ? caseData.notes.split('\n')[0] : 'Task-Based Scam'}
              </span>
            </button>
            
            <div className="w-px h-3.5 bg-surface-200 shrink-0" />

            {/* Reported Loss Dual Display */}
            <div className="flex items-center gap-2 whitespace-nowrap shrink-0">
              <span className="font-mono font-semibold text-red-600 dark:text-red-400">
                {caseData.loss_amount_inr 
                  ? new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(Number(caseData.loss_amount_inr)) 
                  : '₹50,00,000'}
              </span>
              <span className="text-surface-400">/</span>
              <span className="font-mono font-bold text-surface-800 dark:text-surface-100 flex items-center gap-1">
                <Coins className="h-3 w-3 text-emerald-500" />
                {caseData.loss_amount_usdt 
                  ? `${Number(caseData.loss_amount_usdt).toLocaleString()} USDT` 
                  : (caseData.loss_amount_inr 
                      ? `${Math.round(Number(caseData.loss_amount_inr) / 83.33).toLocaleString()} USDT` 
                      : '60,000 USDT')}
              </span>
            </div>
            
            <div className="w-px h-3.5 bg-surface-200 shrink-0" />

            {/* Chain Pill */}
            <span className="font-mono text-[11px] bg-surface-100 text-surface-600 px-2 py-0.5 rounded border border-surface-200 whitespace-nowrap shrink-0">
              {caseData.chain || 'TRON'} ({caseData.asset || 'TRC-20'})
            </span>
          </div>

          {/* Right Action Buttons */}
          <div className="flex items-center gap-2 shrink-0">
            <button 
              onClick={() => setActiveTab('reports')}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-surface-200 bg-surface-default hover:bg-surface-50 text-xs font-semibold text-surface-700 dark:text-surface-200 hover:text-surface-900 dark:hover:text-white transition shadow-xs cursor-pointer"
            >
              <Download className="h-3.5 w-3.5 text-reactor-orange" />
              <span>Export Trace Dossier</span>
            </button>
            <button 
              onClick={() => setIsNotesModalOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-surface-200 bg-surface-default hover:bg-surface-50 text-xs font-semibold text-surface-700 dark:text-surface-200 hover:text-surface-900 dark:hover:text-white transition shadow-xs cursor-pointer"
            >
              <PlusCircle className="h-3.5 w-3.5 text-brand-blue dark:text-blue-400" />
              <span>Add Note</span>
            </button>
          </div>
        </div>
      </div>

      {/* Reactor Subnav Tabs with Safety Orange Active Indicator */}
      <div className="bg-surface-default border-b border-surface-200 px-6 transition-colors">
        <div className="max-w-[1440px] mx-auto flex items-center gap-6 overflow-x-auto">
          {(['graph', 'attribution', 'findings', 'evidence', 'reports'] as const).map(tab => {
            const isActive = activeTab === tab;
            return (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`py-3 text-sm font-semibold border-b-2 transition-all flex items-center gap-2 relative cursor-pointer ${
                  isActive 
                    ? 'border-reactor-orange text-reactor-orange font-bold' 
                    : 'border-transparent text-surface-500 hover:text-surface-800 dark:hover:text-surface-200'
                }`}
              >
                {tab === 'graph' && (
                  <>
                    <Layers className="h-4 w-4" />
                    <span>Trace Graph</span>
                  </>
                )}
                {tab === 'attribution' && (
                  <>
                    <Coins className="h-4 w-4" />
                    <span>VASP Attribution</span>
                  </>
                )}
                {tab === 'findings' && (
                  <>
                    <ShieldAlert className="h-4 w-4" />
                    <span>Forensic Findings</span>
                    {findings.length > 0 && (
                      <span className={`px-2 py-0.5 text-[11px] rounded-full font-mono font-bold transition ${
                        openAlertsCount > 0
                          ? 'bg-red-500 text-white'
                          : 'bg-surface-200 text-surface-700'
                      }`}>
                        {openAlertsCount}
                      </span>
                    )}
                  </>
                )}
                {tab === 'evidence' && (
                  <>
                    <ShieldAlert className="h-4 w-4" />
                    <span>Evidence Vault</span>
                  </>
                )}
                {tab === 'reports' && (
                  <>
                    <FileText className="h-4 w-4" />
                    <span>Reports &amp; Legal Draft</span>
                  </>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Tab Content Area */}
      <div className="flex-1 w-full max-w-[1440px] mx-auto p-4 sm:p-6 overflow-hidden flex flex-col">
        {activeTab === 'graph' && (
          <div className="flex-1 flex flex-col gap-3 h-[calc(100vh-200px)] overflow-hidden">
            {/* Reactor Trace Stats Strip */}
            {graph?.meta && (
              <TraceStatsBar
                meta={graph.meta}
                onOpenPruning={() => setIsPruningOpen(true)}
                prunedCount={graph.pruned_records?.length || 0}
              />
            )}

            {/* Main Graph Split Screen */}
            <div className="flex-1 flex flex-col lg:flex-row gap-3 min-h-0 overflow-hidden">
              {/* Graph Canvas Container */}
              <div className="w-full lg:w-[68%] h-[55%] lg:h-full bg-surface-default border border-surface-200 rounded-lg flex flex-col overflow-hidden shadow-xs">
                <div className="px-3.5 py-2.5 border-b border-surface-200 flex justify-between items-center bg-surface-50">
                  <div className="flex items-center gap-2.5">
                    <h3 className="font-semibold text-sm text-surface-800 dark:text-surface-100">
                      Forensic Transaction Graph
                    </h3>
                    <span className="text-[11px] bg-surface-200 text-surface-700 px-2 py-0.5 rounded font-mono">
                      TRC-20 USDT Flow &bull; Multi-Hop Directed
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setShowFindingsDrawer(!showFindingsDrawer)}
                      className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-semibold border transition cursor-pointer ${
                        showFindingsDrawer
                          ? 'bg-red-500/10 border-red-500/30 text-red-600 dark:text-red-400'
                          : 'bg-surface-default border-surface-200 text-surface-600 hover:bg-surface-100'
                      }`}
                    >
                      <ShieldAlert className="h-3.5 w-3.5 text-red-500" />
                      <span>Alerts</span>
                      {openAlertsCount > 0 && (
                        <span className="px-1.5 py-0.2 bg-red-500 text-white rounded-full text-[10px] font-mono font-bold">
                          {openAlertsCount}
                        </span>
                      )}
                    </button>
                  </div>
                </div>

                <div className="flex-1 relative bg-surface-50 overflow-hidden">
                  {graph ? (
                    <InvestigationGraphCanvas 
                      graph={graph} 
                      selectedNode={selectedNode}
                      selectedEdge={selectedEdge}
                      onSelectNode={setSelectedNode} 
                      onSelectEdge={setSelectedEdge}
                    />
                  ) : (
                    <div className="flex h-full items-center justify-center text-surface-400 text-sm">
                      No active trace data available.
                    </div>
                  )}
                </div>
              </div>

              {/* Right Panel: Reactor Entity Profiler or Forensic Alerts Drawer */}
              <div className="w-full lg:w-[32%] h-[45%] lg:h-full bg-surface-default border border-surface-200 rounded-lg flex flex-col shadow-xs overflow-hidden">
                {showFindingsDrawer ? (
                  <div className="flex-1 flex flex-col overflow-hidden">
                    <div className="p-3 border-b border-surface-200 bg-surface-50 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <ShieldAlert className="h-4 w-4 text-red-600" />
                        <span className="font-semibold text-sm text-surface-800 dark:text-surface-100">Forensic Alerts</span>
                      </div>
                      <button
                        onClick={() => setShowFindingsDrawer(false)}
                        className="text-surface-500 hover:text-surface-800 text-xs font-medium px-2 py-0.5 rounded border border-surface-200 bg-surface-default cursor-pointer"
                      >
                        Close
                      </button>
                    </div>
                    <div className="flex-1 overflow-y-auto p-2">
                      <ForensicFindingsPanel
                        caseId={caseData.id}
                        traceId={selectedTraceId}
                        findings={findings}
                        loading={findingsLoading}
                        onRefresh={loadFindings}
                        onViewOnGraph={handleViewOnGraph}
                        onViewEvidence={handleViewEvidence}
                        compactMode={true}
                      />
                    </div>
                  </div>
                ) : (
                  <GraphDetailDrawer
                    selectedNode={selectedNode}
                    selectedEdge={selectedEdge}
                    onClose={() => { setSelectedNode(null); setSelectedEdge(null); }}
                    onHighlightPathToRoot={handleViewOnGraph}
                    onNavigateToReports={() => setActiveTab('reports')}
                    onNavigateToEvidence={() => setActiveTab('evidence')}
                  />
                )}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'attribution' && (
          <div className="flex-1">
             <VaspAttributionBanner
               attribution={attribution}
               loading={false}
               onNavigateToEvidence={() => setActiveTab('evidence')}
               onOpenReportModal={() => setIsExportModalOpen(true)}
               executionMode="DEMO"
               caseData={caseData}
             />
          </div>
        )}

        {activeTab === 'findings' && (
          <div className="flex-1 overflow-y-auto">
            <ForensicFindingsPanel
              caseId={caseData.id}
              traceId={selectedTraceId}
              findings={findings}
              loading={findingsLoading}
              onRefresh={loadFindings}
              onViewOnGraph={handleViewOnGraph}
              onViewEvidence={handleViewEvidence}
              compactMode={false}
            />
          </div>
        )}

        {activeTab === 'evidence' && (
          <div className="flex-1">
            <EvidenceWorkstation
              caseId={caseData.id}
              traceId={selectedTraceId}
              firNumber={caseData.fir_number}
              initialSelectedEvidenceId={selectedEvidenceId}
            />
          </div>
        )}

        {activeTab === 'reports' && (
          <div className="flex-1">
             <ReportsView caseData={caseData} traceId={selectedTraceId} />
          </div>
        )}
      </div>
      
      {/* Footer */}
      <footer className="border-t border-surface-200 bg-surface-default py-2.5 px-6 text-xs text-surface-500 font-medium flex items-center justify-between transition-colors">
        <span>Crypto-Tracer &bull; Enterprise Blockchain Forensic Intelligence Platform</span>
        <span>Cryptographic Audit Trail: Active &bull; Section 63 BSA Certified</span>
      </footer>

      {/* Case Notes Modal */}
      {caseData && (
        <CaseNotesModal
          isOpen={isNotesModalOpen}
          onClose={() => setIsNotesModalOpen(false)}
          caseData={caseData}
          onCaseUpdated={(updated) => setCaseData(updated)}
        />
      )}

      {/* Legal Report Export Modal */}
      {caseData && (
        <ReportExportModal
          isOpen={isExportModalOpen}
          onClose={() => setIsExportModalOpen(false)}
          caseId={caseData.id}
          traceId={selectedTraceId}
          firNumber={caseData.fir_number}
          suspectWallet={graph?.meta?.source_wallet}
          defaultVasp={attribution?.best_candidate?.vasp_name}
          candidateAddress={attribution?.best_candidate?.deposit_address}
        />
      )}

      {/* Pruning Audit Modal */}
      {graph?.pruned_records && (
        <PruningDrawer
          isOpen={isPruningOpen}
          onClose={() => setIsPruningOpen(false)}
          records={graph.pruned_records}
          minThreshold={graph.meta?.min_relevant_usd || 100}
        />
      )}
    </div>
  );
};
