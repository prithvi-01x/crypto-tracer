import React, { useState } from 'react';
import { 
  X, 
  Wallet, 
  ArrowRight, 
  ArrowLeftRight,
  Copy, 
  Check, 
  ExternalLink, 
  GitCommit, 
  ShieldCheck, 
  Target, 
  FileText, 
  Building2, 
  TrendingDown, 
  Info,
  AlertTriangle,
  Layers,
  FileCheck
} from 'lucide-react';
import type { InvestigationGraph, GraphNode, GraphEdge } from '../../types/graph';
import type { AttributionResponse } from '../../types/attribution';
import type { ForensicFindingItem } from '../../types/findings';

interface GraphDetailDrawerProps {
  selectedNode: GraphNode | null;
  selectedEdge: GraphEdge | null;
  onClose: () => void;
  onHighlightPathToRoot?: (address: string) => void;
  onNavigateToReports?: () => void;
  onNavigateToEvidence?: (evidenceId?: string) => void;
  onNavigateToFinding?: (findingId: string) => void;
  onSelectNodeByAddress?: (address: string) => void;
  graph?: InvestigationGraph | null;
  attribution?: AttributionResponse | null;
  findings?: ForensicFindingItem[];
}

export const GraphDetailDrawer: React.FC<GraphDetailDrawerProps> = ({
  selectedNode,
  selectedEdge,
  onClose,
  onHighlightPathToRoot,
  onNavigateToReports,
  onNavigateToEvidence,
  onNavigateToFinding,
  onSelectNodeByAddress,
  graph,
  attribution,
  findings = [],
}) => {
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const copyToClipboard = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const formatUsdt = (val: number | string) => {
    const num = typeof val === 'string' ? parseFloat(val) : val;
    if (isNaN(num)) return `${val} USDT`;
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 }).format(num).replace('$', '') + ' USDT';
  };

  // If nothing is selected, render the Reactor Entity Profiler standby view
  if (!selectedNode && !selectedEdge) {
    return (
      <div className="flex flex-col h-full bg-surface-default dark:bg-surface-100 text-surface-800 dark:text-surface-100 transition-colors">
        <div className="p-4 border-b border-surface-200 dark:border-surface-300 bg-surface-50 dark:bg-surface-200/50 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded bg-brand-light dark:bg-blue-950/60 text-brand-blue dark:text-blue-400">
              <Building2 className="h-4 w-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold uppercase tracking-wider text-surface-800 dark:text-surface-100">
                Entity Profiler
              </h3>
              <span className="text-xs text-surface-500">Forensic Canvas Standby</span>
            </div>
          </div>
        </div>

        <div className="flex-1 flex flex-col items-center justify-center p-6 text-center space-y-4">
          <div className="p-4 rounded-full bg-surface-100 dark:bg-surface-200 text-surface-400">
            <Wallet className="h-8 w-8" />
          </div>
          <div className="space-y-1.5 max-w-xs">
            <h4 className="text-base font-semibold text-surface-800 dark:text-surface-200">No Item Selected</h4>
            <p className="text-xs text-surface-500 leading-relaxed">
              Click any wallet node or transaction edge on the canvas to inspect counterparty flows, VASP attribution, and legal notice actions.
            </p>
          </div>
          <div className="p-3 rounded-lg bg-surface-50 dark:bg-surface-200/40 border border-surface-200 dark:border-surface-300 text-left w-full text-xs space-y-2">
            <div className="flex items-center gap-2 text-surface-700 dark:text-surface-300 font-semibold">
              <Info className="h-4 w-4 text-reactor-orange shrink-0" />
              <span>Investigation Navigation Tips</span>
            </div>
            <ul className="text-surface-500 space-y-1 pl-4 list-disc text-[11px]">
              <li>Red nodes highlight the root suspect wallet.</li>
              <li>Purple &amp; green nodes indicate candidate VASP deposit cashouts.</li>
              <li>Selecting any node traces its Dijkstra path from the root suspect.</li>
              <li>Use hotkeys: <code className="px-1 py-0.5 bg-surface-200 rounded font-mono">F</code> (Fit), <code className="px-1 py-0.5 bg-surface-200 rounded font-mono">C</code> (Center), <code className="px-1 py-0.5 bg-surface-200 rounded font-mono">L</code> (Labels).</li>
            </ul>
          </div>
        </div>

        <div className="p-3 border-t border-surface-200 dark:border-surface-300 bg-surface-50 dark:bg-surface-200/50 flex items-center justify-between text-xs text-surface-500">
          <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-medium">
            <ShieldCheck className="h-3.5 w-3.5" />
            Forensic Integrity Sealed
          </span>
          <span className="font-mono text-[11px]">Section 63 BSA</span>
        </div>
      </div>
    );
  }

  // Calculate net flow for node
  const receivedNum = selectedNode ? (typeof selectedNode.total_received === 'string' ? parseFloat(selectedNode.total_received) : selectedNode.total_received) : 0;
  const sentNum = selectedNode ? (typeof selectedNode.total_sent === 'string' ? parseFloat(selectedNode.total_sent) : selectedNode.total_sent) : 0;
  const netRetained = Math.max(0, (receivedNum || 0) - (sentNum || 0));

  // Determine role classification
  const isSuspect = selectedNode?.node_type === 'suspect' || (graph?.meta?.source_wallet && selectedNode?.address === graph.meta.source_wallet);
  const isCandidateNode = !!(selectedNode && attribution?.best_candidate?.candidate_address === selectedNode.address);
  const isEndpointNode = selectedNode?.node_type === 'endpoint';
  const vaspName = (attribution?.best_candidate?.exchange_name || 'VASP Entity').toUpperCase();

  // In-degree for consolidation detection
  const inDegree = selectedNode && graph?.edges ? graph.edges.filter(e => e.to_address === selectedNode.address).length : 0;
  const isConsolidation = !isSuspect && !isCandidateNode && !isEndpointNode && (
    inDegree > 1 || 
    (selectedNode?.hop === 2 && (receivedNum || 0) >= 40000)
  );

  let roleLabel = 'HOP MULE';
  let roleDesc = 'Layering Pass-Through';
  let roleBadgeClass = 'bg-sky-50 dark:bg-sky-950/40 text-sky-700 dark:text-sky-300 border-sky-200 dark:border-sky-800';
  let roleIcon = '🔗';

  if (isSuspect) {
    roleLabel = 'ROOT SUSPECT';
    roleDesc = 'Primary Victim Loss Source';
    roleBadgeClass = 'bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 border-red-200 dark:border-red-800';
    roleIcon = '🚨';
  } else if (isCandidateNode) {
    roleLabel = `VASP CANDIDATE (${vaspName})`;
    roleDesc = 'Deposit Sweep Candidate Endpoint';
    roleBadgeClass = 'bg-purple-50 dark:bg-purple-950/40 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-800';
    roleIcon = '🎯';
  } else if (isEndpointNode) {
    roleLabel = 'VASP DESTINATION (Endpoint)';
    roleDesc = 'Centralized Exchange Terminal Endpoint';
    roleBadgeClass = 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800';
    roleIcon = '🏦';
  } else if (isConsolidation) {
    roleLabel = 'CONSOLIDATION HUB';
    roleDesc = 'Intermediate Hop Aggregator';
    roleBadgeClass = 'bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 border-indigo-200 dark:border-indigo-800';
    roleIcon = '🔄';
  } else {
    roleLabel = 'INTERMEDIATE HOP MULE';
    roleDesc = `Hop ${selectedNode?.hop || 1} Intermediate Pass-Through`;
    roleBadgeClass = 'bg-sky-50 dark:bg-sky-950/40 text-sky-700 dark:text-sky-300 border-sky-200 dark:border-sky-800';
    roleIcon = '🔗';
  }

  // Filter findings matching selected node
  const nodeFindings = selectedNode ? findings.filter(f => f.related_address === selectedNode.address || f.graph_node_id === selectedNode.address) : [];
  
  // Extract unique supporting evidence from node findings
  const relevantEvidenceRefs = nodeFindings.flatMap(f => f.evidence_refs || []);
  const uniqueEvidence = Array.from(new Map(relevantEvidenceRefs.map(item => [item.id, item])).values());

  // Compute counterparty flows (inflows & outflows)
  const inflows = selectedNode && graph?.edges ? graph.edges.filter(e => e.to_address === selectedNode.address) : [];
  const outflows = selectedNode && graph?.edges ? graph.edges.filter(e => e.from_address === selectedNode.address) : [];

  return (
    <div className="flex flex-col h-full bg-surface-default dark:bg-surface-100 text-surface-800 dark:text-surface-100 transition-colors">
      {/* Header */}
      <div className="p-4 border-b border-surface-200 dark:border-surface-300 flex items-center justify-between bg-surface-50 dark:bg-surface-200/50">
        <div className="flex items-center gap-2.5">
          {selectedNode ? (
            <div className={`p-1.5 rounded ${
              isSuspect
                ? 'bg-red-500/10 text-red-600 dark:text-red-400'
                : isCandidateNode
                ? 'bg-purple-500/10 text-purple-600 dark:text-purple-400'
                : isEndpointNode
                ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                : isConsolidation
                ? 'bg-indigo-500/10 text-indigo-600 dark:text-indigo-400'
                : 'bg-blue-500/10 text-brand-blue dark:text-blue-400'
            }`}>
              <Wallet className="h-4 w-4" />
            </div>
          ) : (
            <div className="p-1.5 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400">
              <GitCommit className="h-4 w-4" />
            </div>
          )}
          <div>
            <h3 className="text-sm font-bold uppercase tracking-wider text-surface-800 dark:text-surface-100">
              {selectedNode ? 'Wallet Inspection • Entity Profiler' : 'Transaction Edge'}
            </h3>
            <span className="text-xs text-surface-500">
              {selectedNode ? 'Forensic Inspection & Intelligence' : 'On-Chain Ledger Edge'}
            </span>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded text-surface-400 hover:text-surface-700 dark:hover:text-surface-200 hover:bg-surface-200/60 transition cursor-pointer"
          aria-label="Close Inspector"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs">
        {/* NODE DETAILS */}
        {selectedNode && (
          <div className="space-y-4">
            {/* 1. ENTITY IDENTITY (Dominant Header) */}
            <div className="p-3.5 rounded-lg bg-surface-50 dark:bg-surface-200/50 border border-surface-200 dark:border-surface-300 space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-surface-500 uppercase font-bold tracking-wider">
                  Wallet Address
                </span>
                <span className="text-[10px] font-mono text-surface-500">
                  {selectedNode.chain || 'TRON'}
                </span>
              </div>
              <div className="font-mono text-xs sm:text-[13px] text-emerald-700 dark:text-emerald-400 break-all select-all font-extrabold leading-relaxed p-2.5 rounded-md bg-surface-default dark:bg-surface-100 border border-surface-200 dark:border-surface-300 shadow-2xs">
                {selectedNode.address}
              </div>
              <div className="flex justify-between items-center pt-1 border-t border-surface-200 dark:border-surface-300">
                <button
                  onClick={() => copyToClipboard(selectedNode.address, 'node-addr')}
                  className="flex items-center gap-1 text-xs text-surface-600 dark:text-surface-300 hover:text-surface-900 dark:hover:text-white transition font-semibold cursor-pointer"
                >
                  {copiedKey === 'node-addr' ? (
                    <>
                      <Check className="h-3.5 w-3.5 text-emerald-500" />
                      <span className="text-emerald-600 dark:text-emerald-400">Copied Address</span>
                    </>
                  ) : (
                    <>
                      <Copy className="h-3.5 w-3.5" />
                      <span>Copy Address</span>
                    </>
                  )}
                </button>
                <a
                  href={`https://tronscan.org/#/address/${selectedNode.address}`}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1 text-xs text-brand-blue dark:text-blue-400 hover:underline transition font-semibold"
                >
                  <span>Verify on TronScan</span>
                  <ExternalLink className="h-3.5 w-3.5" />
                </a>
              </div>
            </div>

            {/* 2. ROLE & CLASSIFICATION */}
            <div className="p-3 rounded-lg bg-surface-50 dark:bg-surface-200/50 border border-surface-200 dark:border-surface-300 flex items-center justify-between gap-2 flex-wrap">
              <div className="flex items-center gap-2">
                <span className={`px-2.5 py-1 rounded text-xs font-bold uppercase tracking-wide border flex items-center gap-1.5 ${roleBadgeClass}`}>
                  <span>{roleIcon}</span>
                  <span>{roleLabel}</span>
                </span>
                <span className="text-[11px] text-surface-500 hidden sm:inline font-medium">
                  {roleDesc}
                </span>
              </div>
              <span className="px-2 py-0.5 rounded text-xs font-mono bg-surface-100 dark:bg-surface-200 text-surface-700 dark:text-surface-300 border border-surface-200 dark:border-surface-300 font-bold">
                Hop Level: {selectedNode.hop}
              </span>
            </div>

            {/* 3. KEY FINANCIAL & TRANSACTION METRICS */}
            <div className="p-3.5 rounded-lg bg-surface-50 dark:bg-surface-200/50 border border-surface-200 dark:border-surface-300 space-y-2.5">
              <div className="text-[10px] text-surface-500 uppercase font-bold tracking-wider">
                Financial Ledger Metrics
              </div>
              <div className="grid grid-cols-2 gap-2.5">
                <div className="p-2.5 rounded-md bg-surface-default dark:bg-surface-100 border border-surface-200 dark:border-surface-300">
                  <span className="text-[10px] text-surface-500 block uppercase font-bold tracking-wider">Total Received</span>
                  <span className="font-mono font-extrabold text-sm sm:text-base text-emerald-600 dark:text-emerald-400 mt-1 block">
                    {formatUsdt(selectedNode.total_received)}
                  </span>
                </div>
                <div className="p-2.5 rounded-md bg-surface-default dark:bg-surface-100 border border-surface-200 dark:border-surface-300">
                  <span className="text-[10px] text-surface-500 block uppercase font-bold tracking-wider">Total Sent Out</span>
                  <span className="font-mono font-extrabold text-sm sm:text-base text-red-600 dark:text-red-400 mt-1 block">
                    {formatUsdt(selectedNode.total_sent)}
                  </span>
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-2.5 pt-1.5 border-t border-surface-200 dark:border-surface-300">
                <div>
                  <span className="text-[10px] text-surface-500 block uppercase font-bold tracking-wider">Net Retained</span>
                  <span className="font-mono font-bold text-xs sm:text-sm text-surface-900 dark:text-white">
                    {formatUsdt(netRetained)}
                  </span>
                </div>
                <div>
                  <span className="text-[10px] text-surface-500 block uppercase font-bold tracking-wider">Observed Transfers</span>
                  <span className="font-mono font-bold text-xs sm:text-sm text-surface-900 dark:text-white">
                    {selectedNode.transaction_count} txs
                  </span>
                </div>
              </div>
            </div>

            {/* 4. VASP INTELLIGENCE / ATTRIBUTION */}
            {(isCandidateNode || (isEndpointNode && attribution?.best_candidate)) && attribution?.best_candidate && (
              <div className="p-3.5 rounded-lg bg-purple-500/10 border border-purple-500/30 space-y-2.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 text-purple-700 dark:text-purple-300 font-bold uppercase text-[10px] tracking-wider">
                    <Building2 className="h-3.5 w-3.5 text-purple-600 dark:text-purple-400" />
                    <span>VASP Attribution Intelligence</span>
                  </div>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-purple-500/20 text-purple-800 dark:text-purple-300">
                    {Math.round((attribution.best_candidate.confidence_score || 0) * 100)}% Match ({attribution.best_candidate.confidence_band || 'HIGH'})
                  </span>
                </div>
                <div className="p-2.5 rounded bg-surface-default dark:bg-surface-100 border border-purple-200 dark:border-purple-900/40 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-surface-500 uppercase font-bold">Identified VASP</span>
                    <span className="font-bold text-xs text-purple-700 dark:text-purple-300 font-mono">
                      {attribution.best_candidate.exchange_name || 'VASP Entity'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-surface-500 uppercase font-bold">Clustering Strategy</span>
                    <span className="font-mono text-[11px] text-surface-700 dark:text-surface-300">
                      {attribution.best_candidate.clustering_rule || 'Deposit Sweep & Forwarding'}
                    </span>
                  </div>
                  {attribution.best_candidate.attribution_type && (
                    <div className="flex items-center justify-between pt-1 border-t border-surface-200 dark:border-surface-300/50">
                      <span className="text-[10px] text-surface-500 uppercase font-bold">Evidence Rule</span>
                      <span className="font-mono text-[10px] text-surface-600 dark:text-surface-400">
                        {attribution.best_candidate.attribution_type}
                      </span>
                    </div>
                  )}
                </div>
                <p className="text-[10px] text-purple-800/80 dark:text-purple-300/80 italic leading-tight">
                  Analytical attribution hypothesis derived from on-chain patterns. Does not constitute autonomous legal proof of ownership.
                </p>
              </div>
            )}

            {/* 5. FORENSIC FINDINGS */}
            {nodeFindings.length > 0 && (
              <div className="p-3.5 rounded-lg bg-red-500/10 border border-red-500/30 space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-red-700 dark:text-red-300 flex items-center gap-1.5">
                    <AlertTriangle className="h-3.5 w-3.5 text-red-500 shrink-0" />
                    <span>Correlated Forensic Findings ({nodeFindings.length})</span>
                  </span>
                </div>
                <div className="space-y-2">
                  {nodeFindings.map((f) => (
                    <div key={f.finding_id} className="p-2.5 rounded bg-surface-default dark:bg-surface-100 border border-red-200 dark:border-red-900/40 space-y-1">
                      <div className="flex items-center justify-between font-semibold text-red-700 dark:text-red-300 text-xs">
                        <span>{f.title}</span>
                        <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-red-500/20 text-red-800 dark:text-red-200 font-bold">
                          {f.severity}
                        </span>
                      </div>
                      <p className="text-surface-600 dark:text-surface-400 text-[11px] leading-relaxed">
                        {f.description}
                      </p>
                      {onNavigateToFinding && (
                        <div className="pt-1 flex justify-end">
                          <button
                            onClick={() => onNavigateToFinding(f.finding_id)}
                            className="text-[10px] font-bold text-brand-blue dark:text-blue-400 hover:underline flex items-center gap-0.5 cursor-pointer"
                          >
                            <span>Inspect Finding</span>
                            <ArrowRight className="h-3 w-3" />
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 6. SUPPORTING EVIDENCE */}
            {uniqueEvidence.length > 0 && (
              <div className="p-3.5 rounded-lg bg-surface-50 dark:bg-surface-200/50 border border-surface-200 dark:border-surface-300 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-surface-500 uppercase font-bold tracking-wider flex items-center gap-1">
                    <FileCheck className="h-3.5 w-3.5 text-emerald-500" />
                    <span>Supporting Evidentiary Records ({uniqueEvidence.length})</span>
                  </span>
                  <span className="font-mono text-[10px] text-surface-500">BSA §63</span>
                </div>
                <div className="space-y-1.5">
                  {uniqueEvidence.map((ev) => (
                    <div 
                      key={ev.id} 
                      className="p-2 rounded bg-surface-default dark:bg-surface-100 border border-surface-200 dark:border-surface-300 text-xs flex items-center justify-between gap-2"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5">
                          <span className="px-1.5 py-0.2 rounded text-[9px] font-mono font-bold bg-brand-light dark:bg-blue-950/60 text-brand-blue dark:text-blue-400">
                            {ev.classification}
                          </span>
                          <span className="font-mono text-[11px] font-semibold text-surface-800 dark:text-surface-200 truncate">
                            {ev.id}
                          </span>
                        </div>
                        <p className="text-[10px] text-surface-500 truncate mt-0.5">
                          {ev.title} &bull; SHA256: {ev.content_hash.substring(0, 8)}...
                        </p>
                      </div>
                      {onNavigateToEvidence && (
                        <button
                          onClick={() => onNavigateToEvidence(ev.id)}
                          className="text-[11px] text-brand-blue dark:text-blue-400 font-semibold hover:underline shrink-0 flex items-center gap-0.5 cursor-pointer"
                        >
                          <span>View</span>
                          <ExternalLink className="h-3 w-3" />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 7. RELATED FLOWS & COUNTERPARTIES */}
            {(inflows.length > 0 || outflows.length > 0) && (
              <div className="p-3.5 rounded-lg bg-surface-50 dark:bg-surface-200/50 border border-surface-200 dark:border-surface-300 space-y-2.5">
                <div className="text-[10px] text-surface-500 uppercase font-bold tracking-wider flex items-center gap-1.5">
                  <ArrowLeftRight className="h-3.5 w-3.5 text-brand-blue dark:text-blue-400" />
                  <span>Observed Counterparty Transfers ({inflows.length + outflows.length})</span>
                </div>

                {inflows.length > 0 && (
                  <div className="space-y-1">
                    <span className="text-[10px] font-bold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider block">
                      Incoming Inflows ({inflows.length})
                    </span>
                    <div className="space-y-1 max-h-32 overflow-y-auto">
                      {inflows.map((inf) => (
                        <div 
                          key={inf.id} 
                          className="flex items-center justify-between p-1.5 rounded bg-surface-default dark:bg-surface-100 border border-surface-200 dark:border-surface-300 text-[11px]"
                        >
                          <button
                            onClick={() => onSelectNodeByAddress?.(inf.from_address)}
                            className="font-mono text-brand-blue dark:text-blue-400 hover:underline truncate max-w-[170px] text-left cursor-pointer"
                            title={`Jump to sender: ${inf.from_address}`}
                          >
                            &larr; {inf.from_address.slice(0, 8)}...{inf.from_address.slice(-6)}
                          </button>
                          <span className="font-mono font-bold text-emerald-600 dark:text-emerald-400 shrink-0">
                            +{formatUsdt(inf.amount)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {outflows.length > 0 && (
                  <div className="space-y-1 pt-1 border-t border-surface-200 dark:border-surface-300">
                    <span className="text-[10px] font-bold text-red-600 dark:text-red-400 uppercase tracking-wider block">
                      Outgoing Outflows ({outflows.length})
                    </span>
                    <div className="space-y-1 max-h-32 overflow-y-auto">
                      {outflows.map((outf) => (
                        <div 
                          key={outf.id} 
                          className="flex items-center justify-between p-1.5 rounded bg-surface-default dark:bg-surface-100 border border-surface-200 dark:border-surface-300 text-[11px]"
                        >
                          <button
                            onClick={() => onSelectNodeByAddress?.(outf.to_address)}
                            className="font-mono text-brand-blue dark:text-blue-400 hover:underline truncate max-w-[170px] text-left cursor-pointer"
                            title={`Jump to recipient: ${outf.to_address}`}
                          >
                            &rarr; {outf.to_address.slice(0, 8)}...{outf.to_address.slice(-6)}
                          </button>
                          <span className="font-mono font-bold text-red-600 dark:text-red-400 shrink-0">
                            -{formatUsdt(outf.amount)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Forensic Movement Narrative */}
            <div className="p-3.5 rounded-lg bg-surface-50 dark:bg-surface-200/40 border border-surface-200 dark:border-surface-300 space-y-1.5">
              <div className="text-[10px] text-surface-500 uppercase font-bold tracking-wider flex items-center gap-1.5">
                <TrendingDown className="h-3.5 w-3.5 text-brand-blue dark:text-blue-400" />
                <span>Forensic Movement Narrative</span>
              </div>
              <p className="text-xs sm:text-[12px] text-surface-700 dark:text-surface-200 leading-relaxed font-normal">
                {isSuspect ? (
                  'Designated primary victim loss exit / suspect source wallet. Stolen liquidity originates at this root node and is aggressively split or routed forward across downstream mule hops.'
                ) : isCandidateNode || isEndpointNode ? (
                  `Designated terminal cashout destination cluster. Correlated with recognized ${vaspName} deposit aggregation sweeps for crypto-to-fiat off-ramping.`
                ) : isConsolidation ? (
                  `Consolidation hub wallet at hop ${selectedNode.hop}. Gathers fragmented mule disbursements into a single high-volume batch prior to exchange deposit.`
                ) : (
                  `Intermediate pass-through hop ${selectedNode.hop}. Used to rapidly split, layer, and obscure stolen liquidity between the suspect root and destination endpoints.`
                )}
              </p>
            </div>

            {/* 8. INVESTIGATOR ACTIONS */}
            <div className="space-y-2 pt-1">
              {onHighlightPathToRoot && !isSuspect && (
                <button
                  onClick={() => onHighlightPathToRoot(selectedNode.address)}
                  className="w-full py-2.5 px-3 rounded-lg bg-surface-100 hover:bg-surface-200 dark:bg-surface-200 dark:hover:bg-surface-300 text-surface-800 dark:text-surface-100 font-bold text-xs transition flex items-center justify-center gap-2 border border-surface-200 dark:border-surface-300 cursor-pointer shadow-xs"
                >
                  <Target className="h-4 w-4 text-reactor-orange" />
                  <span>Highlight Trail from Suspect</span>
                </button>
              )}

              {(isEndpointNode || isCandidateNode) && onNavigateToReports && (
                <button
                  onClick={onNavigateToReports}
                  className="w-full py-2.5 px-3 rounded-lg bg-brand-blue hover:bg-brand-hover text-white font-bold text-xs transition flex items-center justify-center gap-2 shadow-sm cursor-pointer"
                >
                  <FileText className="h-4 w-4" />
                  <span>Draft Section 94 Notice for VASP</span>
                </button>
              )}

              {onNavigateToEvidence && (
                <button
                  onClick={() => onNavigateToEvidence()}
                  className="w-full py-2.5 px-3 rounded-lg bg-surface-50 hover:bg-surface-100 dark:bg-surface-200/40 dark:hover:bg-surface-200 text-surface-700 dark:text-surface-200 font-semibold text-xs transition flex items-center justify-center gap-2 border border-surface-200 dark:border-surface-300 cursor-pointer shadow-xs"
                >
                  <ShieldCheck className="h-4 w-4 text-emerald-500" />
                  <span>Inspect in Cryptographic Evidence Vault</span>
                </button>
              )}
            </div>
          </div>
        )}

        {/* EDGE DETAILS */}
        {selectedEdge && (
          <div className="space-y-4">
            {/* Edge Badges */}
            <div className="flex items-center justify-between">
              <span className="px-2.5 py-1 rounded text-xs font-bold uppercase bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800 font-semibold">
                Hop {selectedEdge.hop} Transfer
              </span>
              <span className="px-2 py-0.5 rounded text-xs font-mono bg-surface-100 dark:bg-surface-200 text-surface-600 dark:text-surface-300 border border-surface-200 dark:border-surface-300 font-bold">
                {selectedEdge.asset}
              </span>
            </div>

            {/* Transfer Value Card */}
            <div className="p-3.5 rounded-lg bg-surface-50 dark:bg-surface-200/50 border border-surface-200 dark:border-surface-300 space-y-1.5">
              <div className="text-[11px] text-surface-500 uppercase font-bold tracking-wider">Transfer Value</div>
              <div className="text-2xl font-black font-mono text-emerald-600 dark:text-emerald-400">
                {formatUsdt(selectedEdge.amount)}
              </div>
              <div className="text-[11px] text-surface-500 font-mono">
                Raw on-chain units: {selectedEdge.amount_raw.toLocaleString()}
              </div>
            </div>

            {/* Directional Route */}
            <div className="p-3.5 rounded-lg bg-surface-50 dark:bg-surface-200/50 border border-surface-200 dark:border-surface-300 space-y-2.5">
              <div className="text-[11px] text-surface-500 uppercase font-bold tracking-wider">Directional Route</div>
              <div className="space-y-2 font-mono text-xs">
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] text-surface-500 uppercase font-bold tracking-wider">Source (From)</span>
                    {onSelectNodeByAddress && (
                      <button
                        onClick={() => onSelectNodeByAddress(selectedEdge.from_address)}
                        className="text-[11px] text-brand-blue dark:text-blue-400 hover:underline font-bold cursor-pointer"
                      >
                        Inspect Node &rarr;
                      </button>
                    )}
                  </div>
                  <div 
                    onClick={() => onSelectNodeByAddress?.(selectedEdge.from_address)}
                    className={`text-surface-800 dark:text-surface-200 font-bold break-all p-2 rounded bg-surface-default dark:bg-surface-100 border border-surface-200 dark:border-surface-300 ${onSelectNodeByAddress ? 'cursor-pointer hover:border-brand-blue/50' : ''}`}
                    title={onSelectNodeByAddress ? `Jump to source wallet node: ${selectedEdge.from_address}` : undefined}
                  >
                    {selectedEdge.from_address}
                  </div>
                </div>
                <div className="flex justify-center text-surface-400 py-0.5">
                  <ArrowRight className="h-4 w-4" />
                </div>
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] text-surface-500 uppercase font-bold tracking-wider">Destination (To)</span>
                    {onSelectNodeByAddress && (
                      <button
                        onClick={() => onSelectNodeByAddress(selectedEdge.to_address)}
                        className="text-[11px] text-brand-blue dark:text-blue-400 hover:underline font-bold cursor-pointer"
                      >
                        Inspect Node &rarr;
                      </button>
                    )}
                  </div>
                  <div 
                    onClick={() => onSelectNodeByAddress?.(selectedEdge.to_address)}
                    className={`text-surface-800 dark:text-surface-200 font-bold break-all p-2 rounded bg-surface-default dark:bg-surface-100 border border-surface-200 dark:border-surface-300 ${onSelectNodeByAddress ? 'cursor-pointer hover:border-brand-blue/50' : ''}`}
                    title={onSelectNodeByAddress ? `Jump to destination wallet node: ${selectedEdge.to_address}` : undefined}
                  >
                    {selectedEdge.to_address}
                  </div>
                </div>
              </div>
            </div>

            {/* Tx Hash */}
            <div className="p-3.5 rounded-lg bg-surface-50 dark:bg-surface-200/50 border border-surface-200 dark:border-surface-300 space-y-2">
              <div className="text-[11px] text-surface-500 uppercase font-bold tracking-wider">Transaction Hash</div>
              <div className="font-mono text-xs sm:text-[13px] text-surface-800 dark:text-surface-200 break-all select-all font-bold leading-relaxed p-2.5 rounded bg-surface-default dark:bg-surface-100 border border-surface-200 dark:border-surface-300">
                {selectedEdge.tx_hash}
              </div>
              <div className="flex justify-between items-center pt-1 border-t border-surface-200 dark:border-surface-300">
                <button
                  onClick={() => copyToClipboard(selectedEdge.tx_hash, 'edge-hash')}
                  className="flex items-center gap-1 text-xs text-surface-600 dark:text-surface-300 hover:text-surface-900 dark:hover:text-white transition font-semibold cursor-pointer"
                >
                  {copiedKey === 'edge-hash' ? (
                    <>
                      <Check className="h-3.5 w-3.5 text-emerald-500" />
                      <span className="text-emerald-600 dark:text-emerald-400">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="h-3.5 w-3.5" />
                      <span>Copy TxID</span>
                    </>
                  )}
                </button>
                <a
                  href={`https://tronscan.org/#/transaction/${selectedEdge.tx_hash}`}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1 text-xs text-brand-blue dark:text-blue-400 hover:underline transition font-semibold"
                >
                  <span>TronScan</span>
                  <ExternalLink className="h-3.5 w-3.5" />
                </a>
              </div>
            </div>

            {/* Block & Provenance */}
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="p-2.5 rounded-lg bg-surface-50 dark:bg-surface-200/50 border border-surface-200 dark:border-surface-300">
                <span className="text-[10px] text-surface-500 uppercase block font-medium">Block Height</span>
                <span className="font-mono font-semibold text-surface-800 dark:text-surface-200">
                  {selectedEdge.block_number !== null && selectedEdge.block_number !== undefined
                    ? selectedEdge.block_number
                    : 'N/A (Recorded)'}
                </span>
              </div>
              <div className="p-2.5 rounded-lg bg-surface-50 dark:bg-surface-200/50 border border-surface-200 dark:border-surface-300">
                <span className="text-[10px] text-surface-500 uppercase block font-medium">Provenance</span>
                <span className="font-mono font-semibold text-surface-800 dark:text-surface-200">{selectedEdge.source}</span>
              </div>
            </div>

            <div className="p-2.5 rounded-lg bg-surface-50 dark:bg-surface-200/50 border border-surface-200 dark:border-surface-300 text-xs flex items-center justify-between">
              <span className="text-surface-500 font-medium">Timestamp:</span>
              <span className="font-mono text-surface-700 dark:text-surface-300 font-medium">
                {new Date(selectedEdge.timestamp).toLocaleString()}
              </span>
            </div>

            {/* Investigator Action for Edge */}
            {onNavigateToEvidence && (
              <div className="pt-1">
                <button
                  onClick={() => onNavigateToEvidence()}
                  className="w-full py-2.5 px-3 rounded-lg bg-surface-50 hover:bg-surface-100 dark:bg-surface-200/40 dark:hover:bg-surface-200 text-surface-700 dark:text-surface-200 font-semibold text-xs transition flex items-center justify-center gap-2 border border-surface-200 dark:border-surface-300 cursor-pointer shadow-xs"
                >
                  <ShieldCheck className="h-4 w-4 text-emerald-500" />
                  <span>Inspect Transfer in Cryptographic Evidence Vault</span>
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer / Section 63 BSA badge */}
      <div className="p-3 border-t border-surface-200 dark:border-surface-300 bg-surface-50 dark:bg-surface-200/50 flex items-center justify-between text-xs text-surface-500">
        <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-medium">
          <ShieldCheck className="h-3.5 w-3.5" />
          Forensic Integrity Sealed
        </span>
        <span className="font-mono text-[11px]">Section 63 BSA</span>
      </div>
    </div>
  );
};
