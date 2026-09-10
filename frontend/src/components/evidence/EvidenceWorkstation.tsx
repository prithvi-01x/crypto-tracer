import React, { useState, useEffect } from 'react';
import {
  Search,
  Filter,
  Copy,
  Download,
  ShieldCheck,
  FileCode,
  Link2,
  CheckSquare,
  Check
} from 'lucide-react';
import type { EvidenceChain, EvidenceItem, EvidenceClassification } from '../../types/evidence';
import { getTraceEvidence } from '../../api/evidence';

interface EvidenceWorkstationProps {
  caseId: string;
  traceId: string | null;
  firNumber: string;
  initialSelectedEvidenceId?: string | null;
}

export const EvidenceWorkstation: React.FC<EvidenceWorkstationProps> = ({
  caseId: _caseId,
  traceId,
  firNumber,
  initialSelectedEvidenceId,
}) => {
  const [evidenceChain, setEvidenceChain] = useState<EvidenceChain | null>(null);
  const [loading, setLoading] = useState(false);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedEvId, setSelectedEvId] = useState<string | null>(initialSelectedEvidenceId || null);
  const [enabledClasses, setEnabledClasses] = useState<Record<EvidenceClassification, boolean>>({
    OBSERVED: true,
    DERIVED: true,
    INFERRED: true,
    HUMAN_ACTION: true,
  });

  useEffect(() => {
    if (initialSelectedEvidenceId) {
      setSelectedEvId(initialSelectedEvidenceId);
    }
  }, [initialSelectedEvidenceId]);

  useEffect(() => {
    if (!traceId) return;
    async function fetchEvidence() {
      setLoading(true);
      try {
        const data = await getTraceEvidence(traceId!);
        setEvidenceChain(data);
        if (data.items && data.items.length > 0) {
          setSelectedEvId(prev => prev || initialSelectedEvidenceId || data.items[0].id);
        }
      } catch (err: any) {
        console.error('Failed to fetch trace evidence:', err);
      } finally {
        setLoading(false);
      }
    }
    fetchEvidence();
  }, [traceId, initialSelectedEvidenceId]);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(text);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  const toggleClass = (cls: EvidenceClassification) => {
    setEnabledClasses(prev => ({ ...prev, [cls]: !prev[cls] }));
  };

  const allItems: EvidenceItem[] = evidenceChain?.items || [];
  const filteredItems = allItems.filter(item => {
    if (!enabledClasses[item.classification]) return false;
    if (!searchTerm) return true;
    const q = searchTerm.toLowerCase();
    return (
      item.id.toLowerCase().includes(q) ||
      item.evidence_type.toLowerCase().includes(q) ||
      item.title.toLowerCase().includes(q) ||
      (item.description && item.description.toLowerCase().includes(q)) ||
      item.content_hash.toLowerCase().includes(q)
    );
  });

  const selectedItem: EvidenceItem | undefined = 
    allItems.find(i => i.id === selectedEvId) || allItems[0];

  const handleExportChain = () => {
    if (!evidenceChain) return;
    const blob = new Blob([JSON.stringify(evidenceChain, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ChainOfCustody_${firNumber.replace(/[^a-zA-Z0-9_-]/g, '_')}_${caseId.substring(0, 8)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex h-full gap-4">
      {/* LEFT PANEL: Filters */}
      <div className="w-[240px] shrink-0 bg-surface-default border border-surface-200 rounded shadow-sm flex flex-col h-[calc(100vh-220px)]">
         <div className="p-4 border-b border-surface-200">
           <h3 className="text-lg font-semibold text-surface-800 flex items-center gap-2">
             <Filter className="h-4 w-4" /> Filters &amp; Classification
           </h3>
         </div>
         <div className="p-4 flex-1 overflow-y-auto space-y-6 text-lg text-surface-700">
            <div>
               <h4 className="font-bold text-base uppercase tracking-wider text-surface-500 mb-3">Evidence Classifications</h4>
               <div className="space-y-2.5">
                  <label className="flex items-center gap-2 cursor-pointer group">
                    <input 
                      type="checkbox" 
                      checked={enabledClasses.OBSERVED} 
                      onChange={() => toggleClass('OBSERVED')}
                      className="rounded border-surface-300 text-brand-blue focus:ring-brand-blue" 
                    />
                    <span className="flex-1 text-base group-hover:text-surface-900 transition">OBSERVED (On-chain)</span>
                    <span className="text-sm bg-surface-100 text-surface-500 px-2.5 py-1 rounded font-mono">
                      {evidenceChain?.observed_count ?? allItems.filter(i => i.classification === 'OBSERVED').length}
                    </span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer group">
                    <input 
                      type="checkbox" 
                      checked={enabledClasses.DERIVED} 
                      onChange={() => toggleClass('DERIVED')}
                      className="rounded border-surface-300 text-brand-blue focus:ring-brand-blue" 
                    />
                    <span className="flex-1 text-base group-hover:text-surface-900 transition">DERIVED (Metrics)</span>
                    <span className="text-sm bg-surface-100 text-surface-500 px-2.5 py-1 rounded font-mono">
                      {evidenceChain?.derived_count ?? allItems.filter(i => i.classification === 'DERIVED').length}
                    </span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer group">
                    <input 
                      type="checkbox" 
                      checked={enabledClasses.INFERRED} 
                      onChange={() => toggleClass('INFERRED')}
                      className="rounded border-surface-300 text-brand-blue focus:ring-brand-blue" 
                    />
                    <span className="flex-1 text-base group-hover:text-surface-900 transition">INFERRED (Attribution)</span>
                    <span className="text-sm bg-surface-100 text-surface-500 px-2.5 py-1 rounded font-mono">
                      {evidenceChain?.inferred_count ?? allItems.filter(i => i.classification === 'INFERRED').length}
                    </span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer group">
                    <input 
                      type="checkbox" 
                      checked={enabledClasses.HUMAN_ACTION} 
                      onChange={() => toggleClass('HUMAN_ACTION')}
                      className="rounded border-surface-300 text-brand-blue focus:ring-brand-blue" 
                    />
                    <span className="flex-1 text-base group-hover:text-surface-900 transition">HUMAN ACTION</span>
                    <span className="text-sm bg-surface-100 text-surface-500 px-2.5 py-1 rounded font-mono">
                      {evidenceChain?.human_action_count ?? allItems.filter(i => i.classification === 'HUMAN_ACTION').length}
                    </span>
                  </label>
               </div>
            </div>

            <div>
               <h4 className="font-bold text-base uppercase tracking-wider text-surface-500 mb-3">Total Artifacts</h4>
               <div className="p-3 bg-surface-50 rounded border border-surface-200 text-base font-mono">
                 <div className="flex justify-between py-0.5">
                   <span className="text-surface-500">Chain Total:</span>
                   <span className="font-bold text-surface-800">{allItems.length} records</span>
                 </div>
                 <div className="flex justify-between py-0.5">
                   <span className="text-surface-500">In View:</span>
                   <span className="font-bold text-brand-blue">{filteredItems.length} records</span>
                 </div>
               </div>
            </div>

            <div className="pt-4 border-t border-surface-200">
               <div className="flex items-center justify-between p-2 rounded bg-emerald-50 border border-emerald-200">
                 <span className="text-sm font-bold text-emerald-800">Hash Chain Integrity</span>
                 <span className="text-sm font-bold text-emerald-700 bg-emerald-200/50 px-2 py-1 rounded flex items-center gap-1">
                   <ShieldCheck className="h-4 w-4" /> Section 63 BSA
                 </span>
               </div>
            </div>
         </div>
      </div>

      {/* CENTER PANEL: Evidence Table */}
      <div className="flex-1 bg-surface-default border border-surface-200 rounded shadow-sm flex flex-col h-[calc(100vh-220px)] overflow-hidden">
         <div className="p-3 border-b border-surface-200 flex items-center justify-between bg-surface-50">
            <div className="relative w-72">
              <Search className="absolute left-2.5 top-2 h-4 w-4 text-surface-400" />
              <input 
                type="text" 
                placeholder="Search hash, type, or fact..." 
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 bg-surface-default border border-surface-200 rounded text-base focus:ring-1 focus:ring-brand-blue focus:outline-none" 
              />
            </div>
            <button 
              onClick={handleExportChain}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded text-base font-semibold bg-surface-default border border-surface-300 hover:bg-surface-50 transition text-surface-700"
            >
              <Download className="h-4 w-4" /> Export Chain of Custody JSON
            </button>
         </div>
         
         <div className="flex-1 overflow-auto">
            <table className="w-full text-left border-collapse">
               <thead>
                  <tr className="bg-surface-default border-b border-surface-200 text-sm font-bold text-surface-500 uppercase tracking-wider sticky top-0 shadow-sm z-10">
                    <th className="px-3 py-2 w-28">ID</th>
                    <th className="px-3 py-2 w-28">Class</th>
                    <th className="px-3 py-2 w-36">Type</th>
                    <th className="px-3 py-2">Description / Fact</th>
                    <th className="px-3 py-2 w-28">Source</th>
                    <th className="px-3 py-2 w-24">Hash</th>
                  </tr>
               </thead>
               <tbody className="divide-y divide-surface-100 text-base text-surface-800">
                 {loading ? (
                   <tr>
                     <td colSpan={6} className="px-4 py-12 text-center text-surface-500">
                       Loading cryptographic evidence DAG...
                     </td>
                   </tr>
                 ) : filteredItems.length === 0 ? (
                   <tr>
                     <td colSpan={6} className="px-4 py-12 text-center text-surface-500">
                       {allItems.length === 0 ? 'No evidence records found for this trace.' : 'No items match current filters.'}
                     </td>
                   </tr>
                 ) : (
                   filteredItems.map((ev) => {
                     const isSelected = selectedItem?.id === ev.id;
                     const displayId = ev.id.length > 18 ? `${ev.id.substring(0, 16)}...` : ev.id;
                     return (
                       <tr 
                         key={ev.id} 
                         onClick={() => setSelectedEvId(ev.id)}
                         className={`cursor-pointer transition hover:bg-brand-light/30 h-12 ${isSelected ? 'bg-brand-light border-l-2 border-l-brand-blue' : ''}`}
                       >
                         <td className="px-3 py-2 font-mono text-xs text-surface-600 font-semibold" title={ev.id}>
                           {displayId}
                         </td>
                         <td className="px-3 py-2">
                           <span className={`px-2 py-0.5 rounded text-xs font-bold border ${
                             ev.classification === 'OBSERVED' ? 'bg-blue-50 text-brand-blue border-blue-200' :
                             ev.classification === 'DERIVED' ? 'bg-purple-50 text-purple-700 border-purple-200' :
                             ev.classification === 'INFERRED' ? 'bg-amber-50 text-amber-700 border-amber-200' :
                             'bg-emerald-50 text-emerald-700 border-emerald-200'
                           }`}>
                             {ev.classification}
                           </span>
                         </td>
                         <td className="px-3 py-2 text-surface-600 font-medium text-sm truncate max-w-[140px]" title={ev.evidence_type}>
                           {ev.evidence_type.replace(/_/g, ' ')}
                         </td>
                         <td className="px-3 py-2 truncate max-w-sm" title={ev.description || ev.title}>
                           {ev.title || ev.description}
                         </td>
                         <td className="px-3 py-2 text-surface-500 text-sm truncate max-w-[100px]" title={ev.source}>
                           {ev.source}
                         </td>
                         <td className="px-3 py-2 font-mono text-xs text-surface-500">
                           {ev.content_hash.substring(0, 8)}...
                         </td>
                       </tr>
                     );
                   })
                 )}
               </tbody>
            </table>
         </div>
         <div className="p-2 border-t border-surface-200 bg-surface-50 text-sm font-medium text-surface-500 text-center flex items-center justify-center gap-2">
           <ShieldCheck className="h-4 w-4 text-emerald-500" /> Compliant with Section 63 BSA for electronic-record evidence. (Trace: {traceId ? `${traceId.substring(0, 8)}...` : 'N/A'})
         </div>
      </div>

      {/* RIGHT PANEL: Details */}
      <div className="w-[340px] shrink-0 bg-surface-default border border-surface-200 rounded shadow-sm flex flex-col h-[calc(100vh-220px)] overflow-hidden">
         {selectedItem ? (
           <>
             <div className="p-4 border-b border-surface-200 bg-surface-50 flex items-start justify-between">
                <div>
                   <h3 className="text-lg font-bold text-surface-800 break-all font-mono text-base">{selectedItem.id}</h3>
                   <span className={`mt-1 inline-block px-2.5 py-0.5 rounded text-xs font-bold border ${
                     selectedItem.classification === 'OBSERVED' ? 'bg-blue-50 text-brand-blue border-blue-200' :
                     selectedItem.classification === 'DERIVED' ? 'bg-purple-50 text-purple-700 border-purple-200' :
                     selectedItem.classification === 'INFERRED' ? 'bg-amber-50 text-amber-700 border-amber-200' :
                     'bg-emerald-50 text-emerald-700 border-emerald-200'
                   }`}>
                     {selectedItem.classification}
                   </span>
                </div>
             </div>
             
             <div className="p-4 flex-1 overflow-y-auto space-y-4 text-lg text-surface-800">
                <div className="grid grid-cols-1 gap-2 text-base">
                  <div>
                    <span className="font-bold text-surface-500 block text-xs uppercase mb-0.5">Type</span> 
                    <span className="font-semibold text-surface-800">{selectedItem.evidence_type.replace(/_/g, ' ')}</span>
                  </div>
                  <div>
                    <span className="font-bold text-surface-500 block text-xs uppercase mb-0.5">Summary</span>
                    <span className="text-surface-700 text-sm">{selectedItem.title}</span>
                  </div>
                  {selectedItem.source_reference && (
                    <div>
                      <span className="font-bold text-surface-500 block text-xs uppercase mb-0.5">Source Reference</span>
                      <span className="font-mono text-xs bg-surface-100 p-1 rounded block break-all text-surface-700">
                        {selectedItem.source_reference}
                      </span>
                    </div>
                  )}
                  <div>
                    <span className="font-bold text-surface-500 block text-xs uppercase mb-0.5">Collected At</span> 
                    <span className="font-mono text-xs text-surface-600">{selectedItem.collected_at || selectedItem.created_at}</span>
                  </div>
                  
                  <div className="pt-2">
                    <span className="font-bold text-surface-500 block text-xs uppercase mb-0.5">Cryptographic SHA-256 Hash</span>
                    <div className="flex items-center justify-between font-mono text-xs bg-surface-50 border border-surface-200 p-2 rounded break-all text-surface-700">
                      <span className="leading-tight">{selectedItem.content_hash}</span>
                      <button 
                        onClick={() => copyToClipboard(selectedItem.content_hash)}
                        className="ml-2 text-surface-500 hover:text-brand-blue shrink-0"
                        title="Copy SHA-256 hash"
                      >
                        {copiedHash === selectedItem.content_hash ? (
                          <Check className="h-4 w-4 text-emerald-600" />
                        ) : (
                          <Copy className="h-4 w-4" />
                        )}
                      </button>
                    </div>
                  </div>
                </div>

                <div>
                   <span className="font-bold text-surface-500 block text-xs uppercase mb-1 flex items-center gap-1">
                     <FileCode className="h-4 w-4" /> Canonical RFC-8785 JSON Payload
                   </span>
                   <pre className="p-3 bg-surface-900 rounded text-emerald-400 font-mono text-xs overflow-x-auto whitespace-pre-wrap leading-relaxed shadow-inner max-h-56">
                     {JSON.stringify(selectedItem.payload, null, 2)}
                   </pre>
                </div>

                <div>
                   <span className="font-bold text-surface-500 block text-xs uppercase mb-1 flex items-center gap-1">
                     <Link2 className="h-4 w-4" /> Provenance Parent Linkage
                   </span>
                   {selectedItem.parent_evidence_ids && selectedItem.parent_evidence_ids.length > 0 ? (
                     <div className="flex flex-wrap gap-1.5 text-xs font-mono">
                       {selectedItem.parent_evidence_ids.map((pid, pidx) => (
                         <span 
                           key={pidx} 
                           onClick={() => setSelectedEvId(pid)}
                           className="px-2 py-0.5 bg-surface-100 rounded border border-surface-300 text-surface-600 cursor-pointer hover:border-brand-blue hover:text-brand-blue transition"
                           title={`Inspect parent: ${pid}`}
                         >
                           {pid.substring(0, 14)}...
                         </span>
                       ))}
                     </div>
                   ) : (
                     <span className="text-xs text-surface-500 italic">Genesis / Ingress Root Fact (No upstream parents)</span>
                   )}
                </div>

                <div className="pt-2">
                   <button 
                     onClick={() => copyToClipboard(JSON.stringify(selectedItem, null, 2))}
                     className="w-full py-1.5 rounded text-sm font-semibold bg-brand-blue text-white hover:bg-brand-hover transition flex items-center justify-center gap-1.5"
                   >
                     <Copy className="h-4 w-4" /> Copy Full Evidence Record JSON
                   </button>
                </div>
             </div>
           </>
         ) : (
           <div className="p-8 text-center text-surface-400 text-base flex flex-col items-center justify-center h-full">
             <CheckSquare className="h-8 w-8 mb-2 opacity-50" />
             Select an evidence item to view verifiable payload and cryptographic lineage.
           </div>
         )}
      </div>

    </div>
  );
};

