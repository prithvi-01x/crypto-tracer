import React, { useState } from 'react';
import { 
  X, 
  FilterX, 
  ShieldCheck, 
  Copy, 
  Check, 
  Search, 
  AlertTriangle,
  ArrowRight
} from 'lucide-react';
import type { PrunedRecord } from '../../types/graph';

interface PruningDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  records: PrunedRecord[];
  minThreshold: number;
}

export const PruningDrawer: React.FC<PruningDrawerProps> = ({
  isOpen,
  onClose,
  records,
  minThreshold,
}) => {
  const [copiedHash, setCopiedHash] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');

  if (!isOpen) return null;

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(id);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  const dustCount = records.filter(r => r.reason === 'DUST').length;
  const branchCount = records.filter(r => r.reason === 'BRANCH_LIMIT_EXCEEDED').length;
  const assetMismatchCount = records.filter(r => r.reason === 'ASSET_MISMATCH').length;

  const filteredRecords = records.filter(r => 
    r.tx_hash.toLowerCase().includes(searchTerm.toLowerCase()) ||
    r.from_address.toLowerCase().includes(searchTerm.toLowerCase()) ||
    r.to_address.toLowerCase().includes(searchTerm.toLowerCase()) ||
    r.reason.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-black/50 backdrop-blur-sm flex justify-end">
      <div 
        className="w-full max-w-2xl bg-surface-default dark:bg-surface-100 border-l border-surface-200 dark:border-surface-300 shadow-2xl flex flex-col h-full animate-in slide-in-from-right duration-200 text-surface-800 dark:text-surface-100"
      >
        {/* Drawer Header */}
        <div className="p-4 border-b border-surface-200 dark:border-surface-300 flex items-center justify-between bg-surface-50 dark:bg-surface-200/50">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-purple-500/10 border border-purple-500/30 flex items-center justify-center">
              <FilterX className="h-4 w-4 text-purple-600 dark:text-purple-400" />
            </div>
            <div>
              <h2 className="text-base font-bold text-surface-800 dark:text-surface-100 uppercase tracking-wider flex items-center gap-2">
                Forensic Pruning Audit Log
                <span className="text-xs px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-700 dark:text-purple-300 border border-purple-500/30 font-mono">
                  {records.length} Filtered
                </span>
              </h2>
              <p className="text-xs text-surface-500">
                Transparent accounting of low-value and non-relevant blockchain noise
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-surface-400 hover:text-surface-700 dark:hover:text-surface-200 hover:bg-surface-200/60 transition"
            aria-label="Close Pruning Log"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Breakdown Stats */}
        <div className="p-4 border-b border-surface-200 dark:border-surface-300 grid grid-cols-3 gap-3 bg-surface-default dark:bg-surface-100">
          <div className="p-2.5 rounded-lg bg-surface-50 dark:bg-surface-200/50 border border-surface-200 dark:border-surface-300">
            <div className="text-[10px] text-surface-500 font-semibold uppercase">Dust Filtered</div>
            <div className="text-lg font-bold font-mono text-purple-700 dark:text-purple-300 mt-0.5">{dustCount}</div>
            <div className="text-[10px] text-surface-400 mt-0.5">&lt; ${minThreshold.toFixed(2)} USDT</div>
          </div>
          <div className="p-2.5 rounded-lg bg-surface-50 dark:bg-surface-200/50 border border-surface-200 dark:border-surface-300">
            <div className="text-[10px] text-surface-500 font-semibold uppercase">Branch Limit Hit</div>
            <div className="text-lg font-bold font-mono text-amber-600 dark:text-amber-400 mt-0.5">{branchCount}</div>
            <div className="text-[10px] text-surface-400 mt-0.5">Ranked beyond max branch</div>
          </div>
          <div className="p-2.5 rounded-lg bg-surface-50 dark:bg-surface-200/50 border border-surface-200 dark:border-surface-300">
            <div className="text-[10px] text-surface-500 font-semibold uppercase">Asset Mismatch</div>
            <div className="text-lg font-bold font-mono text-blue-600 dark:text-blue-400 mt-0.5">{assetMismatchCount}</div>
            <div className="text-[10px] text-surface-400 mt-0.5">Non-USDT tokens</div>
          </div>
        </div>

        {/* Legal Evidence Banner */}
        <div className="px-4 py-2 bg-blue-50 dark:bg-blue-950/30 border-b border-blue-200 dark:border-blue-900/40 flex items-center gap-2 text-xs text-blue-800 dark:text-blue-300">
          <ShieldCheck className="h-4 w-4 text-brand-blue dark:text-blue-400 shrink-0" />
          <span>Section 63 BSA compliance: Pruned records retained with cryptographic proof for forensic auditability.</span>
        </div>

        {/* Search Input */}
        <div className="p-3 border-b border-surface-200 dark:border-surface-300 bg-surface-50 dark:bg-surface-200/40">
          <div className="relative">
            <Search className="h-4 w-4 text-surface-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search by transaction hash, wallet address or reason..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 text-xs bg-surface-default dark:bg-surface-100 border border-surface-200 dark:border-surface-300 rounded-lg text-surface-800 dark:text-surface-100 placeholder:text-surface-400 focus:outline-none focus:border-brand-blue"
            />
          </div>
        </div>

        {/* Records Table / List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2.5 divide-y divide-surface-200 dark:divide-surface-300">
          {filteredRecords.length === 0 ? (
            <div className="p-8 text-center text-surface-400 space-y-2">
              <AlertTriangle className="h-8 w-8 text-surface-400 mx-auto" />
              <p className="text-xs">No pruned transaction records matched your search filter.</p>
            </div>
          ) : (
            filteredRecords.map((r, i) => (
              <div key={`${r.tx_hash}-${i}`} className="pt-2.5 text-xs space-y-1.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-surface-700 dark:text-surface-300 font-medium">
                      {r.tx_hash.slice(0, 10)}...{r.tx_hash.slice(-8)}
                    </span>
                    <button
                      onClick={() => copyToClipboard(r.tx_hash, `tx-${i}`)}
                      className="text-surface-400 hover:text-surface-700 dark:hover:text-surface-200 transition"
                      title="Copy Tx Hash"
                    >
                      {copiedHash === `tx-${i}` ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
                    </button>
                    <span className="px-1.5 py-0.2 text-[10px] font-mono rounded bg-surface-100 dark:bg-surface-200 text-surface-600 dark:text-surface-300 border border-surface-200 dark:border-surface-300">
                      Hop {r.hop}
                    </span>
                  </div>

                  <span className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${
                    r.reason === 'DUST' 
                      ? 'bg-purple-50 dark:bg-purple-950/40 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-800' 
                      : r.reason === 'BRANCH_LIMIT_EXCEEDED'
                      ? 'bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800'
                      : 'bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800'
                  }`}>
                    {r.reason}
                  </span>
                </div>

                <div className="flex items-center justify-between text-surface-500 text-xs font-mono">
                  <div className="flex items-center gap-1.5">
                    <span>{r.from_address.slice(0, 6)}...{r.from_address.slice(-4)}</span>
                    <ArrowRight className="h-3.5 w-3.5 text-surface-400" />
                    <span>{r.to_address.slice(0, 6)}...{r.to_address.slice(-4)}</span>
                  </div>
                  <div className="font-bold text-surface-800 dark:text-surface-100">
                    {typeof r.amount === 'number' ? r.amount.toFixed(4) : r.amount} USDT
                  </div>
                </div>

                <div className="flex items-center justify-between text-[11px] text-surface-400 pt-0.5">
                  <span>Threshold applied: {typeof r.threshold === 'number' ? r.threshold.toFixed(2) : r.threshold}</span>
                  <span>{new Date(r.timestamp).toLocaleString()} • {r.source}</span>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="p-3 border-t border-surface-200 dark:border-surface-300 bg-surface-50 dark:bg-surface-200/50 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-surface-200 dark:bg-surface-300 hover:bg-surface-300 dark:hover:bg-surface-400 text-xs font-semibold text-surface-800 dark:text-surface-100 transition"
          >
            Close Audit Log
          </button>
        </div>
      </div>
    </div>
  );
};
