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
  Target
} from 'lucide-react';
import type { GraphNode, GraphEdge } from '../../types/graph';

interface GraphDetailDrawerProps {
  selectedNode: GraphNode | null;
  selectedEdge: GraphEdge | null;
  onClose: () => void;
  onHighlightPathToRoot?: (address: string) => void;
}

export const GraphDetailDrawer: React.FC<GraphDetailDrawerProps> = ({
  selectedNode,
  selectedEdge,
  onClose,
  onHighlightPathToRoot,
}) => {
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  if (!selectedNode && !selectedEdge) return null;

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

  return (
    <div className="w-80 lg:w-96 bg-police-850/95 border-l border-police-700/80 shadow-2xl flex flex-col h-full backdrop-blur transition-all duration-200">
      {/* Header */}
      <div className="p-4 border-b border-police-700/80 flex items-center justify-between bg-police-800/60">
        <div className="flex items-center gap-2">
          {selectedNode ? (
            <div className={`p-1.5 rounded-lg ${
              selectedNode.node_type === 'suspect'
                ? 'bg-red-500/20 text-red-400'
                : selectedNode.node_type === 'endpoint'
                ? 'bg-emerald-500/20 text-emerald-400'
                : 'bg-blue-500/20 text-brand-blue'
            }`}>
              <Wallet className="h-4 w-4" />
            </div>
          ) : (
            <div className="p-1.5 rounded-lg bg-amber-500/20 text-amber-400">
              <GitCommit className="h-4 w-4" />
            </div>
          )}
          <div>
            <h3 className="text-base font-bold uppercase tracking-wider text-white">
              {selectedNode ? 'Wallet Inspection' : 'Transaction Edge'}
            </h3>
            <span className="text-sm text-surface-400">Forensic Graph Item</span>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded-md text-surface-400 hover:text-white hover:bg-police-700 transition"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 text-base">
        {/* NODE DETAILS */}
        {selectedNode && (
          <div className="space-y-4">
            {/* Type badge & Hop */}
            <div className="flex items-center justify-between">
              <span className={`px-2 py-0.5 rounded text-sm font-bold uppercase tracking-wide border ${
                selectedNode.node_type === 'suspect'
                  ? 'bg-red-500/20 text-red-300 border-red-500/40'
                  : selectedNode.node_type === 'endpoint'
                  ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                  : 'bg-blue-500/20 text-blue-300 border-blue-500/40'
              }`}>
                {selectedNode.node_type === 'suspect' ? '🚨 Root Suspect' : selectedNode.node_type === 'endpoint' ? '🎯 Endpoint / VASP Candidate' : '🔗 Intermediate Hop'}
              </span>

              <span className="px-2 py-0.5 rounded text-sm font-mono bg-police-900 text-surface-300 border border-police-700">
                Hop Level: {selectedNode.hop}
              </span>
            </div>

            {/* Address Box */}
            <div className="p-3 rounded-lg bg-police-900/90 border border-police-700/80 space-y-1.5">
              <div className="text-sm text-surface-400 uppercase font-semibold">Wallet Address</div>
              <div className="font-mono text-base text-emerald-300 break-all select-all leading-tight">
                {selectedNode.address}
              </div>
              <div className="flex justify-between items-center pt-1">
                <button
                  onClick={() => copyToClipboard(selectedNode.address, 'node-addr')}
                  className="flex items-center gap-1 text-base text-surface-400 hover:text-white transition"
                >
                  {copiedKey === 'node-addr' ? (
                    <>
                      <Check className="h-4 w-4 text-emerald-400" />
                      <span className="text-emerald-400">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="h-4 w-4" />
                      <span>Copy Address</span>
                    </>
                  )}
                </button>
                <a
                  href={`https://tronscan.org/#/address/${selectedNode.address}`}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1 text-base text-brand-blue hover:text-brand-hover transition"
                >
                  <span>TronScan</span>
                  <ExternalLink className="h-4 w-4" />
                </a>
              </div>
            </div>

            {/* Volumes */}
            <div className="p-3 rounded-lg bg-police-900/70 border border-police-700/70 space-y-2.5">
              <div className="text-sm text-surface-400 uppercase font-semibold">Observed Fund Flows</div>
              <div className="grid grid-cols-2 gap-2 text-base">
                <div>
                  <span className="text-sm text-surface-500 block">Total Received</span>
                  <span className="font-mono font-bold text-emerald-300">
                    {formatUsdt(selectedNode.total_received)}
                  </span>
                </div>
                <div>
                  <span className="text-sm text-surface-500 block">Total Sent Out</span>
                  <span className="font-mono font-bold text-red-300">
                    {formatUsdt(selectedNode.total_sent)}
                  </span>
                </div>
              </div>
              <div className="pt-1 border-t border-police-800 flex justify-between items-center text-base">
                <span className="text-surface-400">Observed Transactions:</span>
                <span className="font-mono font-bold text-white">{selectedNode.transaction_count}</span>
              </div>
            </div>

            {/* Action button: Highlight trail */}
            {onHighlightPathToRoot && selectedNode.node_type !== 'suspect' && (
              <button
                onClick={() => onHighlightPathToRoot(selectedNode.address)}
                className="w-full py-2 px-3 rounded-lg bg-brand-blue hover:bg-brand-hover text-white font-semibold text-base transition flex items-center justify-center gap-1.5 shadow-md shadow-blue-500/20 cursor-pointer"
              >
                <Target className="h-4 w-4" />
                Highlight Trail from Suspect
              </button>
            )}
          </div>
        )}

        {/* EDGE DETAILS */}
        {selectedEdge && (
          <div className="space-y-4">
            {/* Edge Badges */}
            <div className="flex items-center justify-between">
              <span className="px-2 py-0.5 rounded text-sm font-bold uppercase bg-amber-500/20 text-amber-300 border border-amber-500/40">
                Hop {selectedEdge.hop} Transfer
              </span>
              <span className="px-2 py-0.5 rounded text-sm font-mono bg-police-900 text-surface-300 border border-police-700">
                {selectedEdge.asset}
              </span>
            </div>

            {/* Amount Banner */}
            <div className="p-3.5 rounded-lg bg-police-900/90 border border-police-700/80 space-y-1">
              <div className="text-sm text-surface-400 uppercase font-semibold">Transfer Value</div>
              <div className="text-2xl font-bold font-mono text-emerald-400">
                {formatUsdt(selectedEdge.amount)}
              </div>
              <div className="text-sm text-surface-500 font-mono">
                Raw units: {selectedEdge.amount_raw.toLocaleString()}
              </div>
            </div>

            {/* From / To Routing */}
            <div className="p-3 rounded-lg bg-police-900/70 border border-police-700/70 space-y-2">
              <div className="text-sm text-surface-400 uppercase font-semibold">Directional Route</div>
              <div className="space-y-1.5 font-mono text-base">
                <div className="flex items-center justify-between">
                  <span className="text-surface-500 text-sm">From:</span>
                  <span className="text-surface-200">{selectedEdge.from_address.slice(0, 10)}...{selectedEdge.from_address.slice(-6)}</span>
                </div>
                <div className="flex justify-center text-surface-600">
                  <ArrowRight className="h-4 w-4" />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-surface-500 text-sm">To:</span>
                  <span className="text-surface-200">{selectedEdge.to_address.slice(0, 10)}...{selectedEdge.to_address.slice(-6)}</span>
                </div>
              </div>
            </div>

            {/* Tx Hash */}
            <div className="p-3 rounded-lg bg-police-900/70 border border-police-700/70 space-y-1.5">
              <div className="text-sm text-surface-400 uppercase font-semibold">Transaction Hash</div>
              <div className="font-mono text-base text-surface-300 break-all select-all leading-tight">
                {selectedEdge.tx_hash}
              </div>
              <div className="flex justify-between items-center pt-1">
                <button
                  onClick={() => copyToClipboard(selectedEdge.tx_hash, 'edge-hash')}
                  className="flex items-center gap-1 text-base text-surface-400 hover:text-white transition"
                >
                  {copiedKey === 'edge-hash' ? (
                    <>
                      <Check className="h-4 w-4 text-emerald-400" />
                      <span className="text-emerald-400">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="h-4 w-4" />
                      <span>Copy TxID</span>
                    </>
                  )}
                </button>
                <a
                  href={`https://tronscan.org/#/transaction/${selectedEdge.tx_hash}`}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1 text-base text-brand-blue hover:text-brand-hover transition"
                >
                  <span>TronScan</span>
                  <ExternalLink className="h-4 w-4" />
                </a>
              </div>
            </div>

            {/* Block & Timestamp */}
            <div className="grid grid-cols-2 gap-2 text-base">
              <div className="p-2.5 rounded-lg bg-police-900/60 border border-police-700/60">
                <span className="text-sm text-surface-500 block">Block Height</span>
                <span className="font-mono font-medium text-surface-300">
                  {selectedEdge.block_number !== null && selectedEdge.block_number !== undefined
                    ? selectedEdge.block_number
                    : 'N/A (Provider Omitted)'}
                </span>
              </div>
              <div className="p-2.5 rounded-lg bg-police-900/60 border border-police-700/60">
                <span className="text-sm text-surface-500 block">Provenance Source</span>
                <span className="font-mono font-medium text-surface-300">{selectedEdge.source}</span>
              </div>
            </div>

            <div className="p-2.5 rounded-lg bg-police-900/60 border border-police-700/60 text-base flex items-center justify-between">
              <span className="text-surface-400">Timestamp:</span>
              <span className="font-mono text-surface-300">{new Date(selectedEdge.timestamp).toLocaleString()}</span>
            </div>
          </div>
        )}
      </div>

      {/* Footer / Section 63 BSA badge */}
      <div className="p-3 border-t border-police-700/80 bg-police-900 flex items-center justify-between text-sm text-surface-400">
        <span className="flex items-center gap-1 text-emerald-400">
          <ShieldCheck className="h-4 w-4" />
          Forensic Integrity Sealed
        </span>
        <span>SIH 2026</span>
      </div>
    </div>
  );
};
