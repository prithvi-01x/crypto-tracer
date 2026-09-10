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
  Check,
  Network,
  ExternalLink
} from 'lucide-react';
import type { EvidenceChain, EvidenceItem, EvidenceClassification } from '../../types/evidence';
import { getTraceEvidence } from '../../api/evidence';

interface EvidenceWorkstationProps {
  caseId: string;
  traceId: string | null;
  firNumber: string;
  initialSelectedEvidenceId?: string | null;
  onNavigateToGraph?: (addressOrId?: string) => void;
}

export const EvidenceWorkstation: React.FC<EvidenceWorkstationProps> = ({
  caseId,
  traceId,
  firNumber,
  initialSelectedEvidenceId,
  onNavigateToGraph,
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

  const getAssociatedAddress = (item?: EvidenceItem): string | null => {
    if (!item) return null;
    const p = (item.payload || {}) as Record<string, any>;
    if (typeof p.address === 'string' && p.address.startsWith('T')) return p.address;
    if (typeof p.suspect_wallet === 'string' && p.suspect_wallet.startsWith('T')) return p.suspect_wallet;
    if (typeof p.candidate_address === 'string' && p.candidate_address.startsWith('T')) return p.candidate_address;
    if (typeof p.from_address === 'string' && p.from_address.startsWith('T')) return p.from_address;
    if (typeof p.to_address === 'string' && p.to_address.startsWith('T')) return p.to_address;
    if (typeof item.source_reference === 'string' && item.source_reference.startsWith('T') && item.source_reference.length >= 30) {
      return item.source_reference;
    }
    return null;
  };

  const associatedAddress = getAssociatedAddress(selectedItem);

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

  if (!traceId) {
    return (
      <div className="bg-surface-default dark:bg-surface-100 border border-surface-200 dark:border-surface-300 rounded-xl p-12 text-center shadow-xs max-w-xl mx-auto my-8">
        <div className="mx-auto w-14 h-14 rounded-full bg-surface-100 dark:bg-surface-200 flex items-center justify-center text-surface-400 dark:text-surface-500 mb-4">
          <ShieldCheck className="h-7 w-7 text-brand-blue dark:text-blue-400" />
        </div>
        <h3 className="text-lg font-bold text-surface-800 dark:text-surface-100 mb-2">
          No Cryptographic Evidence Chain Found
        </h3>
        <p className="text-xs sm:text-sm text-surface-500 dark:text-surface-400 leading-relaxed mb-6">
          Evidence records are cryptographically compiled during multi-hop graph execution under Section 63 BSA rules. Run a multi-hop trace on the suspect wallet to generate verifiable SHA-256 artifacts.
        </p>
        {onNavigateToGraph && (
          <button
            onClick={() => onNavigateToGraph()}
            className="px-4 py-2.5 rounded-lg bg-brand-blue hover:bg-brand-hover text-white text-xs font-bold transition shadow-xs cursor-pointer inline-flex items-center gap-2"
          >
            <Network className="h-4 w-4" />
            <span>Go to Trace Graph &amp; Launch Trace</span>
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col lg:flex-row h-full gap-4">
      {/* LEFT PANEL: Filters */}
      <div className="w-full lg:w-[240px] shrink-0 bg-surface-default dark:bg-surface-100 border border-surface-200 dark:border-surface-300 rounded-xl shadow-xs flex flex-col max-h-[750px] overflow-hidden">
         <div className="p-4 border-b border-surface-200 dark:border-surface-300">
           <h3 className="text-sm font-bold text-surface-800 dark:text-surface-100 flex items-center gap-2 uppercase tracking-wider">
             <Filter className="h-4 w-4 text-brand-blue dark:text-blue-400" /> 
             <span>Filters &amp; Classification</span>
           </h3>
         </div>
         <div className="p-4 flex-1 overflow-y-auto space-y-6 text-xs text-surface-700 dark:text-surface-200">
            <div>
               <h4 className="font-bold text-[10px] uppercase tracking-wider text-surface-500 mb-3">Evidence Classifications</h4>
               <div className="space-y-2.5">
                  <label className="flex items-center gap-2 cursor-pointer group">
                    <input 
                      type="checkbox" 
                      checked={enabledClasses.OBSERVED} 
                      onChange={() => toggleClass('OBSERVED')}
                      className="rounded border-surface-300 text-brand-blue focus:ring-brand-blue cursor-pointer" 
                    />
                    <span className="flex-1 group-hover:text-surface-900 dark:group-hover:text-white transition">OBSERVED (On-chain)</span>
                    <span className="text-[11px] bg-surface-100 dark:bg-surface-200 text-surface-600 dark:text-surface-300 px-2 py-0.5 rounded font-mono font-bold">
                      {evidenceChain?.observed_count ?? allItems.filter(i => i.classification === 'OBSERVED').length}
                    </span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer group">
                    <input 
                      type="checkbox" 
                      checked={enabledClasses.DERIVED} 
                      onChange={() => toggleClass('DERIVED')}
                      className="rounded border-surface-300 text-brand-blue focus:ring-brand-blue cursor-pointer" 
                    />
                    <span className="flex-1 group-hover:text-surface-900 dark:group-hover:text-white transition">DERIVED (Metrics)</span>
                    <span className="text-[11px] bg-surface-100 dark:bg-surface-200 text-surface-600 dark:text-surface-300 px-2 py-0.5 rounded font-mono font-bold">
                      {evidenceChain?.derived_count ?? allItems.filter(i => i.classification === 'DERIVED').length}
                    </span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer group">
                    <input 
                      type="checkbox" 
                      checked={enabledClasses.INFERRED} 
                      onChange={() => toggleClass('INFERRED')}
                      className="rounded border-surface-300 text-brand-blue focus:ring-brand-blue cursor-pointer" 
                    />
                    <span className="flex-1 group-hover:text-surface-900 dark:group-hover:text-white transition">INFERRED (Attribution)</span>
                    <span className="text-[11px] bg-surface-100 dark:bg-surface-200 text-surface-600 dark:text-surface-300 px-2 py-0.5 rounded font-mono font-bold">
                      {evidenceChain?.inferred_count ?? allItems.filter(i => i.classification === 'INFERRED').length}
                    </span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer group">
                    <input 
                      type="checkbox" 
                      checked={enabledClasses.HUMAN_ACTION} 
                      onChange={() => toggleClass('HUMAN_ACTION')}
                      className="rounded border-surface-300 text-brand-blue focus:ring-brand-blue cursor-pointer" 
                    />
                    <span className="flex-1 group-hover:text-surface-900 dark:group-hover:text-white transition">HUMAN ACTION</span>
                    <span className="text-[11px] bg-surface-100 dark:bg-surface-200 text-surface-600 dark:text-surface-300 px-2 py-0.5 rounded font-mono font-bold">
                      {evidenceChain?.human_action_count ?? allItems.filter(i => i.classification === 'HUMAN_ACTION').length}
                    </span>
                  </label>
               </div>
            </div>

            <div>
               <h4 className="font-bold text-[10px] uppercase tracking-wider text-surface-500 mb-2">Total Artifacts</h4>
               <div className="p-2.5 bg-surface-50 dark:bg-surface-200/50 rounded-lg border border-surface-200 dark:border-surface-300 font-mono text-xs space-y-1">
                 <div className="flex justify-between py-0.5">
                   <span className="text-surface-500">Chain Total:</span>
                   <span className="font-bold text-surface-800 dark:text-surface-200">{allItems.length} records</span>
                 </div>
                 <div className="flex justify-between py-0.5">
                   <span className="text-surface-500">In View:</span>
                   <span className="font-bold text-brand-blue dark:text-blue-400">{filteredItems.length} records</span>
                 </div>
               </div>
            </div>

            <div className="pt-2 border-t border-surface-200 dark:border-surface-300">
               <div className="p-2 rounded bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 flex items-center justify-between">
                 <span className="text-[11px] font-bold text-emerald-800 dark:text-emerald-300">Integrity Sealed</span>
                 <span className="text-[10px] font-bold text-emerald-700 dark:text-emerald-300 bg-emerald-200/50 dark:bg-emerald-800/40 px-1.5 py-0.5 rounded flex items-center gap-1 font-mono">
                   <ShieldCheck className="h-3 w-3" /> Section 63 BSA
                 </span>
               </div>
            </div>
         </div>
      </div>

      {/* CENTER PANEL: Evidence Table */}
      <div className="flex-1 bg-surface-default dark:bg-surface-100 border border-surface-200 dark:border-surface-300 rounded-xl shadow-xs flex flex-col max-h-[750px] overflow-hidden">
         <div className="p-3 border-b border-surface-200 dark:border-surface-300 flex items-center justify-between bg-surface-50 dark:bg-surface-200/40 gap-3 flex-wrap">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-2.5 top-2 h-4 w-4 text-surface-400" />
              <input 
                type="text" 
                placeholder="Search hash, type, or fact..." 
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 bg-surface-default dark:bg-surface-100 border border-surface-200 dark:border-surface-300 rounded-lg text-xs focus:ring-1 focus:ring-brand-blue focus:outline-none" 
              />
            </div>
            <button 
              onClick={handleExportChain}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-surface-default dark:bg-surface-100 border border-surface-300 dark:border-surface-300 hover:bg-surface-50 dark:hover:bg-surface-200 transition text-surface-700 dark:text-surface-200 cursor-pointer shadow-xs"
            >
              <Download className="h-3.5 w-3.5" /> 
              <span>Export Chain of Custody JSON</span>
            </button>
         </div>
         
         <div className="flex-1 overflow-auto">
            <table className="w-full text-left border-collapse">
               <thead>
                  <tr className="bg-surface-50 dark:bg-surface-200/60 border-b border-surface-200 dark:border-surface-300 text-[11px] font-bold text-surface-500 uppercase tracking-wider sticky top-0 shadow-2xs z-10">
                    <th className="px-3 py-2 w-28">ID</th>
                    <th className="px-3 py-2 w-24">Class</th>
                    <th className="px-3 py-2 w-36">Type</th>
                    <th className="px-3 py-2">Description / Fact</th>
                    <th className="px-3 py-2 w-24">Source</th>
                    <th className="px-3 py-2 w-24">Hash</th>
                  </tr>
               </thead>
               <tbody className="divide-y divide-surface-100 dark:divide-surface-200/50 text-xs text-surface-800 dark:text-surface-200">
                 {loading ? (
                   <tr>
                     <td colSpan={6} className="px-4 py-12 text-center text-surface-500">
                       <div className="h-5 w-5 border-2 border-brand-blue border-t-transparent rounded-full animate-spin mx-auto mb-2" />
                       <span>Loading cryptographic evidence DAG...</span>
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
                         className={`cursor-pointer transition hover:bg-brand-light/30 dark:hover:bg-surface-200/50 h-10 ${
                           isSelected ? 'bg-brand-light dark:bg-brand-blue/15 border-l-2 border-l-brand-blue' : ''
                         }`}
                       >
                         <td className="px-3 py-2 font-mono text-[11px] text-surface-600 dark:text-surface-400 font-semibold" title={ev.id}>
                           {displayId}
                         </td>
                         <td className="px-3 py-2">
                           <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${
                             ev.classification === 'OBSERVED' ? 'bg-blue-50 dark:bg-blue-950/40 text-brand-blue dark:text-blue-300 border-blue-200 dark:border-blue-800' :
                             ev.classification === 'DERIVED' ? 'bg-purple-50 dark:bg-purple-950/40 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-800' :
                             ev.classification === 'INFERRED' ? 'bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800' :
                             'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800'
                           }`}>
                             {ev.classification}
                           </span>
                         </td>
                         <td className="px-3 py-2 text-surface-600 dark:text-surface-300 font-medium text-xs truncate max-w-[140px]" title={ev.evidence_type}>
                           {ev.evidence_type.replace(/_/g, ' ')}
                         </td>
                         <td className="px-3 py-2 truncate max-w-sm text-xs font-normal" title={ev.description || ev.title}>
                           {ev.title || ev.description}
                         </td>
                         <td className="px-3 py-2 text-surface-500 text-xs truncate max-w-[100px]" title={ev.source}>
                           {ev.source}
                         </td>
                         <td className="px-3 py-2 font-mono text-[11px] text-surface-500">
                           {ev.content_hash.substring(0, 8)}...
                         </td>
                       </tr>
                     );
                   })
                 )}
               </tbody>
            </table>
         </div>
         <div className="p-2 border-t border-surface-200 dark:border-surface-300 bg-surface-50 dark:bg-surface-200/40 text-xs font-medium text-surface-500 text-center flex items-center justify-center gap-2">
           <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" /> 
           <span>Compliant with Section 63 BSA for electronic-record evidence. (Trace: {traceId.substring(0, 8)}...)</span>
         </div>
      </div>

      {/* RIGHT PANEL: Details & Cross-Navigation */}
      <div className="w-full lg:w-[350px] shrink-0 bg-surface-default dark:bg-surface-100 border border-surface-200 dark:border-surface-300 rounded-xl shadow-xs flex flex-col max-h-[750px] overflow-hidden">
         {selectedItem ? (
           <>
             <div className="p-4 border-b border-surface-200 dark:border-surface-300 bg-surface-50 dark:bg-surface-200/40 flex items-start justify-between">
                <div>
                   <h3 className="text-sm font-bold text-surface-800 dark:text-surface-100 break-all font-mono">{selectedItem.id}</h3>
                   <span className={`mt-1 inline-block px-2 py-0.5 rounded text-[10px] font-bold border ${
                     selectedItem.classification === 'OBSERVED' ? 'bg-blue-50 dark:bg-blue-950/40 text-brand-blue dark:text-blue-300 border-blue-200 dark:border-blue-800' :
                     selectedItem.classification === 'DERIVED' ? 'bg-purple-50 dark:bg-purple-950/40 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-800' :
                     selectedItem.classification === 'INFERRED' ? 'bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800' :
                     'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800'
                   }`}>
                     {selectedItem.classification}
                   </span>
                </div>
             </div>
             
             <div className="p-4 flex-1 overflow-y-auto space-y-4 text-xs text-surface-800 dark:text-surface-200">
                {/* Cross-Navigation Jump to Graph */}
                {associatedAddress && onNavigateToGraph && (
                  <button
                    onClick={() => onNavigateToGraph(associatedAddress)}
                    className="w-full py-2 px-3 rounded-lg bg-brand-light dark:bg-brand-blue/15 hover:bg-brand-blue/20 text-brand-blue dark:text-blue-400 font-bold text-xs transition flex items-center justify-center gap-2 border border-brand-blue/30 cursor-pointer shadow-2xs"
                  >
                    <Network className="h-3.5 w-3.5" />
                    <span>Inspect Node on Graph ({associatedAddress.slice(0, 6)}...{associatedAddress.slice(-4)})</span>
                  </button>
                )}

                <div className="grid grid-cols-1 gap-2.5">
                  <div>
                    <span className="font-bold text-surface-500 block text-[10px] uppercase mb-0.5">Type</span> 
                    <span className="font-semibold text-surface-800 dark:text-surface-100">{selectedItem.evidence_type.replace(/_/g, ' ')}</span>
                  </div>
                  <div>
                    <span className="font-bold text-surface-500 block text-[10px] uppercase mb-0.5">Summary</span>
                    <span className="text-surface-700 dark:text-surface-300">{selectedItem.title}</span>
                  </div>
                  {selectedItem.source_reference && (
                    <div>
                      <span className="font-bold text-surface-500 block text-[10px] uppercase mb-0.5">Source Reference</span>
                      <span className="font-mono text-[11px] bg-surface-100 dark:bg-surface-200 p-1.5 rounded block break-all text-surface-700 dark:text-surface-300">
                        {selectedItem.source_reference}
                      </span>
                    </div>
                  )}
                  <div>
                    <span className="font-bold text-surface-500 block text-[10px] uppercase mb-0.5">Collected At</span> 
                    <span className="font-mono text-[11px] text-surface-600 dark:text-surface-400">{selectedItem.collected_at || selectedItem.created_at}</span>
                  </div>
                  
                  <div>
                    <span className="font-bold text-surface-500 block text-[10px] uppercase mb-0.5">Cryptographic SHA-256 Hash</span>
                    <div className="flex items-center justify-between font-mono text-[11px] bg-surface-50 dark:bg-surface-200/50 border border-surface-200 dark:border-surface-300 p-2 rounded-lg break-all text-surface-700 dark:text-surface-300">
                      <span className="leading-tight">{selectedItem.content_hash}</span>
                      <button 
                        onClick={() => copyToClipboard(selectedItem.content_hash)}
                        className="ml-2 text-surface-500 hover:text-brand-blue cursor-pointer shrink-0"
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
                   <span className="font-bold text-surface-500 block text-[10px] uppercase mb-1 flex items-center gap-1">
                     <FileCode className="h-3.5 w-3.5 text-brand-blue dark:text-blue-400" /> 
                     <span>Canonical RFC-8785 JSON Payload</span>
                   </span>
                   <pre className="p-3 bg-surface-900 rounded-lg text-emerald-400 font-mono text-[11px] overflow-x-auto whitespace-pre-wrap leading-relaxed shadow-inner max-h-52">
                     {JSON.stringify(selectedItem.payload, null, 2)}
                   </pre>
                </div>

                <div>
                   <span className="font-bold text-surface-500 block text-[10px] uppercase mb-1 flex items-center gap-1">
                     <Link2 className="h-3.5 w-3.5 text-brand-blue dark:text-blue-400" /> 
                     <span>Provenance Parent Linkage</span>
                   </span>
                   {selectedItem.parent_evidence_ids && selectedItem.parent_evidence_ids.length > 0 ? (
                     <div className="flex flex-wrap gap-1.5 font-mono text-[11px]">
                       {selectedItem.parent_evidence_ids.map((pid, pidx) => (
                         <span 
                           key={pidx} 
                           onClick={() => setSelectedEvId(pid)}
                           className="px-2 py-0.5 bg-surface-100 dark:bg-surface-200 rounded border border-surface-300 dark:border-surface-300 text-surface-600 dark:text-surface-300 cursor-pointer hover:border-brand-blue hover:text-brand-blue transition"
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

                <div className="pt-1">
                   <button 
                     onClick={() => copyToClipboard(JSON.stringify(selectedItem, null, 2))}
                     className="w-full py-2 rounded-lg text-xs font-bold bg-brand-blue hover:bg-brand-hover text-white transition flex items-center justify-center gap-1.5 cursor-pointer shadow-xs"
                   >
                     <Copy className="h-3.5 w-3.5" /> 
                     <span>Copy Full Evidence Record JSON</span>
                   </button>
                </div>
             </div>
           </>
         ) : (
           <div className="p-8 text-center text-surface-400 text-xs flex flex-col items-center justify-center h-full">
             <CheckSquare className="h-8 w-8 mb-2 opacity-50" />
             <span>Select an evidence item to view verifiable payload and cryptographic lineage.</span>
           </div>
         )}
      </div>

    </div>
  );
};

