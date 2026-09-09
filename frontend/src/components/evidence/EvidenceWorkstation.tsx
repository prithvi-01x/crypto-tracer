import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  Search,
  Filter,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  FileCode,
  Link2,
  History,
  Sparkles,
  Database,
  Calculator,
  UserCheck,
  Loader2,
  RefreshCw
} from 'lucide-react';
import type { EvidenceClassification, EvidenceChain } from '../../types/evidence';
import { getTraceEvidence, reviewAttributionHypothesis, recordAuditEvent } from '../../api/evidence';
import { AuditTrailModal } from './AuditTrailModal';

interface EvidenceWorkstationProps {
  caseId: string;
  traceId: string | null;
  firNumber: string;
}

export const EvidenceWorkstation: React.FC<EvidenceWorkstationProps> = ({
  caseId,
  traceId,
  firNumber,
}) => {
  const [evidenceChain, setEvidenceChain] = useState<EvidenceChain | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedClassification, setSelectedClassification] = useState<EvidenceClassification | 'ALL'>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedPayloadIds, setExpandedPayloadIds] = useState<Set<string>>(new Set());
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  // Human Review Gate state
  const [reviewerId, setReviewerId] = useState('IO-Vikram-742');
  const [reviewNotes, setReviewNotes] = useState('');
  const [reviewSubmitting, setReviewSubmitting] = useState(false);
  const [reviewFeedback, setReviewFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Audit Modal state
  const [isAuditModalOpen, setIsAuditModalOpen] = useState(false);

  // Fetch evidence whenever traceId changes
  useEffect(() => {
    if (!traceId) return;

    async function fetchEvidence() {
      setLoading(true);
      setError(null);
      try {
        const data = await getTraceEvidence(traceId!);
        setEvidenceChain(data);

        // Record automated audit event for investigator viewing evidence
        recordAuditEvent(caseId, {
          trace_id: traceId!,
          event_type: 'EVIDENCE_REVIEWED',
          actor_id: reviewerId,
          action_summary: `Investigator viewed evidence chain and cryptographic DAG for trace ${traceId!.slice(0, 8)}...`,
          metadata: { total_items: data.total_evidence_count },
        }).catch(() => {});
      } catch (err: any) {
        setError(err.message || 'Failed to load evidence chain');
      } finally {
        setLoading(false);
      }
    }

    fetchEvidence();
  }, [traceId, caseId]);

  const handleRefresh = async () => {
    if (!traceId) return;
    setLoading(true);
    try {
      const data = await getTraceEvidence(traceId);
      setEvidenceChain(data);
    } catch (err: any) {
      setError(err.message || 'Failed to refresh evidence chain');
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(text);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  const togglePayload = (id: string) => {
    setExpandedPayloadIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  // Find top attribution candidate from INFERRED items
  const attributionItem = evidenceChain?.items.find(
    (it) => it.classification === 'INFERRED' && it.evidence_type === 'VASP_ATTRIBUTION'
  );
  const attributionCandidateAddress = attributionItem?.payload?.candidate_address || attributionItem?.source_reference;

  // Check if this candidate already has a HUMAN_ACTION review
  const existingReview = evidenceChain?.items.find(
    (it) =>
      it.classification === 'HUMAN_ACTION' &&
      it.evidence_type === 'ATTRIBUTION_REVIEW' &&
      it.parent_evidence_ids?.some((pid) => pid.includes(attributionCandidateAddress?.slice(0, 8) || '---'))
  );

  const handleDecision = async (decision: 'ACCEPT' | 'REJECT') => {
    if (!attributionCandidateAddress || !traceId) return;

    setReviewSubmitting(true);
    setReviewFeedback(null);
    try {
      await reviewAttributionHypothesis(caseId, attributionCandidateAddress, {
        actor_id: reviewerId.trim() || 'investigator',
        decision,
        notes: reviewNotes.trim() || undefined,
        trace_id: traceId,
      });

      setReviewFeedback({
        type: 'success',
        message: `Attribution hypothesis successfully ${decision === 'ACCEPT' ? 'ACCEPTED' : 'REJECTED'}. Cryptographic audit log & Section 63 BSA electronic record updated.`,
      });
      setReviewNotes('');
      // Reload evidence chain to reflect newly created HUMAN_ACTION item
      await handleRefresh();
    } catch (err: any) {
      setReviewFeedback({
        type: 'error',
        message: err.message || 'Failed to record decision gate',
      });
    } finally {
      setReviewSubmitting(false);
    }
  };

  const getClassificationBadge = (cls: EvidenceClassification) => {
    switch (cls) {
      case 'OBSERVED':
        return 'bg-blue-500/20 text-blue-300 border-blue-500/30';
      case 'DERIVED':
        return 'bg-purple-500/20 text-purple-300 border-purple-500/30';
      case 'INFERRED':
        return 'bg-amber-500/20 text-amber-300 border-amber-500/30';
      case 'HUMAN_ACTION':
        return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30';
      default:
        return 'bg-slate-700/50 text-slate-300 border-slate-600/50';
    }
  };

  const filteredItems = (evidenceChain?.items || []).filter((item) => {
    if (selectedClassification !== 'ALL' && item.classification !== selectedClassification) {
      return false;
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchTitle = item.title.toLowerCase().includes(q);
      const matchDesc = item.description?.toLowerCase().includes(q);
      const matchHash = item.content_hash.toLowerCase().includes(q);
      const matchRef = item.source_reference?.toLowerCase().includes(q);
      const matchType = item.evidence_type.toLowerCase().includes(q);
      return matchTitle || matchDesc || matchHash || matchRef || matchType;
    }
    return true;
  });

  if (!traceId) {
    return (
      <div className="h-96 rounded-2xl bg-police-900 border border-police-700 flex flex-col items-center justify-center p-8 text-center space-y-3">
        <ShieldCheck className="h-10 w-10 text-slate-500" />
        <h3 className="text-sm font-semibold text-white">No Active Trace Selected</h3>
        <p className="text-xs text-slate-400 max-w-sm">
          Run or select an existing trace from the dropdown above to inspect verifiable evidence, provenance DAGs, and attribution decision gates.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Four-Tier Provenance Pipeline Header */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        {/* Tier 1 */}
        <div
          onClick={() => setSelectedClassification('OBSERVED')}
          className={`p-3.5 rounded-xl border transition cursor-pointer flex items-start justify-between ${
            selectedClassification === 'OBSERVED'
              ? 'bg-blue-950/40 border-blue-500 shadow-md shadow-blue-500/10'
              : 'bg-police-900/90 border-police-700/80 hover:border-slate-600'
          }`}
        >
          <div className="space-y-1">
            <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-blue-400">
              <Database className="h-3 w-3" />
              <span>Tier 1: Observed</span>
            </div>
            <div className="text-xs font-semibold text-white">On-Chain Facts</div>
            <p className="text-[11px] text-slate-400">Raw transfers, explorer timestamps & blocks</p>
          </div>
          <span className="px-2 py-0.5 rounded text-xs font-mono font-bold bg-blue-500/20 text-blue-300 border border-blue-500/30">
            {evidenceChain?.observed_count || 0}
          </span>
        </div>

        {/* Tier 2 */}
        <div
          onClick={() => setSelectedClassification('DERIVED')}
          className={`p-3.5 rounded-xl border transition cursor-pointer flex items-start justify-between ${
            selectedClassification === 'DERIVED'
              ? 'bg-purple-950/40 border-purple-500 shadow-md shadow-purple-500/10'
              : 'bg-police-900/90 border-police-700/80 hover:border-slate-600'
          }`}
        >
          <div className="space-y-1">
            <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-purple-400">
              <Calculator className="h-3 w-3" />
              <span>Tier 2: Derived</span>
            </div>
            <div className="text-xs font-semibold text-white">Structural Metrics</div>
            <p className="text-[11px] text-slate-400">Hops, sweep % ratio, fan-in & temporal delay</p>
          </div>
          <span className="px-2 py-0.5 rounded text-xs font-mono font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30">
            {evidenceChain?.derived_count || 0}
          </span>
        </div>

        {/* Tier 3 */}
        <div
          onClick={() => setSelectedClassification('INFERRED')}
          className={`p-3.5 rounded-xl border transition cursor-pointer flex items-start justify-between ${
            selectedClassification === 'INFERRED'
              ? 'bg-amber-950/40 border-amber-500 shadow-md shadow-amber-500/10'
              : 'bg-police-900/90 border-police-700/80 hover:border-slate-600'
          }`}
        >
          <div className="space-y-1">
            <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-amber-400">
              <Sparkles className="h-3 w-3" />
              <span>Tier 3: Inferred</span>
            </div>
            <div className="text-xs font-semibold text-white">VASP Hypotheses</div>
            <p className="text-[11px] text-slate-400">Attribution scoring & candidate confidence</p>
          </div>
          <span className="px-2 py-0.5 rounded text-xs font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
            {evidenceChain?.inferred_count || 0}
          </span>
        </div>

        {/* Tier 4 */}
        <div
          onClick={() => setSelectedClassification('HUMAN_ACTION')}
          className={`p-3.5 rounded-xl border transition cursor-pointer flex items-start justify-between ${
            selectedClassification === 'HUMAN_ACTION'
              ? 'bg-emerald-950/40 border-emerald-500 shadow-md shadow-emerald-500/10'
              : 'bg-police-900/90 border-police-700/80 hover:border-slate-600'
          }`}
        >
          <div className="space-y-1">
            <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-emerald-400">
              <UserCheck className="h-3 w-3" />
              <span>Tier 4: Decision</span>
            </div>
            <div className="text-xs font-semibold text-white">Human Gate</div>
            <p className="text-[11px] text-slate-400">Investigator reviews & electronic audit trail</p>
          </div>
          <span className="px-2 py-0.5 rounded text-xs font-mono font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
            {evidenceChain?.human_action_count || 0}
          </span>
        </div>
      </div>

      {/* Human Investigator Decision Gate Box */}
      {attributionItem && (
        <div className="p-5 rounded-xl bg-police-900 border border-police-700 shadow-xl space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-police-800">
            <div className="flex items-center gap-2">
              <div className="h-8 w-8 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400">
                <ShieldCheck className="h-4 w-4" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
                  Human-in-the-Loop Decision Gate
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-police-800 text-amber-300 border border-amber-500/30">
                    Confidence: {attributionItem.payload?.confidence_percentage}% ({attributionItem.payload?.confidence_band})
                  </span>
                </h4>
                <p className="text-[11px] text-slate-400">
                  Target: <span className="font-mono text-slate-200">{attributionCandidateAddress}</span> &rarr; Attributed VASP: <strong className="text-amber-300">{attributionItem.payload?.vasp_name}</strong>
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setIsAuditModalOpen(true)}
                className="flex items-center gap-1 px-3 py-1 rounded-lg bg-police-800 hover:bg-police-700 border border-police-700 text-xs font-medium text-slate-300 hover:text-white transition"
              >
                <History className="h-3.5 w-3.5 text-blue-400" />
                <span>View Case Audit Log</span>
              </button>
            </div>
          </div>

          {/* Mandatory Legal Notice */}
          <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-start gap-2.5 text-xs text-amber-200">
            <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
            <div className="space-y-0.5 text-[11px] leading-relaxed">
              <span className="font-semibold text-amber-300">Statutory Compliance & Evidentiary Disclaimer:</span>
              <p className="text-amber-200/90">
                {attributionItem.payload?.disclaimer ||
                  'Attribution is an automated investigative hypothesis based on observable on-chain transaction patterns, not legal proof of account ownership.'}
              </p>
            </div>
          </div>

          {/* Decision Form or Existing Decision Display */}
          {existingReview ? (
            <div className="p-4 rounded-xl bg-police-950/70 border border-emerald-500/30 flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                {existingReview.payload?.decision === 'ACCEPT' ? (
                  <CheckCircle2 className="h-6 w-6 text-emerald-400 shrink-0" />
                ) : (
                  <XCircle className="h-6 w-6 text-rose-400 shrink-0" />
                )}
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-white">
                      Investigator Formally {existingReview.payload?.decision === 'ACCEPT' ? 'ACCEPTED' : 'REJECTED'} Attribution Hypothesis
                    </span>
                    <span className="text-[10px] font-mono px-1.5 py-0.2 bg-emerald-500/20 text-emerald-300 rounded border border-emerald-500/30">
                      Verified
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-300 mt-0.5">
                    {existingReview.description || existingReview.payload?.action_summary}
                  </p>
                  <div className="text-[10px] text-slate-500 font-mono mt-1">
                    Actor: {existingReview.payload?.actor_id || 'investigator'} | Hash: {existingReview.content_hash.slice(0, 16)}...
                  </div>
                </div>
              </div>
              <span className="text-xs text-slate-400 font-mono shrink-0">
                {new Date(existingReview.created_at).toLocaleString()}
              </span>
            </div>
          ) : (
            <div className="space-y-3 pt-1">
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                <div>
                  <label className="text-[10px] text-slate-400 uppercase font-semibold block mb-1">
                    Investigating Officer (IO) ID
                  </label>
                  <input
                    type="text"
                    value={reviewerId}
                    onChange={(e) => setReviewerId(e.target.value)}
                    className="w-full px-3 py-1.5 rounded-lg bg-police-950 border border-police-700 text-xs font-mono text-slate-200 focus:outline-none focus:border-blue-500"
                    placeholder="IO-ID"
                  />
                </div>
                <div className="md:col-span-3">
                  <label className="text-[10px] text-slate-400 uppercase font-semibold block mb-1">
                    Evidentiary Justification & Case Notes (Section 63 BSA)
                  </label>
                  <input
                    type="text"
                    value={reviewNotes}
                    onChange={(e) => setReviewNotes(e.target.value)}
                    className="w-full px-3 py-1.5 rounded-lg bg-police-950 border border-police-700 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
                    placeholder="E.g. Rapid 99.5% sweep into verified Binance hot wallet within 15 mins confirmed. Notice preparation authorized."
                  />
                </div>
              </div>

              {reviewFeedback && (
                <div
                  className={`p-3 rounded-lg text-xs flex items-center gap-2 ${
                    reviewFeedback.type === 'success'
                      ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-300'
                      : 'bg-red-500/10 border border-red-500/30 text-red-300'
                  }`}
                >
                  {reviewFeedback.type === 'success' ? (
                    <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
                  ) : (
                    <XCircle className="h-4 w-4 text-red-400 shrink-0" />
                  )}
                  <span>{reviewFeedback.message}</span>
                </div>
              )}

              <div className="flex items-center justify-end gap-2.5 pt-2">
                <button
                  onClick={() => handleDecision('REJECT')}
                  disabled={reviewSubmitting}
                  className="px-4 py-2 rounded-lg bg-police-800 hover:bg-rose-950/60 border border-police-700 hover:border-rose-600 text-rose-300 font-semibold text-xs transition cursor-pointer disabled:opacity-50"
                >
                  Reject / Mark Inconclusive
                </button>
                <button
                  onClick={() => handleDecision('ACCEPT')}
                  disabled={reviewSubmitting}
                  className="px-5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs transition shadow-lg shadow-emerald-600/20 flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                >
                  {reviewSubmitting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <CheckCircle2 className="h-4 w-4" />
                  )}
                  <span>Accept Attribution Hypothesis</span>
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Evidence Toolbar & Search */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-xl bg-police-900 border border-police-700/80">
        <div className="flex items-center gap-2 flex-wrap text-xs">
          <span className="text-slate-400 font-medium mr-1 flex items-center gap-1">
            <Filter className="h-3.5 w-3.5" />
            Filter:
          </span>
          {(['ALL', 'OBSERVED', 'DERIVED', 'INFERRED', 'HUMAN_ACTION'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setSelectedClassification(tab)}
              className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition ${
                selectedClassification === tab
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'bg-police-800 text-slate-300 hover:text-white hover:bg-police-750'
              }`}
            >
              {tab.replace('_', ' ')}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="h-3.5 w-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search hashes, titles, addresses..."
              className="pl-8 pr-3 py-1 rounded-lg bg-police-950 border border-police-700 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500 w-60"
            />
          </div>

          <button
            onClick={handleRefresh}
            className="p-1.5 rounded-lg bg-police-800 hover:bg-police-700 text-slate-300 hover:text-white transition"
            title="Refresh Evidence"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Evidence Items List */}
      <div className="space-y-3">
        {loading && !evidenceChain ? (
          <div className="flex flex-col items-center justify-center p-16 space-y-3">
            <Loader2 className="h-8 w-8 text-blue-500 animate-spin" />
            <span className="text-xs text-slate-400">Verifying immutable evidence records & DAG provenance...</span>
          </div>
        ) : error ? (
          <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-xs text-red-300">
            {error}
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="p-12 rounded-xl bg-police-900/60 border border-police-700/60 text-center text-xs text-slate-400">
            No evidence records found matching the active filter.
          </div>
        ) : (
          filteredItems.map((item) => {
            const isPayloadOpen = expandedPayloadIds.has(item.id);
            return (
              <div
                key={item.id}
                className="p-4 rounded-xl bg-police-900 border border-police-700/80 hover:border-police-600 transition space-y-3"
              >
                {/* Header */}
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-semibold tracking-wider border ${getClassificationBadge(
                          item.classification
                        )}`}
                      >
                        {item.classification}
                      </span>
                      <span className="text-[10px] font-mono text-slate-400 bg-police-950 px-2 py-0.5 rounded border border-police-800">
                        {item.evidence_type}
                      </span>
                      <span className="text-xs text-slate-500">via {item.source}</span>
                    </div>
                    <h4 className="text-xs font-bold text-white tracking-wide">{item.title}</h4>
                  </div>

                  {/* Hash Pill */}
                  <div className="flex items-center gap-1.5 font-mono text-[10px] bg-police-950 px-2.5 py-1 rounded-md border border-police-800 text-slate-400">
                    <span className="text-blue-400 font-semibold">SHA256:</span>
                    <span className="truncate max-w-[140px]" title={item.content_hash}>
                      {item.content_hash.slice(0, 12)}...{item.content_hash.slice(-6)}
                    </span>
                    <button
                      onClick={() => copyToClipboard(item.content_hash)}
                      className="text-slate-400 hover:text-white transition"
                      title="Copy SHA-256 Hash"
                    >
                      {copiedHash === item.content_hash ? (
                        <Check className="h-3 w-3 text-emerald-400" />
                      ) : (
                        <Copy className="h-3 w-3" />
                      )}
                    </button>
                  </div>
                </div>

                {/* Description */}
                {item.description && (
                  <p className="text-xs text-slate-300 leading-relaxed bg-police-950/40 p-2.5 rounded-lg border border-police-800/60">
                    {item.description}
                  </p>
                )}

                {/* Provenance DAG Links */}
                {item.parent_evidence_ids && item.parent_evidence_ids.length > 0 && (
                  <div className="flex items-center gap-2 text-[11px] text-slate-400 flex-wrap">
                    <Link2 className="h-3.5 w-3.5 text-purple-400 shrink-0" />
                    <span className="font-semibold text-slate-300">Precursor Evidence:</span>
                    {item.parent_evidence_ids.map((pid) => (
                      <span
                        key={pid}
                        className="px-2 py-0.5 rounded font-mono text-[10px] bg-police-950 text-purple-300 border border-purple-500/20"
                      >
                        {pid}
                      </span>
                    ))}
                  </div>
                )}

                {/* Footer Bar & Payload Toggle */}
                <div className="pt-2 border-t border-police-800 flex flex-wrap items-center justify-between text-[11px] text-slate-400 gap-2">
                  <div className="flex items-center gap-3">
                    <span>
                      Collected: <strong className="text-slate-300 font-mono">{new Date(item.collected_at).toLocaleTimeString()}</strong>
                    </span>
                    {item.source_reference && (
                      <span className="truncate max-w-[240px]">
                        Ref: <span className="font-mono text-slate-300">{item.source_reference}</span>
                      </span>
                    )}
                  </div>

                  <button
                    onClick={() => togglePayload(item.id)}
                    className="flex items-center gap-1 text-[11px] text-blue-400 hover:text-blue-300 transition"
                  >
                    <FileCode className="h-3.5 w-3.5" />
                    <span>{isPayloadOpen ? 'Hide Payload' : 'Inspect JSON Payload'}</span>
                    {isPayloadOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                  </button>
                </div>

                {/* Collapsible JSON Payload */}
                {isPayloadOpen && (
                  <div className="mt-2 p-3 rounded-lg bg-police-950 border border-police-800 font-mono text-[11px] text-emerald-300 overflow-x-auto">
                    <pre>{JSON.stringify(item.payload, null, 2)}</pre>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Case Audit Trail Modal */}
      <AuditTrailModal
        isOpen={isAuditModalOpen}
        onClose={() => setIsAuditModalOpen(false)}
        caseId={caseId}
        firNumber={firNumber}
      />
    </div>
  );
};
