import React, { useState, useEffect } from 'react';
import {
  X,
  FileText,
  Copy,
  Check,
  Plus,
  Loader2,
  AlertCircle,
  Clock,
  User,
  Edit3
} from 'lucide-react';
import type { CaseItem } from '../../types/case';
import { addCaseNote, updateCase } from '../../api/cases';

interface CaseNotesModalProps {
  isOpen: boolean;
  onClose: () => void;
  caseData: CaseItem;
  onCaseUpdated: (updatedCase: CaseItem) => void;
}

export const CaseNotesModal: React.FC<CaseNotesModalProps> = ({
  isOpen,
  onClose,
  caseData,
  onCaseUpdated,
}) => {
  const [mode, setMode] = useState<'append' | 'edit'>('append');
  const [newNote, setNewNote] = useState('');
  const [author, setAuthor] = useState('Investigating Officer');
  const [fullNotes, setFullNotes] = useState(caseData.notes || '');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setFullNotes(caseData.notes || '');
      setNewNote('');
      setError(null);
    }
  }, [isOpen, caseData.notes]);

  if (!isOpen) return null;

  const handleCopyNotes = () => {
    if (!caseData.notes) return;
    navigator.clipboard.writeText(caseData.notes);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleAddQuickTemplate = (text: string) => {
    setNewNote((prev) => (prev ? `${prev}\n${text}` : text));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      let updated: CaseItem;
      if (mode === 'append') {
        if (!newNote.trim()) {
          setError('Please enter note text before saving.');
          setLoading(false);
          return;
        }
        updated = await addCaseNote(caseData.id, newNote.trim(), author.trim() || 'Investigating Officer');
      } else {
        updated = await updateCase(caseData.id, { notes: fullNotes.trim() });
      }

      onCaseUpdated(updated);
      onClose();
    } catch (err: any) {
      console.error('Failed to update case notes:', err);
      setError(err.message || 'Failed to save note. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/75 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-in fade-in duration-200">
      <div className="bg-white dark:bg-police-900 border border-surface-200 dark:border-police-700 rounded-xl shadow-2xl w-full max-w-2xl flex flex-col max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="p-4 border-b border-surface-200 dark:border-police-800 bg-surface-50 dark:bg-police-850 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-brand-blue/10 dark:bg-blue-500/20 text-brand-blue dark:text-blue-400">
              <FileText className="h-5 w-5" />
            </div>
            <div>
              <h3 className="font-semibold text-lg text-surface-900 dark:text-white">Investigation Notes & Observations</h3>
              <p className="text-xs text-surface-500 dark:text-surface-400 font-mono">
                FIR: {caseData.fir_number} &bull; Case ID: {caseData.id.substring(caseData.id.length - 8)}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-surface-400 hover:text-surface-600 dark:hover:text-white hover:bg-surface-200 dark:hover:bg-police-800 transition"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Mode Selector Tabs */}
        <div className="px-6 pt-4 flex gap-4 border-b border-surface-200 dark:border-police-800 bg-white dark:bg-police-900">
          <button
            type="button"
            onClick={() => setMode('append')}
            className={`pb-3 text-sm font-semibold border-b-2 flex items-center gap-1.5 transition ${
              mode === 'append'
                ? 'border-brand-blue text-brand-blue dark:border-blue-400 dark:text-blue-400'
                : 'border-transparent text-surface-500 dark:text-surface-400 hover:text-surface-800 dark:hover:text-white'
            }`}
          >
            <Clock className="h-4 w-4" />
            Append Timestamped Entry
          </button>
          <button
            type="button"
            onClick={() => setMode('edit')}
            className={`pb-3 text-sm font-semibold border-b-2 flex items-center gap-1.5 transition ${
              mode === 'edit'
                ? 'border-brand-blue text-brand-blue dark:border-blue-400 dark:text-blue-400'
                : 'border-transparent text-surface-500 dark:text-surface-400 hover:text-surface-800 dark:hover:text-white'
            }`}
          >
            <Edit3 className="h-4 w-4" />
            Edit Full Case Notes
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="flex-1 flex flex-col min-h-0 overflow-hidden bg-white dark:bg-police-900">
          <div className="flex-1 overflow-y-auto p-6 space-y-4">
            {error && (
              <div className="p-3 bg-red-50 dark:bg-red-950/50 border border-red-200 dark:border-red-800 rounded-lg flex items-center gap-2 text-sm text-red-700 dark:text-red-300">
                <AlertCircle className="h-4 w-4 shrink-0 text-red-600 dark:text-red-400" />
                <span>{error}</span>
              </div>
            )}

            {mode === 'append' ? (
              <>
                {/* Existing Notes Preview */}
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="text-xs font-semibold uppercase tracking-wider text-surface-500 dark:text-surface-400">
                      Existing Case Notes History
                    </label>
                    {caseData.notes && (
                      <button
                        type="button"
                        onClick={handleCopyNotes}
                        className="flex items-center gap-1 text-xs text-brand-blue dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 font-medium"
                      >
                        {copied ? <Check className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                        {copied ? 'Copied' : 'Copy All'}
                      </button>
                    )}
                  </div>
                  {caseData.notes ? (
                    <div className="bg-surface-50 dark:bg-police-950 border border-surface-200 dark:border-police-800 rounded-lg p-3 max-h-32 overflow-y-auto text-xs font-mono text-surface-800 dark:text-surface-200 whitespace-pre-wrap leading-relaxed select-text">
                      {caseData.notes}
                    </div>
                  ) : (
                    <div className="bg-surface-50 dark:bg-police-950 border border-dashed border-surface-200 dark:border-police-800 rounded-lg p-3 text-center text-xs text-surface-400">
                      No prior notes recorded for this case.
                    </div>
                  )}
                </div>

                {/* Author field */}
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-surface-600 dark:text-surface-300 mb-1">
                    Officer / Source
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-surface-400">
                      <User className="h-4 w-4" />
                    </div>
                    <input
                      type="text"
                      value={author}
                      onChange={(e) => setAuthor(e.target.value)}
                      placeholder="e.g. Insp. Sharma (Cyber Cell)"
                      className="w-full pl-9 pr-3 py-2 text-sm bg-white dark:bg-police-950 border border-surface-300 dark:border-police-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-blue/20 focus:border-brand-blue text-surface-900 dark:text-white placeholder:text-surface-400"
                    />
                  </div>
                </div>

                {/* Quick Template Chips */}
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-surface-500 dark:text-surface-400 mb-1.5">
                    Quick Templates
                  </label>
                  <div className="flex flex-wrap gap-1.5">
                    {[
                      'Section 94 BNSS production notice dispatched to Binance Compliance.',
                      'Section 94 BNSS preservation request served on exchange.',
                      'Suspect deposit cluster verified; freezing requested.',
                      'Mule intermediary accounts verified via local bank liaison.',
                    ].map((chip) => (
                      <button
                        key={chip}
                        type="button"
                        onClick={() => handleAddQuickTemplate(chip)}
                        className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-full bg-surface-100 dark:bg-police-800 hover:bg-surface-200 dark:hover:bg-police-700 border border-surface-200 dark:border-police-700 text-surface-700 dark:text-surface-300 transition"
                      >
                        <Plus className="h-3 w-3 text-brand-blue dark:text-blue-400" />
                        {chip.substring(0, 32)}...
                      </button>
                    ))}
                  </div>
                </div>

                {/* New Note Textarea */}
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-surface-600 dark:text-surface-300 mb-1">
                    New Observation / Action Taken *
                  </label>
                  <textarea
                    rows={4}
                    value={newNote}
                    onChange={(e) => setNewNote(e.target.value)}
                    placeholder="Record investigation updates, subpoenas, communication with exchanges, or syndicate structure findings..."
                    className="w-full p-3 text-sm bg-white dark:bg-police-950 border border-surface-300 dark:border-police-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-blue/20 focus:border-brand-blue text-surface-900 dark:text-white placeholder:text-surface-400"
                    maxLength={4096}
                  />
                  <div className="flex justify-between items-center mt-1 text-xs text-surface-400">
                    <span>Entry will be timestamped in UTC automatically.</span>
                    <span>{newNote.length} / 4096</span>
                  </div>
                </div>
              </>
            ) : (
              <>
                {/* Full Notes Editor */}
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-surface-600 dark:text-surface-300 mb-1">
                    Full Case Notes & Modus Operandi
                  </label>
                  <textarea
                    rows={10}
                    value={fullNotes}
                    onChange={(e) => setFullNotes(e.target.value)}
                    placeholder="Enter or revise complete case notes..."
                    className="w-full p-3 text-sm font-mono bg-white dark:bg-police-950 border border-surface-300 dark:border-police-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-blue/20 focus:border-brand-blue text-surface-900 dark:text-white leading-relaxed placeholder:text-surface-400"
                    maxLength={8192}
                  />
                  <div className="flex justify-between items-center mt-1 text-xs text-surface-400">
                    <span>Directly modifies the case notes record.</span>
                    <span>{fullNotes.length} chars</span>
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Pinned Modal Footer */}
          <div className="px-6 py-3.5 border-t border-surface-200 dark:border-police-800 flex items-center justify-end gap-3 bg-surface-50 dark:bg-police-850 shrink-0">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-surface-600 dark:text-surface-300 hover:text-surface-800 dark:hover:text-white hover:bg-surface-200 dark:hover:bg-police-800 rounded-lg transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex items-center gap-1.5 px-4 py-2 bg-brand-blue text-white rounded-lg text-sm font-semibold hover:bg-blue-600 disabled:opacity-50 transition shadow-sm"
            >
              {loading && <Loader2 className="h-4 w-4 animate-spin" />}
              {mode === 'append' ? 'Add Note Entry' : 'Save Full Notes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
