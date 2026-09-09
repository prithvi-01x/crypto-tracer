import { useState } from 'react';
import { 
  X, 
  FilePlus, 
  Sparkles, 
  AlertCircle, 
  ArrowRight,
  Wallet
} from 'lucide-react';
import type { CaseCreateInput } from '../../types/case';
import { createCase } from '../../api/cases';

interface NewCaseModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (caseId: string) => void;
}

export const NewCaseModal: React.FC<NewCaseModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const [firNumber, setFirNumber] = useState('');
  const [victimReference, setVictimReference] = useState('');
  const [lossAmountInr, setLossAmountInr] = useState('');
  const [ackNumber, setAckNumber] = useState('');
  const [suspectWallet, setSuspectWallet] = useState('');
  const [chain, setChain] = useState('TRON');
  const [asset, setAsset] = useState('TRC20:USDT');
  const [notes, setNotes] = useState('');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handlePrefillDemo = () => {
    setFirNumber('2026/812');
    setVictimReference('RAMESH-001 (Ramesh Kumar)');
    setLossAmountInr('500000');
    setAckNumber('1930-DL-2026-812');
    setSuspectWallet('TYDZSxdBzWnCuB4jF3K6j5X3qW7b9X1234');
    setChain('TRON');
    setAsset('TRC20:USDT');
    setNotes('Victim contacted via Telegram "VIP Investment Club". Transferred ₹5,00,000 via local P2P/UPI converted to 5,500 USDT sent to suspect unhosted TRON wallet.');
    setError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!firNumber.trim()) {
      setError('FIR Number is required.');
      return;
    }

    setLoading(true);
    setError(null);

    const payload: CaseCreateInput = {
      fir_number: firNumber.trim(),
      victim_reference: victimReference.trim() || undefined,
      loss_amount_inr: lossAmountInr ? parseFloat(lossAmountInr) : undefined,
      ack_number: ackNumber.trim() || undefined,
      suspect_wallet: suspectWallet.trim() || undefined,
      chain,
      asset,
      notes: notes.trim() || undefined,
    };

    try {
      const created = await createCase(payload);
      onSuccess(created.id);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to register case');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm overflow-y-auto">
      <div className="bg-police-800 border border-police-600 rounded-xl shadow-2xl max-w-2xl w-full my-8 overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-police-700 flex items-center justify-between bg-police-900/60">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-blue-600/20 border border-blue-500/30 text-blue-400">
              <FilePlus className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white tracking-wide">New Crypto Investigation Intake</h2>
              <p className="text-xs text-slate-400">Register incident metadata and target suspect wallet</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handlePrefillDemo}
              className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 hover:bg-amber-500/30 transition"
              title="Populate with SIH demo case data"
            >
              <Sparkles className="h-3.5 w-3.5" />
              Demo Data
            </button>
            <button
              onClick={onClose}
              className="p-1 rounded-lg hover:bg-police-700 text-slate-400 hover:text-white transition"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Error Notification */}
        {error && (
          <div className="mx-6 mt-4 p-3 rounded-lg bg-red-950/60 border border-red-800 text-red-200 text-xs flex items-center gap-2">
            <AlertCircle className="h-4 w-4 text-red-400 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4 overflow-y-auto flex-1">
          {/* Section 1: Legal / Case ID */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                FIR / Case Number <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                required
                placeholder="e.g. 2026/812"
                value={firNumber}
                onChange={(e) => setFirNumber(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-police-900 border border-police-700 text-white placeholder-slate-500 text-xs focus:outline-none focus:border-blue-500 font-mono"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                1930 Portal Acknowledgement No.
              </label>
              <input
                type="text"
                placeholder="e.g. 1930-DL-2026-812"
                value={ackNumber}
                onChange={(e) => setAckNumber(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-police-900 border border-police-700 text-white placeholder-slate-500 text-xs focus:outline-none focus:border-blue-500 font-mono"
              />
            </div>
          </div>

          {/* Section 2: Victim & Financials */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                Complainant / Victim Reference
              </label>
              <input
                type="text"
                placeholder="e.g. Ramesh Kumar (RAMESH-001)"
                value={victimReference}
                onChange={(e) => setVictimReference(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-police-900 border border-police-700 text-white placeholder-slate-500 text-xs focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                Reported Loss Amount (INR)
              </label>
              <div className="relative">
                <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-slate-500 text-xs">₹</span>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  placeholder="500000.00"
                  value={lossAmountInr}
                  onChange={(e) => setLossAmountInr(e.target.value)}
                  className="w-full pl-7 pr-3 py-2 rounded-lg bg-police-900 border border-police-700 text-white placeholder-slate-500 text-xs focus:outline-none focus:border-blue-500 font-mono"
                />
              </div>
            </div>
          </div>

          {/* Section 3: Target Wallet & Chain */}
          <div className="pt-2 border-t border-police-700/60">
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
              Suspect Cryptocurrency Wallet Address or Transaction ID
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-500">
                <Wallet className="h-4 w-4" />
              </div>
              <input
                type="text"
                placeholder="TRON Address (starts with T...) or Tx Hash"
                value={suspectWallet}
                onChange={(e) => setSuspectWallet(e.target.value)}
                className="w-full pl-9 pr-3 py-2 rounded-lg bg-police-900 border border-police-700 text-emerald-300 font-mono text-xs focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          {/* Chain & Asset Selection */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5 flex items-center justify-between">
                <span>Target Blockchain</span>
                <span className="text-[10px] text-amber-400 font-normal">SIH P0: TRON</span>
              </label>
              <select
                value={chain}
                onChange={(e) => setChain(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-police-900 border border-police-700 text-white text-xs focus:outline-none focus:border-blue-500"
              >
                <option value="TRON">TRON (Mainnet) - Active</option>
                <option value="ETHEREUM" disabled>Ethereum (EVM) - Phase 12 Roadmap</option>
                <option value="BITCOIN" disabled>Bitcoin (UTXO) - Phase 12 Roadmap</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5 flex items-center justify-between">
                <span>Asset / Token Standard</span>
                <span className="text-[10px] text-emerald-400 font-normal">Primary: TRC-20</span>
              </label>
              <select
                value={asset}
                onChange={(e) => setAsset(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-police-900 border border-police-700 text-white text-xs focus:outline-none focus:border-blue-500"
              >
                <option value="TRC20:USDT">USDT (TRC-20 Tether USD)</option>
                <option value="TRX" disabled>TRX (Native TRON - Roadmap)</option>
              </select>
            </div>
          </div>

          {/* Section 4: Investigation Notes */}
          <div className="pt-2 border-t border-police-700/60">
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
              Investigation Notes & Modus Operandi
            </label>
            <textarea
              rows={3}
              placeholder="Record preliminary details, fraudulent Telegram links, phishing domains, or syndicate notes..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-police-900 border border-police-700 text-white placeholder-slate-500 text-xs focus:outline-none focus:border-blue-500"
            />
          </div>
        </form>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-police-700 bg-police-900/60 flex items-center justify-between">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold rounded-lg bg-police-700 hover:bg-police-600 text-slate-200 transition"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={loading}
            className="flex items-center gap-2 px-5 py-2 text-xs font-bold rounded-lg bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-500/20 transition disabled:opacity-50"
          >
            {loading ? 'Persisting to PostgreSQL...' : 'Register Investigation Case'}
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
