import React, { useState, useEffect, useCallback } from 'react';
import { 
  ArrowLeft, 
  Download,
  PlusCircle,
  ShieldAlert
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
import { EvidenceWorkstation } from '../evidence/EvidenceWorkstation';
import { VaspAttributionBanner } from '../graph/VaspAttributionBanner';
import { ReportsView } from '../reports/ReportsView';
import { ForensicFindingsPanel } from '../findings/ForensicFindingsPanel';

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

  return (
    <div className="min-h-screen bg-surface-50 flex flex-col">
      {/* Case Context Strip */}
      <div className="bg-surface-default border-b border-surface-200 px-6 py-3 sticky top-[61px] z-30">
        <div className="max-w-[1440px] mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-4 text-lg w-full sm:w-auto overflow-x-auto">
            <button onClick={onBack} className="text-surface-500 hover:text-brand-blue flex items-center gap-1 font-medium transition">
              <ArrowLeft className="h-4 w-4" /> Cases
            </button>
            <div className="w-px h-4 bg-surface-200" />
            
            <div className="flex items-center gap-2 whitespace-nowrap">
              <span className="font-mono text-surface-600 bg-surface-100 px-2 py-0.5 rounded text-base border border-surface-200">
                Case {caseData.id.substring(caseData.id.length - 5)}
              </span>
              <span className="font-mono font-semibold text-brand-blue">{caseData.fir_number}</span>
            </div>
            
            <div className="w-px h-4 bg-surface-200" />
            <span className="font-medium text-surface-800 whitespace-nowrap">
              {caseData.victim_reference ? caseData.victim_reference.split('(')[0].trim() : 'Ramesh Kumar'}
            </span>
            
            <div className="w-px h-4 bg-surface-200" />
            <span className="text-surface-600 truncate max-w-[180px]" title={caseData.notes || caseData.description || 'Cyber Financial Fraud'}>
              {caseData.description || 'Task-Based Scam'}
            </span>
            
            <div className="w-px h-4 bg-surface-200" />
            <span className="font-mono font-medium text-red-700 whitespace-nowrap">
              {caseData.loss_amount_inr 
                ? new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(Number(caseData.loss_amount_inr)) 
                : '₹50,00,000'}
            </span>
            
            <div className="w-px h-4 bg-surface-200" />
            <span className="font-mono font-bold text-surface-800 whitespace-nowrap">
              {caseData.loss_amount_usdt 
                ? `${Number(caseData.loss_amount_usdt).toLocaleString()} USDT` 
                : (caseData.loss_amount_inr 
                    ? `${Math.round(Number(caseData.loss_amount_inr) / 83.33).toLocaleString()} USDT` 
                    : '60,000 USDT')}
            </span>
            
            <div className="w-px h-4 bg-surface-200" />
            <span className="font-mono text-sm bg-surface-200 text-surface-700 px-2 py-0.5 rounded whitespace-nowrap">
              {caseData.chain || 'TRON'} ({caseData.asset || 'TRC-20'})
            </span>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button 
              onClick={() => setActiveTab('reports')}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded border border-surface-200 bg-surface-default hover:bg-surface-50 text-base font-semibold text-surface-700 transition"
            >
              <Download className="h-4 w-4" /> Export Trace Dossier
            </button>
            <button className="flex items-center gap-1.5 px-3 py-1.5 rounded border border-surface-200 bg-surface-default hover:bg-surface-50 text-base font-semibold text-surface-700 transition">
              <PlusCircle className="h-4 w-4" /> Add Note
            </button>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-surface-50 border-b border-surface-200 px-6">
        <div className="max-w-[1440px] mx-auto flex items-center gap-6">
          {(['graph', 'attribution', 'findings', 'evidence', 'reports'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`py-3 text-lg font-semibold border-b-2 transition-colors flex items-center gap-2 ${
                activeTab === tab 
                  ? 'border-brand-blue text-brand-blue' 
                  : 'border-transparent text-surface-500 hover:text-surface-800'
              }`}
            >
              {tab === 'graph' && 'Trace Graph'}
              {tab === 'attribution' && 'VASP Attribution'}
              {tab === 'findings' && (
                <span className="flex items-center gap-1.5">
                  Forensic Findings
                  {findings.length > 0 && (
                    <span className={`px-2 py-0.5 text-xs rounded-full font-mono font-bold ${
                      findings.some(f => f.severity === 'CRITICAL' && f.status === 'OPEN')
                        ? 'bg-red-500 text-white animate-pulse'
                        : findings.some(f => f.severity === 'HIGH' && f.status === 'OPEN')
                        ? 'bg-amber-500 text-white'
                        : 'bg-surface-200 text-surface-700'
                    }`}>
                      {findings.filter(f => f.status === 'OPEN').length || findings.length}
                    </span>
                  )}
                </span>
              )}
              {tab === 'evidence' && 'Evidence Vault'}
              {tab === 'reports' && 'Reports & Legal Draft'}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content Area */}
      <div className="flex-1 w-full max-w-[1440px] mx-auto p-4 sm:p-6 overflow-hidden flex flex-col">
        {activeTab === 'graph' && (
          <div className="flex-1 flex flex-col lg:flex-row gap-4 h-[calc(100vh-220px)] overflow-hidden">
            {/* Graph Canvas */}
            <div className="w-full lg:w-[68%] h-[55%] lg:h-full bg-surface-default border border-surface-200 rounded flex flex-col overflow-hidden shadow-sm">
              <div className="px-4 py-3 border-b border-surface-200 flex justify-between items-center bg-surface-50">
                <div className="flex items-center gap-3">
                  <h3 className="font-semibold text-lg text-surface-800">Forensic Transaction Graph</h3>
                  <span className="text-sm bg-surface-200 text-surface-700 px-2 py-0.5 rounded font-mono">TRC-20 USDT Flow &bull; Multi-Hop</span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setShowFindingsDrawer(!showFindingsDrawer)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-sm font-semibold border transition ${
                      showFindingsDrawer
                        ? 'bg-red-50 border-red-300 text-red-700'
                        : 'bg-surface-default border-surface-200 text-surface-700 hover:bg-surface-100'
                    }`}
                  >
                    <ShieldAlert className="h-4 w-4 text-red-600" />
                    Alerts
                    {findings.length > 0 && (
                      <span className="px-1.5 py-0.2 bg-red-100 text-red-800 rounded-full text-xs font-mono font-bold">
                        {findings.filter(f => f.status === 'OPEN').length}
                      </span>
                    )}
                  </button>
                </div>
              </div>
              <div className="flex-1 relative bg-surface-50">
                {graph ? (
                  <InvestigationGraphCanvas 
                    graph={graph} 
                    selectedNode={selectedNode}
                    selectedEdge={selectedEdge}
                    onSelectNode={setSelectedNode} 
                    onSelectEdge={setSelectedEdge}
                  />
                ) : (
                  <div className="flex h-full items-center justify-center text-surface-400 text-lg">
                    No active trace data available.
                  </div>
                )}
              </div>
            </div>
            {/* Detail Drawer or Findings Quick Drawer */}
            <div className="w-full lg:w-[32%] h-[45%] lg:h-full bg-surface-default border border-surface-200 rounded flex flex-col shadow-sm overflow-y-auto">
              {showFindingsDrawer ? (
                <div className="flex-1 flex flex-col overflow-hidden">
                  <div className="p-3 border-b border-surface-200 bg-surface-50 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <ShieldAlert className="h-4 w-4 text-red-600" />
                      <span className="font-semibold text-base text-surface-800">Forensic Alerts</span>
                    </div>
                    <button
                      onClick={() => setShowFindingsDrawer(false)}
                      className="text-surface-500 hover:text-surface-800 text-sm font-medium px-2 py-0.5 rounded border border-surface-200 bg-surface-default"
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
                />
              )}
            </div>
          </div>
        )}

        {activeTab === 'attribution' && (
          <div className="flex-1">
             <VaspAttributionBanner
               attribution={attribution}
               loading={false}
               onNavigateToEvidence={() => setActiveTab('evidence')}
               onOpenReportModal={() => setActiveTab('reports')}
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
      <footer className="border-t border-surface-200 bg-surface-default py-3 px-6 text-base text-surface-500 font-medium flex items-center justify-between">
        <span>Crypto-Tracer Forensic Platform &bull; Enterprise Case Workspace</span>
        <span>Session: Active &amp; Encrypted</span>
      </footer>
    </div>
  );
};
