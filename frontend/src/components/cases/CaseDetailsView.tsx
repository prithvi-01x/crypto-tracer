import React, { useState, useEffect, useCallback, useRef } from 'react';
import { 
  ArrowLeft, 
  Download,
  PlusCircle,
  ShieldAlert,
  Layers,
  FileText,
  User,
  Coins,
  Play,
  RefreshCw,
  Zap,
  Activity,
  AlertTriangle,
  Sparkles,
  X,
  Maximize2,
  Minimize2,
  GripVertical,
  GripHorizontal,
  Sliders
} from 'lucide-react';
import type { CaseItem } from '../../types/case';
import type { InvestigationGraph, TraceStatus, GraphNode, GraphEdge } from '../../types/graph';
import type { AttributionResponse } from '../../types/attribution';
import type { ForensicFindingItem } from '../../types/findings';
import { getCaseById } from '../../api/cases';
import { getTracesByCase, getTraceGraph, getTraceAttribution, startTrace } from '../../api/traces';
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
  const [traces, setTraces] = useState<TraceStatus[]>([]);
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
  const [isRetraceModalOpen, setIsRetraceModalOpen] = useState<boolean>(false);

  // Trace Execution & Execution Mode States (P0 & P1)
  const [isTracing, setIsTracing] = useState<boolean>(false);
  const [traceStatusStage, setTraceStatusStage] = useState<'IDLE' | 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'PARTIAL' | 'FAILED'>('IDLE');
  const [traceStageText, setTraceStageText] = useState<string>('');
  const [traceError, setTraceError] = useState<string | null>(null);
  const [traceWalletInput, setTraceWalletInput] = useState<string>('');
  const [traceExecutionMode, setTraceExecutionMode] = useState<'DEMO' | 'LIVE'>('LIVE');
  const [traceHops, setTraceHops] = useState<number>(4);
  const [traceMinUsd, setTraceMinUsd] = useState<number>(1.0);

  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [isGraphMaximized, setIsGraphMaximized] = useState<boolean>(false);
  const [graphWidthPercent, setGraphWidthPercent] = useState<number>(75);
  const [isDraggingSplitter, setIsDraggingSplitter] = useState<boolean>(false);
  const splitContainerRef = useRef<HTMLDivElement>(null);

  // Drag handler for dynamic panel splitter
  const handleSplitterPointerDown = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    setIsDraggingSplitter(true);

    const onPointerMove = (moveEvent: PointerEvent) => {
      if (!splitContainerRef.current) return;
      const rect = splitContainerRef.current.getBoundingClientRect();
      const offsetX = moveEvent.clientX - rect.left;
      const totalWidth = rect.width;
      if (totalWidth <= 0) return;

      let newPercent = Math.round((offsetX / totalWidth) * 100);
      if (newPercent < 40) newPercent = 40;
      if (newPercent > 98) newPercent = 100;

      setGraphWidthPercent(newPercent);
      if (newPercent >= 100) {
        setIsGraphMaximized(true);
      } else {
        setIsGraphMaximized(false);
      }
    };

    const onPointerUp = () => {
      setIsDraggingSplitter(false);
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', onPointerUp);
    };

    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp);
  }, []);

  const [graphHeightPx, setGraphHeightPx] = useState<number | null>(null);
  const [isDraggingHeightSplitter, setIsDraggingHeightSplitter] = useState<boolean>(false);

  // Drag handler for dynamic vertical height splitter
  const handleHeightSplitterPointerDown = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    setIsDraggingHeightSplitter(true);
    const startY = e.clientY;
    const initialHeight = splitContainerRef.current?.getBoundingClientRect().height || 700;

    const onPointerMove = (moveEvent: PointerEvent) => {
      const deltaY = moveEvent.clientY - startY;
      let newHeight = Math.round(initialHeight + deltaY);
      if (newHeight < 400) newHeight = 400;
      if (newHeight > 1400) newHeight = 1400;
      setGraphHeightPx(newHeight);
    };

    const onPointerUp = () => {
      setIsDraggingHeightSplitter(false);
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', onPointerUp);
    };

    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp);
  }, []);
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
        if (caseRes.suspect_wallet) {
          setTraceWalletInput(caseRes.suspect_wallet);
        }
        if (tracesRes.length > 0) {
          setSelectedTraceId(tracesRes[0].trace_id);
        } else {
          setSelectedTraceId(null);
          setGraph(null);
          setAttribution(null);
        }
      } catch (err: any) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [caseId]);

  const handleExecuteTrace = async (overrideWallet?: string, overrideMode?: 'DEMO' | 'LIVE', overrideHops?: number) => {
    if (!caseData) return;
    const targetWallet = (overrideWallet || traceWalletInput || caseData.suspect_wallet || '').trim();
    if (!targetWallet) {
      setTraceError('Target suspect wallet address is required to execute trace.');
      return;
    }
    const mode = overrideMode || traceExecutionMode;
    const hops = overrideHops ?? traceHops;

    setIsTracing(true);
    setTraceError(null);
    setTraceStatusStage('QUEUED');
    setTraceStageText('Allocating forensic worker and initializing graph traversal pipeline...');

    const stepTimer = setTimeout(() => {
      setTraceStatusStage('RUNNING');
      setTraceStageText(
        mode === 'LIVE'
          ? 'Querying on-chain TRON node via JSON-RPC / Trongrid for TRC-20 USDT transfer logs...'
          : 'Parsing deterministic replay fixture for suspect wallet...'
      );
    }, 350);

    try {
      const result = await startTrace({
        case_id: caseData.id,
        chain: caseData.chain || 'TRON',
        input: targetWallet,
        asset: caseData.asset || 'TRC20:USDT',
        max_hops: hops,
        min_relevant_usd: traceMinUsd,
        execution_mode: mode,
      });

      clearTimeout(stepTimer);
      setTraceStatusStage((result.status as any) || 'COMPLETED');
      setTraceStageText('Compiling evidence DAG, evaluating VASP attribution & generating Section 63 hash roots...');

      // Reload traces for this case
      const updatedTraces = await getTracesByCase(caseData.id);
      setTraces(updatedTraces);
      setSelectedTraceId(result.trace_id);

      // Fetch newly generated graph & attribution
      const [graphRes, attrRes] = await Promise.allSettled([
        getTraceGraph(result.trace_id),
        getTraceAttribution(result.trace_id),
      ]);
      if (graphRes.status === 'fulfilled') setGraph(graphRes.value);
      if (attrRes.status === 'fulfilled') setAttribution(attrRes.value);
      await loadFindings();

      if (!caseData.suspect_wallet) {
        setCaseData(prev => prev ? { ...prev, suspect_wallet: targetWallet } : prev);
      }
      setIsRetraceModalOpen(false);
    } catch (err: any) {
      clearTimeout(stepTimer);
      console.error('Trace execution failed:', err);
      setTraceStatusStage('FAILED');
      setTraceError(err.message || 'Trace execution failed. Please verify TRON wallet address.');
    } finally {
      setIsTracing(false);
    }
  };

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
    setIsGraphMaximized(false);
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
      <div className="bg-surface-default border-b border-surface-200 px-4 sm:px-6 py-2 sticky top-[53px] z-30 shadow-xs transition-colors">
        <div className="w-full max-w-[96vw] 2xl:max-w-[1920px] mx-auto flex flex-col md:flex-row items-center justify-between gap-3">
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
              <span className="font-mono font-bold text-brand-blue dark:text-blue-400">
                {caseData.fir_number.toUpperCase().includes('FIR') ? caseData.fir_number : `FIR ${caseData.fir_number}`}
              </span>
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

            <div className="w-px h-3.5 bg-surface-200 shrink-0" />

            {/* Execution Mode Pill */}
            <span className={`font-mono text-[11px] px-2 py-0.5 rounded border whitespace-nowrap shrink-0 font-bold flex items-center gap-1.5 ${
              (graph?.meta?.execution_mode || (traces.find(t => t.trace_id === selectedTraceId)?.execution_mode) || 'DEMO') === 'LIVE'
                ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/30'
                : 'bg-amber-500/10 text-amber-800 dark:text-amber-300 border-amber-500/30'
            }`}>
              <span className={`h-1.5 w-1.5 rounded-full ${
                (graph?.meta?.execution_mode || (traces.find(t => t.trace_id === selectedTraceId)?.execution_mode) || 'DEMO') === 'LIVE'
                  ? 'bg-emerald-500 animate-pulse'
                  : 'bg-amber-500'
              }`} />
              {(graph?.meta?.execution_mode || (traces.find(t => t.trace_id === selectedTraceId)?.execution_mode) || 'DEMO') === 'LIVE'
                ? 'LIVE TRON RPC'
                : 'DEMO REPLAY FIXTURE'}
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
      <div className="bg-surface-default border-b border-surface-200 px-4 sm:px-6 transition-colors">
        <div className="w-full max-w-[96vw] 2xl:max-w-[1920px] mx-auto flex items-center gap-6 overflow-x-auto">
          {(['graph', 'attribution', 'findings', 'evidence', 'reports'] as const).map(tab => {
            const isActive = activeTab === tab;
            return (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`py-2 sm:py-2.5 text-xs sm:text-sm font-semibold border-b-2 transition-all flex items-center gap-2 relative cursor-pointer ${
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
      <div className="flex-1 w-full max-w-[98vw] 2xl:max-w-[2100px] mx-auto px-2 sm:px-4 py-1 sm:py-2 overflow-y-auto lg:overflow-y-auto flex flex-col">
        {activeTab === 'graph' && (
          <div 
            style={{
              height: isGraphMaximized
                ? 'calc(100vh - 130px)'
                : graphHeightPx
                  ? `${graphHeightPx}px`
                  : 'calc(100vh - 130px)',
              minHeight: '420px',
            }}
            className="flex-1 flex flex-col gap-2 overflow-hidden transition-[height] duration-150"
          >
            {/* Reactor Trace Stats Strip */}
            {graph?.meta && (
              <TraceStatsBar
                meta={graph.meta}
                onOpenPruning={() => setIsPruningOpen(true)}
                prunedCount={graph.pruned_records?.length || 0}
              />
            )}

            {/* Main Graph Split Screen */}
            <div 
              ref={splitContainerRef}
              className={`flex-1 flex flex-col lg:flex-row gap-0 min-h-0 overflow-hidden ${
                isDraggingSplitter ? 'select-none cursor-col-resize' : ''
              } ${isDraggingHeightSplitter ? 'select-none cursor-row-resize' : ''}`}
            >
              {/* Graph Canvas Container */}
              <div 
                style={{ 
                  width: isGraphMaximized || graphWidthPercent >= 100 ? '100%' : `${graphWidthPercent}%` 
                }}
                className={`h-[55%] lg:h-full bg-surface-default border border-surface-200 rounded-lg flex flex-col overflow-hidden shadow-xs ${
                  isDraggingSplitter ? 'transition-none' : 'transition-[width] duration-150'
                }`}
              >
                <div className="px-3 py-2 border-b border-surface-200 flex justify-between items-center bg-surface-50">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="font-semibold text-sm text-surface-800 dark:text-surface-100">
                      Forensic Transaction Graph
                    </h3>
                    <span className="text-[11px] bg-surface-200 text-surface-700 px-2 py-0.5 rounded font-mono">
                      TRC-20 USDT Flow &bull; Multi-Hop Directed
                    </span>
                    {graph && (
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className={`text-[11px] px-2 py-0.5 rounded font-mono font-bold border flex items-center gap-1.5 ${
                          (graph.meta?.execution_mode || (traces.find(t => t.trace_id === selectedTraceId)?.execution_mode) || 'DEMO') === 'LIVE'
                            ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/30'
                            : 'bg-amber-500/10 text-amber-800 dark:text-amber-300 border-amber-500/30'
                        }`}>
                          <span className={`h-1.5 w-1.5 rounded-full ${
                            (graph.meta?.execution_mode || (traces.find(t => t.trace_id === selectedTraceId)?.execution_mode) || 'DEMO') === 'LIVE'
                              ? 'bg-emerald-500 animate-pulse'
                              : 'bg-amber-500'
                          }`} />
                          {(graph.meta?.execution_mode || (traces.find(t => t.trace_id === selectedTraceId)?.execution_mode) || 'DEMO') === 'LIVE'
                            ? 'LIVE TRON RPC'
                            : 'DEMO REPLAY'}
                        </span>

                        {traces.find(t => t.trace_id === selectedTraceId)?.status === 'PARTIAL' && (
                          <span 
                            className="text-[11px] px-2 py-0.5 rounded font-mono font-bold border bg-amber-500/15 text-amber-800 dark:text-amber-300 border-amber-500/40 flex items-center gap-1"
                            title="Trace reached maximum hop depth or pruning threshold before terminal exchange sweep."
                          >
                            <AlertTriangle className="h-3 w-3 text-amber-600 dark:text-amber-400" />
                            PARTIAL
                          </span>
                        )}

                        {traces.find(t => t.trace_id === selectedTraceId)?.status === 'FAILED' && (
                          <div className="flex items-center gap-1">
                            <span 
                              className="text-[11px] px-2 py-0.5 rounded font-mono font-bold border bg-red-500/15 text-red-800 dark:text-red-300 border-red-500/40 flex items-center gap-1"
                              title="Previous trace execution failed. Click retry to re-execute."
                            >
                              <AlertTriangle className="h-3 w-3 text-red-600 dark:text-red-400" />
                              FAILED
                            </span>
                            <button
                              type="button"
                              onClick={() => handleExecuteTrace()}
                              className="text-[10px] px-2 py-0.5 rounded font-bold bg-red-600 hover:bg-red-700 text-white transition cursor-pointer"
                            >
                              Retry
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {/* Dynamic Canvas Width Slider Option */}
                    {graph && (
                      <div 
                        className="hidden sm:flex items-center gap-1.5 px-2 py-1 rounded text-xs font-semibold border border-surface-200 bg-surface-default text-surface-700 dark:text-surface-200 shadow-2xs"
                        title={`Adjust Canvas Width: ${isGraphMaximized ? 100 : graphWidthPercent}%`}
                      >
                        <Sliders className="h-3.5 w-3.5 text-reactor-orange" />
                        <span className="text-[10px] uppercase font-bold text-surface-500">Width</span>
                        <input
                          type="range"
                          min={40}
                          max={100}
                          step={1}
                          value={isGraphMaximized ? 100 : graphWidthPercent}
                          onChange={(e) => {
                            const val = Number(e.target.value);
                            setGraphWidthPercent(val);
                            if (val >= 100) {
                              setIsGraphMaximized(true);
                            } else {
                              setIsGraphMaximized(false);
                            }
                          }}
                          className="w-16 sm:w-20 md:w-24 h-1.5 bg-surface-200 dark:bg-surface-300 rounded-lg appearance-none cursor-pointer accent-reactor-orange"
                          aria-label="Canvas Width Slider"
                        />
                        <span className="font-mono text-[11px] font-bold text-surface-800 dark:text-surface-100 w-8 text-right">
                          {isGraphMaximized ? '100%' : `${graphWidthPercent}%`}
                        </span>
                      </div>
                    )}
                    {/* Dynamic Canvas Height Slider Option */}
                    {graph && (
                      <div 
                        className="hidden md:flex items-center gap-1.5 px-2 py-1 rounded text-xs font-semibold border border-surface-200 bg-surface-default text-surface-700 dark:text-surface-200 shadow-2xs"
                        title={`Adjust Canvas Height: ${graphHeightPx ? `${graphHeightPx}px` : 'Auto (Fit Viewport)'} • Click value to reset`}
                      >
                        <Sliders className="h-3.5 w-3.5 text-reactor-orange rotate-90" />
                        <span className="text-[10px] uppercase font-bold text-surface-500">Height</span>
                        <input
                          type="range"
                          min={450}
                          max={1200}
                          step={25}
                          value={graphHeightPx || 720}
                          onChange={(e) => {
                            setGraphHeightPx(Number(e.target.value));
                          }}
                          className="w-16 sm:w-20 md:w-24 h-1.5 bg-surface-200 dark:bg-surface-300 rounded-lg appearance-none cursor-pointer accent-reactor-orange"
                          aria-label="Canvas Height Slider"
                        />
                        <button
                          type="button"
                          onClick={() => setGraphHeightPx(null)}
                          className="font-mono text-[11px] font-bold text-surface-800 dark:text-surface-100 hover:text-reactor-orange transition cursor-pointer"
                          title="Click to reset height to Auto"
                        >
                          {graphHeightPx ? `${graphHeightPx}px` : 'Auto'}
                        </button>
                      </div>
                    )}
                    {graph && (
                      <button
                        onClick={() => {
                          if (isGraphMaximized) {
                            setIsGraphMaximized(false);
                            if (graphWidthPercent >= 100) setGraphWidthPercent(75);
                          } else {
                            setIsGraphMaximized(true);
                            setGraphWidthPercent(100);
                          }
                        }}
                        className="flex items-center gap-1 px-2 py-1 rounded text-xs font-semibold border border-surface-200 bg-surface-default hover:bg-surface-100 text-surface-700 dark:text-surface-200 transition cursor-pointer"
                        title={isGraphMaximized ? "Restore Split View" : "Maximize Graph"}
                      >
                        {isGraphMaximized ? <Minimize2 className="h-3.5 w-3.5 text-reactor-orange" /> : <Maximize2 className="h-3.5 w-3.5" />}
                        <span className="hidden sm:inline">{isGraphMaximized ? 'Split View' : 'Maximize'}</span>
                      </button>
                    )}
                    {graph && (
                      <button
                        onClick={() => setIsRetraceModalOpen(true)}
                        className="flex items-center gap-1.5 px-2 py-1 rounded text-xs font-semibold border border-surface-200 bg-surface-default hover:bg-surface-100 text-surface-700 dark:text-surface-200 transition cursor-pointer"
                        title="Re-run trace with different parameters"
                      >
                        <RefreshCw className="h-3.5 w-3.5 text-reactor-orange" />
                        <span>Re-Trace</span>
                      </button>
                    )}
                    <button
                      onClick={() => setShowFindingsDrawer(!showFindingsDrawer)}
                      className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs font-semibold border transition cursor-pointer ${
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

                <div className={`flex-1 relative bg-surface-50 ${graph ? 'p-0 overflow-hidden' : 'p-4 overflow-y-auto flex items-center justify-center'}`}>
                  {graph ? (
                    <InvestigationGraphCanvas 
                      graph={graph} 
                      selectedNode={selectedNode}
                      selectedEdge={selectedEdge}
                      onSelectNode={setSelectedNode} 
                      onSelectEdge={setSelectedEdge}
                      attribution={attribution}
                      isMaximized={isGraphMaximized}
                      onToggleMaximize={() => setIsGraphMaximized(!isGraphMaximized)}
                    />
                  ) : isTracing ? (
                    /* Active Execution Progress Screen */
                    <div className="w-full max-w-lg bg-surface-default border border-surface-200 rounded-xl p-6 shadow-md text-center space-y-5">
                      <div className="flex justify-center">
                        <div className="h-14 w-14 rounded-full bg-orange-500/10 border border-orange-500/30 flex items-center justify-center">
                          <Activity className="h-7 w-7 text-reactor-orange animate-spin" />
                        </div>
                      </div>
                      
                      <div>
                        <div className="flex items-center justify-center gap-2 mb-1.5">
                          <span className={`px-2.5 py-0.5 rounded-full text-xs font-mono font-bold tracking-wide border ${
                            traceStatusStage === 'QUEUED' 
                              ? 'bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/30' 
                              : 'bg-brand-blue/15 text-brand-blue dark:text-blue-300 border-brand-blue/30'
                          }`}>
                            STATUS: {traceStatusStage}
                          </span>
                          <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-surface-100 text-surface-600 border border-surface-200">
                            MODE: {traceExecutionMode === 'LIVE' ? 'LIVE TRON RPC' : 'DEMO FIXTURE'}
                          </span>
                        </div>
                        <h3 className="text-base font-bold text-surface-900 dark:text-white">
                          Executing Multi-Hop Graph Traversal
                        </h3>
                        <p className="text-xs text-surface-500 mt-1 font-mono break-all px-4">
                          Target: {traceWalletInput || caseData.suspect_wallet || 'Initializing...'}
                        </p>
                      </div>

                      {/* Animated Progress Bar */}
                      <div className="w-full bg-surface-200 dark:bg-surface-300 h-2 rounded-full overflow-hidden">
                        <div className="h-full bg-gradient-to-r from-reactor-orange to-brand-blue animate-pulse rounded-full w-3/4 transition-all duration-700" />
                      </div>

                      <div className="p-3 bg-surface-50 dark:bg-surface-200/40 border border-surface-200 dark:border-surface-300 rounded-lg text-xs text-surface-600 dark:text-surface-300 text-left font-mono space-y-1">
                        <div className="flex items-center gap-2 text-reactor-orange font-bold">
                          <Zap className="h-3.5 w-3.5" />
                          <span>Forensic Pipeline Progress</span>
                        </div>
                        <p className="leading-relaxed">{traceStageText}</p>
                      </div>
                    </div>
                  ) : (
                    /* Trace Launcher Card */
                    <div className="w-full max-w-xl bg-surface-default border border-surface-200 rounded-xl p-6 shadow-sm space-y-5">
                      {/* Header */}
                      <div className="flex items-start justify-between gap-3 border-b border-surface-200 pb-4">
                        <div className="flex items-center gap-3">
                          <div className="h-10 w-10 rounded-lg bg-orange-500/10 border border-orange-500/30 flex items-center justify-center text-reactor-orange shrink-0">
                            <Zap className="h-5 w-5" />
                          </div>
                          <div>
                            <h3 className="text-base font-bold text-surface-900 dark:text-white">
                              Trace Suspect Wallet
                            </h3>
                            <p className="text-xs text-surface-500">
                              Execute BFS transaction traversal across TRON ledger & compute VASP attribution
                            </p>
                          </div>
                        </div>
                        <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-surface-100 border border-surface-200 text-surface-600">
                          {caseData.chain || 'TRON'} &bull; {caseData.asset || 'TRC-20'}
                        </span>
                      </div>

                      {/* Error Alert if any */}
                      {traceError && (
                        <div className="p-3 rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 flex items-start justify-between gap-2.5 text-xs text-red-700 dark:text-red-300">
                          <div className="flex items-start gap-2.5">
                            <AlertTriangle className="h-4 w-4 text-red-500 shrink-0 mt-0.5" />
                            <div className="flex-1">
                              <span className="font-semibold block">Execution Failed</span>
                              <span className="mt-0.5 block">{traceError}</span>
                            </div>
                          </div>
                          <button
                            type="button"
                            onClick={() => handleExecuteTrace()}
                            disabled={isTracing}
                            className="px-2.5 py-1 rounded bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white font-bold text-xs shrink-0 cursor-pointer transition shadow-2xs"
                          >
                            Retry
                          </button>
                        </div>
                      )}

                      {/* Target Wallet Input */}
                      <div className="space-y-1.5">
                        <div className="flex items-center justify-between">
                          <label className="text-xs font-bold text-surface-700 dark:text-surface-300 uppercase tracking-wide">
                            Suspect Wallet Address
                          </label>
                          <button
                            type="button"
                            onClick={() => setTraceWalletInput('TSuspectScamRootWallet111111111111')}
                            className="text-[11px] font-medium text-brand-blue dark:text-blue-400 hover:underline flex items-center gap-1 cursor-pointer"
                          >
                            <Sparkles className="h-3 w-3" />
                            Use Demo Wallet
                          </button>
                        </div>
                        <input
                          type="text"
                          value={traceWalletInput}
                          onChange={(e) => setTraceWalletInput(e.target.value.trim())}
                          placeholder="e.g. TSuspectScamRootWallet111111111111"
                          className="w-full px-3 py-2 text-xs font-mono bg-surface-50 dark:bg-surface-200/50 border border-surface-200 dark:border-surface-300 rounded-lg text-surface-800 dark:text-surface-100 focus:outline-none focus:border-reactor-orange focus:ring-1 focus:ring-reactor-orange transition"
                        />
                        <p className="text-[11px] text-surface-400">
                          34-character TRON Base58Check address starting with 'T'.
                        </p>
                      </div>

                      {/* Execution Mode Selector (P1) */}
                      <div className="space-y-2">
                        <label className="text-xs font-bold text-surface-700 dark:text-surface-300 uppercase tracking-wide block">
                          Execution Engine Mode
                        </label>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                          <button
                            type="button"
                            onClick={() => setTraceExecutionMode('LIVE')}
                            className={`p-3 rounded-lg border text-left transition cursor-pointer flex flex-col justify-between ${
                              traceExecutionMode === 'LIVE'
                                ? 'border-emerald-500/60 bg-emerald-500/10 text-surface-900 dark:text-white ring-1 ring-emerald-500/40'
                                : 'border-surface-200 hover:bg-surface-50 dark:hover:bg-surface-200/40 text-surface-700'
                            }`}
                          >
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-xs font-bold flex items-center gap-1.5 text-emerald-700 dark:text-emerald-400">
                                <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                                LIVE TRON RPC
                              </span>
                              <span className="text-[10px] font-mono bg-emerald-500/20 text-emerald-800 dark:text-emerald-300 px-1.5 py-0.2 rounded font-semibold">
                                Default (Mainnet)
                              </span>
                            </div>
                            <p className="text-[11px] text-surface-500 leading-tight">
                              Live on-chain RPC queries against TRON network. Reconstructs live wallet transfers.
                            </p>
                          </button>

                          <button
                            type="button"
                            onClick={() => setTraceExecutionMode('DEMO')}
                            className={`p-3 rounded-lg border text-left transition cursor-pointer flex flex-col justify-between ${
                              traceExecutionMode === 'DEMO'
                                ? 'border-amber-500/60 bg-amber-500/10 text-surface-900 dark:text-white ring-1 ring-amber-500/40'
                                : 'border-surface-200 hover:bg-surface-50 dark:hover:bg-surface-200/40 text-surface-700'
                            }`}
                          >
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-xs font-bold flex items-center gap-1.5 text-amber-700 dark:text-amber-400">
                                <span className="h-2 w-2 rounded-full bg-amber-500" />
                                DEMO REPLAY
                              </span>
                              <span className="text-[10px] font-mono bg-amber-500/20 text-amber-800 dark:text-amber-300 px-1.5 py-0.2 rounded">
                                Courtroom Fixture
                              </span>
                            </div>
                            <p className="text-[11px] text-surface-500 leading-tight">
                              Offline deterministic dataset. 100% reproducible for judge/courtroom validation.
                            </p>
                          </button>
                        </div>
                      </div>

                      {/* Traversal Controls */}
                      <div className="grid grid-cols-2 gap-4 border-t border-surface-200 pt-3 text-xs">
                        <div>
                          <label className="font-semibold text-surface-600 dark:text-surface-300 block mb-1">
                            Traversal Depth: <span className="font-bold text-surface-900 dark:text-white">{traceHops} Hops</span>
                          </label>
                          <div className="flex items-center gap-1">
                            {[2, 3, 4, 5, 6].map(h => (
                              <button
                                key={h}
                                type="button"
                                onClick={() => setTraceHops(h)}
                                className={`flex-1 py-1 rounded text-xs font-mono font-bold transition cursor-pointer ${
                                  traceHops === h
                                    ? 'bg-reactor-orange text-white'
                                    : 'bg-surface-100 hover:bg-surface-200 text-surface-700 border border-surface-200'
                                }`}
                              >
                                {h}
                              </button>
                            ))}
                          </div>
                        </div>

                        <div>
                          <label className="font-semibold text-surface-600 dark:text-surface-300 block mb-1">
                            Min Value Filter
                          </label>
                          <div className="flex items-center gap-1">
                            {[0.0, 1.0, 10.0, 100.0].map(val => (
                              <button
                                key={val}
                                type="button"
                                onClick={() => setTraceMinUsd(val)}
                                className={`flex-1 py-1 rounded text-[11px] font-mono font-bold transition cursor-pointer ${
                                  traceMinUsd === val
                                    ? 'bg-brand-blue text-white'
                                    : 'bg-surface-100 hover:bg-surface-200 text-surface-700 border border-surface-200'
                                }`}
                              >
                                ${val}
                              </button>
                            ))}
                          </div>
                        </div>
                      </div>

                      {/* Submit Action */}
                      <button
                        type="button"
                        onClick={() => handleExecuteTrace()}
                        disabled={isTracing || !(traceWalletInput || caseData.suspect_wallet)}
                        className="w-full py-2.5 rounded-lg bg-reactor-orange hover:bg-orange-600 disabled:opacity-50 text-white text-xs font-bold flex items-center justify-center gap-2 transition shadow-sm cursor-pointer"
                      >
                        <Play className="h-4 w-4 fill-current" />
                        <span>Execute Multi-Hop Trace</span>
                      </button>
                    </div>
                  )}
                </div>
              </div>

              {/* Draggable Splitter Handle (Desktop) */}
              {!isGraphMaximized && graphWidthPercent < 100 && (
                <div
                  onPointerDown={handleSplitterPointerDown}
                  onDoubleClick={() => setGraphWidthPercent(75)}
                  className="hidden lg:flex w-2.5 items-center justify-center cursor-col-resize z-20 group relative px-0.5 hover:bg-reactor-orange/10 active:bg-reactor-orange/20 transition-colors select-none shrink-0"
                  title="Drag slider to resize graph canvas • Double-click to reset (75%)"
                  aria-label="Resize Graph Canvas Splitter"
                >
                  <div className="w-1 h-14 rounded-full bg-surface-300 dark:bg-surface-400 group-hover:bg-reactor-orange group-active:bg-reactor-orange transition-colors flex items-center justify-center">
                    <GripVertical className="h-3.5 w-3.5 text-surface-600 dark:text-surface-200 opacity-40 group-hover:opacity-100 transition-opacity" />
                  </div>
                </div>
              )}

              {/* Right Panel: Reactor Entity Profiler or Forensic Alerts Drawer */}
              <div 
                style={{ 
                  width: isGraphMaximized || graphWidthPercent >= 100 ? '0%' : `${100 - graphWidthPercent}%` 
                }}
                className={`${
                  isGraphMaximized || graphWidthPercent >= 100 ? 'hidden' : 'flex'
                } h-[45%] lg:h-full bg-surface-default border border-surface-200 rounded-lg flex-col shadow-xs overflow-hidden ${
                  isDraggingSplitter ? 'transition-none' : 'transition-[width] duration-150'
                }`}
              >
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
                    onNavigateToFinding={() => setActiveTab('findings')}
                    onSelectNodeByAddress={handleViewOnGraph}
                    attribution={attribution}
                    findings={findings}
                    graph={graph}
                  />
                )}
              </div>
            </div>

            {/* Draggable Bottom Height Handle */}
            {!isGraphMaximized && (
              <div
                onPointerDown={handleHeightSplitterPointerDown}
                onDoubleClick={() => setGraphHeightPx(null)}
                className="w-full h-2.5 flex items-center justify-center cursor-row-resize z-20 group relative hover:bg-reactor-orange/10 active:bg-reactor-orange/20 transition-colors select-none shrink-0"
                title="Drag up/down to adjust canvas height • Double-click to reset (Auto)"
                aria-label="Resize Graph Canvas Height Splitter"
              >
                <div className="h-1 w-20 rounded-full bg-surface-300 dark:bg-surface-400 group-hover:bg-reactor-orange group-active:bg-reactor-orange transition-colors flex items-center justify-center">
                  <GripHorizontal className="h-3 w-3 text-surface-600 dark:text-surface-200 opacity-40 group-hover:opacity-100 transition-opacity" />
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'attribution' && (
          <div className="flex-1">
             <VaspAttributionBanner
               attribution={attribution}
               loading={false}
               onNavigateToEvidence={() => setActiveTab('evidence')}
               onNavigateToGraph={handleViewOnGraph}
               onOpenReportModal={() => setIsExportModalOpen(true)}
               executionMode={graph?.meta?.execution_mode || (traces.find(t => t.trace_id === selectedTraceId)?.execution_mode) || 'DEMO'}
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
              onNavigateToGraph={handleViewOnGraph}
            />
          </div>
        )}

        {activeTab === 'reports' && (
          <div className="flex-1">
             <ReportsView 
               caseData={caseData} 
               traceId={selectedTraceId} 
               onNavigateToGraph={() => setActiveTab('graph')}
               onNavigateToEvidence={() => setActiveTab('evidence')}
             />
          </div>
        )}
      </div>
      
      {/* Footer */}
      <footer className="border-t border-surface-200 bg-surface-default py-1.5 px-4 sm:px-6 text-[11px] text-surface-500 font-medium flex items-center justify-between transition-colors">
        <span>Crypto-Tracer &bull; Enterprise Blockchain Forensic Intelligence Platform</span>
        <span>Cryptographic Audit Trail: Active &bull; Section 63 BSA Certified</span>
      </footer>

      {/* Re-Trace Modal */}
      {isRetraceModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
          <div className="bg-surface-default border border-surface-200 rounded-xl max-w-md w-full p-5 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-surface-200 pb-3">
              <div className="flex items-center gap-2">
                <RefreshCw className="h-4 w-4 text-reactor-orange" />
                <h3 className="font-bold text-sm text-surface-900 dark:text-white">Execute Re-Trace</h3>
              </div>
              <button 
                onClick={() => setIsRetraceModalOpen(false)}
                className="text-surface-400 hover:text-surface-700 p-1 cursor-pointer"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Wallet input */}
            <div className="space-y-1">
              <label className="text-xs font-semibold text-surface-700 dark:text-surface-300">Target Suspect Wallet</label>
              <input
                type="text"
                value={traceWalletInput}
                onChange={(e) => setTraceWalletInput(e.target.value.trim())}
                className="w-full px-3 py-1.5 text-xs font-mono bg-surface-50 dark:bg-surface-200/50 border border-surface-200 dark:border-surface-300 rounded-lg text-surface-800 dark:text-surface-100"
              />
            </div>

            {/* Mode selection */}
            <div className="space-y-1">
              <label className="text-xs font-semibold text-surface-700 dark:text-surface-300">Execution Mode</label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setTraceExecutionMode('LIVE')}
                  className={`p-2 rounded-lg border text-xs font-bold text-left cursor-pointer transition ${
                    traceExecutionMode === 'LIVE'
                      ? 'border-emerald-500 bg-emerald-500/15 text-emerald-700 dark:text-emerald-400'
                      : 'border-surface-200 text-surface-600 hover:bg-surface-50'
                  }`}
                >
                  <span className="block font-bold">LIVE TRON RPC</span>
                  <span className="text-[10px] font-normal text-surface-500">On-Chain Mainnet</span>
                </button>
                <button
                  type="button"
                  onClick={() => setTraceExecutionMode('DEMO')}
                  className={`p-2 rounded-lg border text-xs font-bold text-left cursor-pointer transition ${
                    traceExecutionMode === 'DEMO'
                      ? 'border-amber-500 bg-amber-500/15 text-amber-700 dark:text-amber-400'
                      : 'border-surface-200 text-surface-600 hover:bg-surface-50'
                  }`}
                >
                  <span className="block font-bold">DEMO FIXTURE</span>
                  <span className="text-[10px] font-normal text-surface-500">Deterministic replay</span>
                </button>
              </div>
            </div>

            {/* Traversal Depth */}
            <div className="space-y-1">
              <label className="text-xs font-semibold text-surface-700 dark:text-surface-300">Depth ({traceHops} Hops)</label>
              <div className="flex gap-1">
                {[2, 3, 4, 5, 6].map(h => (
                  <button
                    key={h}
                    type="button"
                    onClick={() => setTraceHops(h)}
                    className={`flex-1 py-1 rounded text-xs font-mono font-bold cursor-pointer transition ${
                      traceHops === h ? 'bg-reactor-orange text-white' : 'bg-surface-100 text-surface-700 border border-surface-200'
                    }`}
                  >
                    {h}
                  </button>
                ))}
              </div>
            </div>

            <button
              onClick={() => handleExecuteTrace()}
              disabled={isTracing}
              className="w-full py-2 bg-reactor-orange hover:bg-orange-600 disabled:opacity-50 text-white text-xs font-bold rounded-lg transition flex items-center justify-center gap-1.5 cursor-pointer shadow-sm"
            >
              {isTracing ? <Activity className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4 fill-current" />}
              <span>Launch Traversal</span>
            </button>
          </div>
        </div>
      )}

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
