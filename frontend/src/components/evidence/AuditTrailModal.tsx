import React, { useState, useEffect } from 'react';
import { 
  X, 
  ShieldCheck, 
  Clock, 
  User, 
  Hash, 
  Copy, 
  Check, 
  Filter, 
  Loader2,
  AlertCircle
} from 'lucide-react';
import type { AuditEvent } from '../../types/evidence';
import { getCaseAuditEvents } from '../../api/evidence';

interface AuditTrailModalProps {
  isOpen: boolean;
  onClose: () => void;
  caseId: string;
  firNumber: string;
}

export const AuditTrailModal: React.FC<AuditTrailModalProps> = ({
  isOpen,
  onClose,
  caseId,
  firNumber,
}) => {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);
  const [filterType, setFilterType] = useState<string>('ALL');

  useEffect(() => {
    if (!isOpen) return;

    async function fetchAudit() {
      setLoading(true);
      setError(null);
      try {
        const auditLog = await getCaseAuditEvents(caseId);
        setEvents(auditLog);
      } catch (err: any) {
        setError(err.message || 'Failed to fetch audit log');
      } finally {
        setLoading(false);
      }
    }

    fetchAudit();
  }, [isOpen, caseId]);

  if (!isOpen) return null;

  const copyHash = (hash: string) => {
    navigator.clipboard.writeText(hash);
    setCopiedHash(hash);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  const getEventBadgeClass = (eventType: string) => {
    switch (eventType) {
      case 'ATTRIBUTION_ACCEPTED':
        return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30';
      case 'ATTRIBUTION_REJECTED':
        return 'bg-rose-500/20 text-rose-300 border-rose-500/30';
      case 'CASE_OPENED':
        return 'bg-blue-500/20 text-blue-300 border-blue-500/30';
      case 'TRACE_STARTED':
        return 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30';
      case 'ATTRIBUTION_VIEWED':
        return 'bg-amber-500/20 text-amber-300 border-amber-500/30';
      case 'EVIDENCE_REVIEWED':
        return 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30';
      default:
        return 'bg-slate-700/50 text-slate-300 border-slate-600/50';
    }
  };

  const filteredEvents = filterType === 'ALL'
    ? events
    : events.filter(e => e.event_type === filterType);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="w-full max-w-3xl max-h-[85vh] flex flex-col rounded-2xl bg-police-900 border border-police-700 shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-police-800 bg-police-850 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg bg-blue-500/10 border border-blue-500/30 flex items-center justify-center text-blue-400">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-white tracking-wide">Investigator Chain of Custody & Audit Trail</h3>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-police-800 text-slate-300 border border-police-700">
                  {firNumber}
                </span>
              </div>
              <p className="text-[11px] text-slate-400">
                Append-only forensic event log with deterministic SHA-256 tamper-evident integrity hashes
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-police-800 transition"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Filter Bar */}
        <div className="px-6 py-2.5 bg-police-950/60 border-b border-police-800 flex items-center justify-between text-xs">
          <div className="flex items-center gap-2 text-slate-400">
            <Filter className="h-3.5 w-3.5" />
            <span>Filter Action:</span>
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="px-2 py-1 rounded bg-police-900 border border-police-700 text-xs font-medium text-slate-200 focus:outline-none focus:border-blue-500"
            >
              <option value="ALL">All Recorded Actions ({events.length})</option>
              <option value="ATTRIBUTION_ACCEPTED">Attribution Accepted</option>
              <option value="ATTRIBUTION_REJECTED">Attribution Rejected</option>
              <option value="ATTRIBUTION_VIEWED">Attribution Evaluated</option>
              <option value="TRACE_STARTED">Trace Initiated</option>
              <option value="EVIDENCE_REVIEWED">Evidence Reviewed</option>
              <option value="CASE_OPENED">Case Opened</option>
            </select>
          </div>
          <span className="text-[11px] text-slate-400">
            Showing <strong className="text-white">{filteredEvents.length}</strong> events
          </span>
        </div>

        {/* Event List */}
        <div className="flex-1 overflow-y-auto p-6 space-y-3">
          {loading ? (
            <div className="flex flex-col items-center justify-center p-12 space-y-3">
              <Loader2 className="h-6 w-6 text-blue-500 animate-spin" />
              <span className="text-xs text-slate-400">Retrieving append-only audit events...</span>
            </div>
          ) : error ? (
            <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-xs text-red-300 flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 text-red-400" />
              <span>{error}</span>
            </div>
          ) : filteredEvents.length === 0 ? (
            <div className="text-center py-12 text-slate-500 text-xs">
              No audit actions recorded matching this filter.
            </div>
          ) : (
            filteredEvents.map((ev) => (
              <div
                key={ev.id}
                className="p-4 rounded-xl bg-police-850/70 border border-police-700/80 hover:border-police-600 transition space-y-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold tracking-wider border ${getEventBadgeClass(ev.event_type)}`}>
                      {ev.event_type.replace(/_/g, ' ')}
                    </span>
                    <span className="text-xs font-semibold text-slate-200">
                      {ev.action_summary}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 text-[11px] text-slate-400 font-mono shrink-0">
                    <Clock className="h-3 w-3" />
                    <span>{new Date(ev.created_at).toLocaleString()}</span>
                  </div>
                </div>

                <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-police-800 text-[11px]">
                  <div className="flex items-center gap-3 text-slate-400">
                    <span className="flex items-center gap-1">
                      <User className="h-3 w-3 text-slate-500" />
                      Actor: <strong className="text-slate-300 font-mono">{ev.actor_id}</strong>
                    </span>
                    {ev.trace_id && (
                      <span className="text-slate-500">
                        Trace: <span className="font-mono text-slate-400">{ev.trace_id.slice(0, 8)}...</span>
                      </span>
                    )}
                  </div>

                  {/* Tamper-evident Hash */}
                  <div className="flex items-center gap-1.5 font-mono text-[10px] bg-police-950 px-2 py-0.5 rounded border border-police-800 text-slate-400">
                    <Hash className="h-3 w-3 text-blue-400" />
                    <span className="truncate max-w-[200px]" title={ev.content_hash}>
                      {ev.content_hash.slice(0, 16)}...{ev.content_hash.slice(-8)}
                    </span>
                    <button
                      onClick={() => copyHash(ev.content_hash)}
                      className="text-slate-400 hover:text-white transition"
                      title="Copy SHA-256 Hash"
                    >
                      {copiedHash === ev.content_hash ? (
                        <Check className="h-3 w-3 text-emerald-400" />
                      ) : (
                        <Copy className="h-3 w-3" />
                      )}
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-police-800 bg-police-950/60 flex items-center justify-between text-xs text-slate-400">
          <span>All recorded actions comply with Indian Evidence Act & Section 63 BNSS electronic record requirements.</span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-police-800 hover:bg-police-700 text-slate-200 font-medium transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
