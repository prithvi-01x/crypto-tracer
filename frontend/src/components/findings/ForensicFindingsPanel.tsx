import React, { useState } from 'react';
import {
  AlertTriangle,
  ShieldAlert,
  Info,
  CheckCircle2,
  ExternalLink,
  FileCheck,
  Building2,
  Layers,
  Search,
  Check,
  Copy,
  ChevronDown,
  ChevronUp,
  Loader2
} from 'lucide-react';
import type { ForensicFindingItem, FindingSeverity, FindingStatus } from '../../types/findings';
import { reviewFinding } from '../../api/findings';

interface ForensicFindingsPanelProps {
  caseId: string;
  findings: ForensicFindingItem[];
  loading?: boolean;
  onRefresh?: () => void;
  onViewOnGraph?: (addressOrId: string) => void;
  onViewEvidence?: (evidenceId: string) => void;
  compactMode?: boolean;
}

export const ForensicFindingsPanel: React.FC<ForensicFindingsPanelProps> = ({
  caseId,
  findings,
  loading = false,
  onRefresh,
  onViewOnGraph,
  onViewEvidence,
  compactMode = false,
}) => {
  const [statusFilter, setStatusFilter] = useState<'ALL' | FindingStatus>('ALL');
  const [severityFilter, setSeverityFilter] = useState<'ALL' | FindingSeverity>('ALL');
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [copiedText, setCopiedText] = useState<string | null>(null);

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedText(text);
    setTimeout(() => setCopiedText(null), 2000);
  };

  const handleStatusChange = async (finding: ForensicFindingItem, newStatus: FindingStatus) => {
    setUpdatingId(finding.finding_id);
    try {
      await reviewFinding(caseId, finding.finding_id, {
        status: newStatus,
        notes: `Status updated to ${newStatus} by investigator`,
      });
      if (onRefresh) {
        onRefresh();
      }
    } catch (err) {
      console.error('Failed to update finding status:', err);
    } finally {
      setUpdatingId(null);
    }
  };

  const filtered = findings.filter((f) => {
    if (statusFilter !== 'ALL' && f.status !== statusFilter) return false;
    if (severityFilter !== 'ALL' && f.severity !== severityFilter) return false;
    return true;
  });

  const getSeverityBadge = (severity: FindingSeverity) => {
    switch (severity) {
      case 'CRITICAL':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-xs font-bold bg-red-100 text-red-800 dark:bg-red-950/60 dark:text-red-400 border border-red-200 dark:border-red-800">
            <ShieldAlert className="h-3 w-3" />
            CRITICAL
          </span>
        );
      case 'HIGH':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-xs font-bold bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-400 border border-amber-200 dark:border-amber-800">
            <AlertTriangle className="h-3 w-3" />
            HIGH
          </span>
        );
      case 'MEDIUM':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-xs font-bold bg-blue-100 text-blue-800 dark:bg-blue-950/60 dark:text-blue-400 border border-blue-200 dark:border-blue-800">
            <Layers className="h-3 w-3" />
            MEDIUM
          </span>
        );
      case 'LOW':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-xs font-bold bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
            <Info className="h-3 w-3" />
            LOW
          </span>
        );
      case 'INFO':
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-xs font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">
            <CheckCircle2 className="h-3 w-3" />
            INFO
          </span>
        );
    }
  };

  const getStatusBadge = (status: FindingStatus) => {
    switch (status) {
      case 'REVIEWED':
        return (
          <span className="px-2 py-0.5 rounded text-xs font-semibold bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
            REVIEWED
          </span>
        );
      case 'DISMISSED':
        return (
          <span className="px-2 py-0.5 rounded text-xs font-semibold bg-surface-200 text-surface-600 dark:bg-surface-800 dark:text-surface-400 border border-surface-300 dark:border-surface-700">
            DISMISSED
          </span>
        );
      case 'OPEN':
      default:
        return (
          <span className="px-2 py-0.5 rounded text-xs font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
            OPEN
          </span>
        );
    }
  };

  const openCount = findings.filter(f => f.status === 'OPEN').length;
  const highCount = findings.filter(f => f.severity === 'HIGH' || f.severity === 'CRITICAL').length;

  return (
    <div className={`flex flex-col h-full bg-surface-default border border-surface-200 rounded-xl overflow-hidden shadow-sm ${compactMode ? 'text-sm' : ''}`}>
      {/* Header */}
      <div className="p-4 border-b border-surface-200 bg-surface-50 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400">
            <ShieldAlert className="h-5 w-5" />
          </div>
          <div>
            <h2 className="font-semibold text-lg text-surface-900 flex items-center gap-2">
              Forensic Findings & Alerts
              <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300">
                {findings.length}
              </span>
            </h2>
            <p className="text-xs text-surface-500">
              {openCount} active investigations &bull; {highCount} high-priority signals
            </p>
          </div>
        </div>

        {/* Filter controls */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Status filter */}
          <div className="flex items-center rounded-lg border border-surface-200 bg-surface-default p-0.5 text-xs font-medium text-surface-600">
            {(['ALL', 'OPEN', 'REVIEWED', 'DISMISSED'] as const).map((st) => (
              <button
                key={st}
                onClick={() => setStatusFilter(st)}
                className={`px-2 py-1 rounded transition ${
                  statusFilter === st
                    ? 'bg-brand-blue text-white shadow-xs'
                    : 'hover:text-surface-900'
                }`}
              >
                {st}
              </button>
            ))}
          </div>

          {/* Severity filter */}
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value as 'ALL' | FindingSeverity)}
            className="text-xs bg-surface-default border border-surface-200 text-surface-700 rounded-lg px-2 py-1 focus:outline-none focus:border-brand-blue"
          >
            <option value="ALL">All Severities</option>
            <option value="CRITICAL">Critical</option>
            <option value="HIGH">High</option>
            <option value="MEDIUM">Medium</option>
            <option value="LOW">Low</option>
            <option value="INFO">Info</option>
          </select>

          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={loading}
              className="p-1.5 rounded-lg border border-surface-200 hover:bg-surface-100 text-surface-600 transition"
              title="Refresh findings"
            >
              <Loader2 className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          )}
        </div>
      </div>

      {/* Findings List */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {loading && findings.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-12 text-surface-400 space-y-2">
            <Loader2 className="h-8 w-8 animate-spin text-brand-blue" />
            <p className="text-sm">Evaluating behavioral signals & attribution findings...</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-12 text-surface-400 space-y-2 text-center">
            <Info className="h-8 w-8 text-surface-400" />
            <p className="font-medium text-surface-700">No Forensic Alerts Found</p>
            <p className="text-xs text-surface-500 max-w-sm">
              {findings.length === 0
                ? 'Automated findings are derived from completed multi-hop traces, VASP consolidations, and operational boundaries.'
                : 'No findings match the selected status filter.'}
            </p>
          </div>
        ) : (
          filtered.map((finding) => {
            const isExpanded = expandedId === finding.finding_id;
            const isUpdating = updatingId === finding.finding_id;

            return (
              <div
                key={finding.finding_id}
                className={`rounded-xl border transition p-4 ${
                  finding.severity === 'CRITICAL'
                    ? 'border-red-200 dark:border-red-900/60 bg-red-50/20 dark:bg-red-950/10'
                    : finding.severity === 'HIGH'
                    ? 'border-amber-200 dark:border-amber-900/60 bg-amber-50/20 dark:bg-amber-950/10'
                    : 'border-surface-200 bg-surface-default hover:border-surface-300'
                }`}
              >
                {/* Header row */}
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      {getSeverityBadge(finding.severity)}
                      {getStatusBadge(finding.status)}
                      <span className="text-xs font-mono text-surface-400">
                        {finding.source_signal}
                      </span>
                    </div>
                    <h3 className="font-semibold text-base text-surface-900 leading-snug">
                      {finding.title}
                    </h3>
                  </div>

                  {/* Quick status actions */}
                  <div className="flex items-center gap-1.5 shrink-0">
                    {finding.status === 'OPEN' ? (
                      <>
                        <button
                          onClick={() => handleStatusChange(finding, 'REVIEWED')}
                          disabled={isUpdating}
                          className="px-2.5 py-1 rounded text-xs font-medium border border-blue-200 bg-blue-50 hover:bg-blue-100 text-blue-700 dark:bg-blue-950/40 dark:border-blue-800 dark:text-blue-300 transition"
                          title="Mark finding as reviewed by investigator"
                        >
                          Mark Reviewed
                        </button>
                        <button
                          onClick={() => handleStatusChange(finding, 'DISMISSED')}
                          disabled={isUpdating}
                          className="px-2 py-1 rounded text-xs font-medium border border-surface-200 hover:bg-surface-100 text-surface-500 transition"
                          title="Dismiss finding"
                        >
                          Dismiss
                        </button>
                      </>
                    ) : finding.status === 'REVIEWED' ? (
                      <button
                        onClick={() => handleStatusChange(finding, 'OPEN')}
                        disabled={isUpdating}
                        className="px-2.5 py-1 rounded text-xs font-medium border border-surface-200 hover:bg-surface-100 text-surface-600 transition"
                      >
                        Re-Open
                      </button>
                    ) : (
                      <button
                        onClick={() => handleStatusChange(finding, 'OPEN')}
                        disabled={isUpdating}
                        className="px-2.5 py-1 rounded text-xs font-medium border border-surface-200 hover:bg-surface-100 text-surface-600 transition"
                      >
                        Restore
                      </button>
                    )}
                  </div>
                </div>

                {/* Description */}
                <p className="mt-2 text-sm text-surface-700 leading-relaxed">
                  {finding.description}
                </p>

                {/* Metadata details row */}
                <div className="mt-3 pt-3 border-t border-surface-100 dark:border-surface-800/80 flex flex-wrap items-center justify-between gap-3 text-xs">
                  <div className="flex flex-wrap items-center gap-3 text-surface-600">
                    {finding.related_address && (
                      <div className="flex items-center gap-1.5 font-mono">
                        <span className="text-surface-400">Target:</span>
                        <span className="text-surface-800 font-semibold bg-surface-100 dark:bg-surface-800 px-1.5 py-0.5 rounded">
                          {finding.related_address.slice(0, 8)}...{finding.related_address.slice(-6)}
                        </span>
                        <button
                          onClick={() => handleCopy(finding.related_address!)}
                          className="text-surface-400 hover:text-surface-700 transition"
                          title="Copy address"
                        >
                          {copiedText === finding.related_address ? (
                            <Check className="h-3 w-3 text-emerald-500" />
                          ) : (
                            <Copy className="h-3 w-3" />
                          )}
                        </button>
                      </div>
                    )}

                    {finding.related_vasp && (
                      <div className="flex items-center gap-1 text-brand-blue font-semibold">
                        <Building2 className="h-3.5 w-3.5" />
                        <span>{finding.related_vasp}</span>
                      </div>
                    )}

                    {finding.confidence !== null && finding.confidence !== undefined && (
                      <div className="flex items-center gap-1">
                        <span className="text-surface-400">Confidence:</span>
                        <span className="font-semibold text-surface-800 font-mono">
                          {(finding.confidence * 100).toFixed(1)}%
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Interactive Action Links */}
                  <div className="flex items-center gap-2">
                    {finding.graph_node_id && onViewOnGraph && (
                      <button
                        onClick={() => onViewOnGraph(finding.graph_node_id!)}
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-semibold bg-surface-100 hover:bg-surface-200 text-surface-800 dark:bg-surface-800 dark:hover:bg-surface-700 transition"
                      >
                        <Search className="h-3 w-3 text-brand-blue" />
                        View on Graph
                      </button>
                    )}

                    {finding.evidence_refs.length > 0 && onViewEvidence && (
                      <button
                        onClick={() => onViewEvidence(finding.evidence_refs[0].id)}
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-semibold bg-surface-100 hover:bg-surface-200 text-surface-800 dark:bg-surface-800 dark:hover:bg-surface-700 transition"
                      >
                        <FileCheck className="h-3 w-3 text-emerald-600" />
                        View Evidence ({finding.evidence_refs.length})
                      </button>
                    )}

                    {finding.evidence_refs.length > 0 && (
                      <button
                        onClick={() => setExpandedId(isExpanded ? null : finding.finding_id)}
                        className="p-1 text-surface-400 hover:text-surface-700 transition"
                        title={isExpanded ? 'Collapse evidence details' : 'Expand evidence details'}
                      >
                        {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                      </button>
                    )}
                  </div>
                </div>

                {/* Expandable Supporting Evidence Records */}
                {isExpanded && finding.evidence_refs.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-surface-200 dark:border-surface-700/60 space-y-2 bg-surface-50/50 dark:bg-surface-900/40 p-3 rounded-lg">
                    <h4 className="text-xs font-semibold text-surface-700 uppercase tracking-wider">
                      Supporting Evidentiary Records ({finding.evidence_refs.length})
                    </h4>
                    <div className="space-y-1.5">
                      {finding.evidence_refs.map((ref) => (
                        <div
                          key={ref.id}
                          className="flex items-center justify-between gap-2 p-2 rounded bg-surface-default border border-surface-200 text-xs"
                        >
                          <div className="flex items-center gap-2 truncate">
                            <span className="px-1.5 py-0.5 rounded font-mono text-[10px] bg-brand-light text-brand-blue">
                              {ref.classification}
                            </span>
                            <span className="font-medium text-surface-800 truncate">
                              {ref.title}
                            </span>
                          </div>
                          <div className="flex items-center gap-2 shrink-0 font-mono text-[11px] text-surface-400">
                            <span>SHA256: {ref.content_hash.slice(0, 8)}...</span>
                            {onViewEvidence && (
                              <button
                                onClick={() => onViewEvidence(ref.id)}
                                className="text-brand-blue hover:underline font-sans font-medium flex items-center gap-0.5"
                              >
                                View <ExternalLink className="h-3 w-3" />
                              </button>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Statutory Disclaimer Footer */}
      <div className="px-4 py-2.5 border-t border-surface-200 bg-surface-50 text-[11px] text-surface-500 flex items-center justify-between gap-3">
        <span>
          &bull; Forensic findings are analytical signals derived from observed on-chain transactions and are subject to investigator review.
        </span>
        <span className="font-mono text-surface-400">BSA §63 / BNSS §94</span>
      </div>
    </div>
  );
};
