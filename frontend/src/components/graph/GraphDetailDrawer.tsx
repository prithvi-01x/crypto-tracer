import React, { useState } from 'react';
import { 
  X, 
  Wallet, 
  ArrowRight, 
  Copy, 
  Check, 
  ExternalLink,
  GitCommit,
  ShieldCheck,
  Target,
  FileText,
  Building2,
  TrendingDown,
  Info
} from 'lucide-react';
import type { GraphNode, GraphEdge } from '../../types/graph';

interface GraphDetailDrawerProps {
  selectedNode: GraphNode | null;
  selectedEdge: GraphEdge | null;
  onClose: () => void;
  onHighlightPathToRoot?: (address: string) => void;
  onNavigateToReports?: () => void;
  onNavigateToEvidence?: () => void;
}

export const GraphDetailDrawer: React.FC<GraphDetailDrawerProps> = ({
  selectedNode,
  selectedEdge,
  onClose,
  onHighlightPathToRoot,
  onNavigateToReports,
  onNavigateToEvidence,
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

  // If nothing is selected, render the Reactor Entity Profiler idle/standby view
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
              <span>Investigation Tips</span>
            </div>
            <ul className="text-surface-500 space-y-1 pl-4 list-disc text-[11px]">
              <li>Red nodes highlight the illicit source wallet.</li>
              <li>Green nodes indicate candidate VASP deposit cashouts.</li>
              <li>Clicking an endpoint automatically computes Dijkstra path to root.</li>
            </ul>
          </div>
        </div>

        <div className="p-3 border-t border-surface-200 dark:border-surface-300 bg-surface-50 dark:bg-surface-200/50 flex items-center justify-between text-xs text-surface-500">
          <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-medium">
            <ShieldCheck className="h-3.5 w-3.5" />
            DAG Sealed
          </span>
          <span className="font-mono text-[11px]">BSA Sec. 63</span>
        </div>
      </div>
    );
  }

  // Calculate net flow for node
  const receivedNum = selectedNode ? (typeof selectedNode.total_received === 'string' ? parseFloat(selectedNode.total_received) : selectedNode.total_received) : 0;
  const sentNum = selectedNode ? (typeof selectedNode.total_sent === 'string' ? parseFloat(selectedNode.total_sent) : selectedNode.total_sent) : 0;
  const netRetained = Math.max(0, (receivedNum || 0) - (sentNum || 0));

  return (
    <div className="flex flex-col h-full bg-surface-default dark:bg-surface-100 text-surface-800 dark:text-surface-100 transition-colors">
      {/* Header */}
      <div className="p-4 border-b border-surface-200 dark:border-surface-300 flex items-center justify-between bg-surface-50 dark:bg-surface-200/50">
        <div className="flex items-center gap-2.5">
          {selectedNode ? (
            <div className={`p-1.5 rounded ${
              selectedNode.node_type === 'suspect'
                ? 'bg-red-500/10 text-red-600 dark:text-red-400'
                : selectedNode.node_type === 'endpoint'
                ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
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
              {selectedNode ? 'Wallet Inspection' : 'Transaction Edge'}
            </h3>
            <span className="text-xs text-surface-500">
              {selectedNode ? 'Entity Profiler • Forensic Intelligence' : 'On-Chain Ledger Edge'}
            </span>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded text-surface-400 hover:text-surface-700 dark:hover:text-surface-200 hover:bg-surface-200/60 transition"
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
            {/* Risk / Entity Type Badge & Hop */}
            <div className="flex items-center justify-between gap-2">
              <span className={`px-2.5 py-1 rounded text-xs font-bold uppercase tracking-wide border ${
                selectedNode.node_type === 'suspect'
                  ? 'bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 border-red-200 dark:border-red-800'
                  : selectedNode.node_type === 'endpoint'
                  ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800'
                  : 'bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-800'
              }`}>
                {selectedNode.node_type === 'suspect' 
                  ? '🚨 Root Suspect' 
                  : selectedNode.node_type === 'endpoint' 
                  ? '🎯 Endpoint / VASP Candidate' 
                  : '🔗 Intermediate Hop'}
              </span>

              <span className="px-2 py-0.5 rounded text-xs font-mono bg-surface-100 dark:bg-surface-200 text-surface-600 dark:text-surface-300 border border-surface-200 dark:border-surface-300">
                Hop Level: {selectedNode.hop}
              </span>
            </div>

            {/* Address Box */}
            <div className="p-3 rounded-lg bg-surface-50 dark:bg-surface-200/50 border border-surface-200 dark:border-surface-300 space-y-2">
              <div className="text-[11px] text-surface-500 uppercase font-semibold">Wallet Address</div>
              <div className="font-mono text-xs text-emerald-700 dark:text-emerald-400 break-all select-all font-semibold leading-relaxed">
                {selectedNode.address}
              </div>
              <div className="flex justify-between items-center pt-1 border-t border-surface-200 dark:border-surface-300">
                <button
                  onClick={() => copyToClipboard(selectedNode.address, 'node-addr')}
                  className="flex items-center gap-1 text-xs text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-white transition font-medium"
                >
                  {copiedKey === 'node-addr' ? (
                    <>
                      <Check className="h-3.5 w-3.5 text-emerald-500" />
                      <span className="text-emerald-600 dark:text-emerald-400">Copied</span>
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
                  className="flex items-center gap-1 text-xs text-brand-blue dark:text-blue-400 hover:underline transition font-medium"
                >
                  <span>TronScan</span>
                  <ExternalLink className="h-3.5 w-3.5" />
                </a>
              </div>
            </div>

            {/* 2-Column Financial Summary Card */}
            <div className="p-3 rounded-lg bg-surface-50 dark:bg-surface-200/50 border border-surface-200 dark:border-surface-300 space-y-2.5">
              <div className="text-[11px] text-surface-500 uppercase font-semibold">Financial Ledger Profile</div>
              <div className="grid grid-cols-2 gap-2">
                <div className="p-2 rounded bg-surface-default dark:bg-surface-100 border border-surface-200 dark:border-surface-300">
                  <span className="text-[10px] text-surface-500 block uppercase font-medium">Total Received</span>
                  <span className="font-mono font-bold text-xs text-emerald-600 dark:text-emerald-400 mt-0.5 block">
                    {formatUsdt(selectedNode.total_received)}
                  </span>
                </div>
                <div className="p-2 rounded bg-surface-default dark:bg-surface-100 border border-surface-200 dark:border-surface-300">
                  <span className="text-[10px] text-surface-500 block uppercase font-medium">Total Sent Out</span>
                  <span className="font-mono font-bold text-xs text-red-600 dark:text-red-400 mt-0.5 block">
                    {formatUsdt(selectedNode.total_sent)}
                  </span>
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-2 pt-1">
                <div>
                  <span className="text-[10px] text-surface-500 block uppercase">Net Retained</span>
                  <span className="font-mono font-bold text-xs text-surface-800 dark:text-surface-100">
                    {formatUsdt(netRetained)}
                  </span>
                </div>
                <div>
                  <span className="text-[10px] text-surface-500 block uppercase">Observed Transactions:</span>
                  <span className="font-mono font-bold text-xs text-surface-800 dark:text-surface-100">
                    {selectedNode.transaction_count} transfers
                  </span>
                </div>
              </div>
            </div>

            {/* Forensic Movement Narrative */}
            <div className="p-3 rounded-lg bg-surface-50 dark:bg-surface-200/40 border border-surface-200 dark:border-surface-300 space-y-1.5">
              <div className="text-[11px] text-surface-500 uppercase font-semibold flex items-center gap-1.5">
                <TrendingDown className="h-3.5 w-3.5 text-brand-blue dark:text-blue-400" />
                <span>Forensic Interpretation</span>
              </div>
              <p className="text-xs text-surface-600 dark:text-surface-300 leading-relaxed">
                {selectedNode.node_type === 'suspect' ? (
                  'Designated primary victim loss exit / suspect source wallet. All downstream funds cascade from this root address across multi-hop layering.'
                ) : selectedNode.node_type === 'endpoint' ? (
                  'Designated terminal cashout destination cluster. Associated with recognized VASP deposit patterns for crypto-to-fiat off-ramping.'
                ) : (
                  `Intermediate pass-through hop ${selectedNode.hop}. Used to rapidly split or consolidate stolen liquidity before depositing to centralized exchanges.`
                )}
              </p>
            </div>

            {/* Quick Actions */}
            <div className="space-y-2 pt-2">
              {onHighlightPathToRoot && selectedNode.node_type !== 'suspect' && (
                <button
                  onClick={() => onHighlightPathToRoot(selectedNode.address)}
                  className="w-full py-2 px-3 rounded-lg bg-surface-100 hover:bg-surface-200 dark:bg-surface-200 dark:hover:bg-surface-300 text-surface-800 dark:text-surface-100 font-semibold text-xs transition flex items-center justify-center gap-1.5 border border-surface-200 dark:border-surface-300 cursor-pointer"
                >
                  <Target className="h-3.5 w-3.5 text-reactor-orange" />
                  Highlight Dijkstra Path to Root
                </button>
              )}

              {selectedNode.node_type === 'endpoint' && onNavigateToReports && (
                <button
                  onClick={onNavigateToReports}
                  className="w-full py-2 px-3 rounded-lg bg-brand-blue hover:bg-brand-hover text-white font-semibold text-xs transition flex items-center justify-center gap-1.5 shadow-sm cursor-pointer"
                >
                  <FileText className="h-3.5 w-3.5" />
                  Draft Section 94 Notice for VASP
                </button>
              )}

              {onNavigateToEvidence && (
                <button
                  onClick={onNavigateToEvidence}
                  className="w-full py-2 px-3 rounded-lg bg-surface-50 hover:bg-surface-100 dark:bg-surface-200/40 dark:hover:bg-surface-200 text-surface-600 dark:text-surface-300 font-medium text-xs transition flex items-center justify-center gap-1.5 border border-surface-200 dark:border-surface-300 cursor-pointer"
                >
                  <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" />
                  Verify in Cryptographic Evidence Vault
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
              <span className="px-2.5 py-1 rounded text-xs font-bold uppercase bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
                Hop {selectedEdge.hop} Transfer
              </span>
              <span className="px-2 py-0.5 rounded text-xs font-mono bg-surface-100 dark:bg-surface-200 text-surface-600 dark:text-surface-300 border border-surface-200 dark:border-surface-300">
                {selectedEdge.asset}
              </span>
            </div>

            {/* Transfer Value Card */}
            <div className="p-3.5 rounded-lg bg-surface-50 dark:bg-surface-200/50 border border-surface-200 dark:border-surface-300 space-y-1">
              <div className="text-[11px] text-surface-500 uppercase font-semibold">Transfer Value</div>
              <div className="text-xl font-bold font-mono text-emerald-600 dark:text-emerald-400">
                {formatUsdt(selectedEdge.amount)}
              </div>
              <div className="text-[11px] text-surface-500 font-mono">
                Raw on-chain units: {selectedEdge.amount_raw.toLocaleString()}
              </div>
            </div>

            {/* Directional Route */}
            <div className="p-3 rounded-lg bg-surface-50 dark:bg-surface-200/50 border border-surface-200 dark:border-surface-300 space-y-2">
              <div className="text-[11px] text-surface-500 uppercase font-semibold">Directional Route</div>
              <div className="space-y-2 font-mono text-xs">
                <div>
                  <span className="text-[10px] text-surface-500 uppercase block">Source (From)</span>
                  <span className="text-surface-800 dark:text-surface-200 font-medium break-all">
                    {selectedEdge.from_address}
                  </span>
                </div>
                <div className="flex justify-center text-surface-400 py-0.5">
                  <ArrowRight className="h-4 w-4" />
                </div>
                <div>
                  <span className="text-[10px] text-surface-500 uppercase block">Destination (To)</span>
                  <span className="text-surface-800 dark:text-surface-200 font-medium break-all">
                    {selectedEdge.to_address}
                  </span>
                </div>
              </div>
            </div>

            {/* Tx Hash */}
            <div className="p-3 rounded-lg bg-surface-50 dark:bg-surface-200/50 border border-surface-200 dark:border-surface-300 space-y-1.5">
              <div className="text-[11px] text-surface-500 uppercase font-semibold">Transaction Hash</div>
              <div className="font-mono text-xs text-surface-700 dark:text-surface-300 break-all select-all font-medium leading-relaxed">
                {selectedEdge.tx_hash}
              </div>
              <div className="flex justify-between items-center pt-1 border-t border-surface-200 dark:border-surface-300">
                <button
                  onClick={() => copyToClipboard(selectedEdge.tx_hash, 'edge-hash')}
                  className="flex items-center gap-1 text-xs text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-white transition font-medium"
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
                  className="flex items-center gap-1 text-xs text-brand-blue dark:text-blue-400 hover:underline transition font-medium"
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
