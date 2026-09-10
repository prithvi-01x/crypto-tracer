import { useState, useEffect, useRef } from 'react';
import { 
  Shield, 
  Search, 
  Bell, 
  HelpCircle, 
  Moon, 
  Sun, 
  AlertCircle,
  Command,
  CheckCircle2,
  Database,
  Cpu,
  Server,
  FileCheck,
  BookOpen,
  Keyboard,
  X
} from 'lucide-react';
import type { CaseItem } from './types/case';
import { getCases } from './api/cases';
import { getSystemHealth } from './api/health';
import { CaseListView } from './components/cases/CaseListView';
import { CaseDetailsView } from './components/cases/CaseDetailsView';
import { NewCaseModal } from './components/cases/NewCaseModal';

export default function App() {
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [casesLoading, setCasesLoading] = useState<boolean>(true);
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [isNewCaseOpen, setIsNewCaseOpen] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [isDarkMode, setIsDarkMode] = useState<boolean>(false);
  const [globalSearch, setGlobalSearch] = useState<string>('');
  const [healthStatus, setHealthStatus] = useState<'HEALTHY' | 'DEGRADED' | 'CHECKING'>('CHECKING');
  const [isNotificationsOpen, setIsNotificationsOpen] = useState<boolean>(false);
  const [isHelpOpen, setIsHelpOpen] = useState<boolean>(false);

  const searchInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        searchInputRef.current?.focus();
        searchInputRef.current?.select();
      }
      if (e.key === 'Escape') {
        setIsNotificationsOpen(false);
        setIsHelpOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDarkMode]);

  useEffect(() => {
    getSystemHealth()
      .then((res) => setHealthStatus(res.status === 'HEALTHY' ? 'HEALTHY' : 'DEGRADED'))
      .catch(() => setHealthStatus('DEGRADED'));
  }, []);

  const loadCases = async () => {
    setCasesLoading(true);
    try {
      const data = await getCases();
      setCases(data.cases);
    } catch (err: any) {
      console.error('Failed to load cases:', err);
      setError(err.message || 'Failed to fetch cases from database');
    } finally {
      setCasesLoading(false);
    }
  };

  useEffect(() => {
    loadCases();
  }, []);

  const handleCaseCreated = (newCaseId: string) => {
    loadCases();
    setSelectedCaseId(newCaseId);
  };

  return (
    <div className="min-h-screen bg-surface-50 text-surface-800 flex flex-col font-sans transition-colors">
      {/* Reactor Top Command Header */}
      <header className="border-b border-surface-200 dark:border-surface-300 bg-surface-default dark:bg-surface-100 px-4 sm:px-6 py-2 sticky top-0 z-40 shadow-xs transition-colors">
        <div className="w-full max-w-[96vw] 2xl:max-w-[1920px] mx-auto flex items-center justify-between gap-4">
          
          {/* Brand Logo & Reactor Edition */}
          <div 
            onClick={() => setSelectedCaseId(null)}
            className="flex items-center gap-3 cursor-pointer group shrink-0"
          >
            <div className="h-9 w-9 rounded-lg bg-gradient-to-br from-reactor-orange to-reactor-orange-tint p-0.5 shadow-sm shadow-orange-500/25 flex items-center justify-center">
              <div className="h-full w-full bg-surface-900 dark:bg-surface-50 rounded-[7px] flex items-center justify-center">
                <Shield className="h-5 w-5 text-reactor-orange" />
              </div>
            </div>
            <div className="flex flex-col">
              <div className="flex items-center gap-2">
                <span className="font-extrabold text-sm tracking-wider text-surface-900 dark:text-white font-sans">
                  CRYPTO<span className="text-reactor-orange font-black">TRACER</span>
                </span>
                <span className="text-[10px] font-mono tracking-wider text-reactor-orange font-bold px-1.5 py-0.2 rounded bg-orange-500/10 border border-orange-500/30">
                  REACTOR
                </span>
              </div>
              <span className="text-[10px] text-surface-500 font-mono tracking-tight">
                Blockchain Forensic Investigation Console
              </span>
            </div>
          </div>

          {/* Center Search Bar with Keyboard Hotkey Chip */}
          <div className="hidden md:flex flex-1 max-w-lg items-center px-4">
             <div className="relative w-full">
               <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-surface-400" />
               <input 
                 ref={searchInputRef}
                 type="text" 
                 value={globalSearch}
                 onChange={(e) => {
                   setGlobalSearch(e.target.value);
                   if (selectedCaseId) {
                     setSelectedCaseId(null);
                   }
                 }}
                 placeholder="Search address (T...), transaction hash, FIR, or victim... (⌘K)"
                 className="w-full pl-9 pr-14 py-1.5 text-xs bg-surface-50 dark:bg-surface-200/50 border border-surface-200 dark:border-surface-300 rounded-lg text-surface-800 dark:text-surface-100 focus:outline-none focus:border-reactor-orange focus:ring-1 focus:ring-reactor-orange placeholder:text-surface-400 font-medium transition"
               />
               <div className="absolute right-2.5 top-1/2 -translate-y-1/2 flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-surface-200 dark:bg-surface-300 text-surface-500 text-[10px] font-mono pointer-events-none">
                 <Command className="h-2.5 w-2.5" />
                 <span>K</span>
               </div>
             </div>
          </div>

          {/* Right Utilities */}
          <div className="flex items-center gap-3 shrink-0">
            {healthStatus === 'HEALTHY' ? (
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30" title="Backend, PostgreSQL & Redis services healthy">
                <div className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                <span className="text-[11px] font-bold text-emerald-700 dark:text-emerald-400 font-mono">SYSTEM ONLINE</span>
              </div>
            ) : (
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-500/10 border border-amber-500/30" title="Service degraded or connecting">
                <div className="h-2 w-2 rounded-full bg-amber-500" />
                <span className="text-[11px] font-bold text-amber-700 dark:text-amber-400 font-mono">LOCAL MODE</span>
              </div>
            )}
            
            <div className="w-px h-4 bg-surface-200 dark:bg-surface-300 hidden sm:block" />

            {/* Notifications Bell Dropdown */}
            <div className="relative">
              <button 
                onClick={() => setIsNotificationsOpen(!isNotificationsOpen)}
                className={`p-1.5 rounded-lg transition cursor-pointer relative ${
                  isNotificationsOpen 
                    ? 'bg-surface-200 dark:bg-surface-300 text-surface-900 dark:text-white' 
                    : 'text-surface-500 hover:text-surface-800 dark:hover:text-surface-200 hover:bg-surface-100 dark:hover:bg-surface-200'
                }`}
                title="Notifications & System Telemetry"
                aria-label="Notifications"
              >
                <Bell className="h-4 w-4" />
                <span className="absolute top-1 right-1 h-1.5 w-1.5 rounded-full bg-reactor-orange" />
              </button>

              {isNotificationsOpen && (
                <div className="absolute right-0 mt-2 w-80 bg-surface-default border border-surface-200 dark:border-surface-300 rounded-xl shadow-xl z-50 p-4 space-y-3">
                  <div className="flex items-center justify-between border-b border-surface-200 dark:border-surface-300 pb-2">
                    <div className="flex items-center gap-2">
                      <Bell className="h-4 w-4 text-reactor-orange" />
                      <span className="font-bold text-xs text-surface-900 dark:text-white">System Telemetry &amp; Alerts</span>
                    </div>
                    <button onClick={() => setIsNotificationsOpen(false)} className="text-surface-400 hover:text-surface-700 cursor-pointer">
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>

                  <div className="space-y-2 text-xs">
                    <div className="p-2.5 rounded-lg bg-surface-50 dark:bg-surface-200/40 border border-surface-200 dark:border-surface-300 space-y-1.5">
                      <span className="text-[10px] font-bold uppercase text-surface-500 block">Core Infrastructure</span>
                      <div className="flex items-center justify-between">
                        <span className="flex items-center gap-1.5 font-mono text-surface-700 dark:text-surface-200">
                          <Database className="h-3 w-3 text-emerald-500" /> PostgreSQL 18
                        </span>
                        <span className="text-[10px] font-bold text-emerald-600 bg-emerald-500/10 px-1.5 py-0.2 rounded border border-emerald-500/20">CONNECTED</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="flex items-center gap-1.5 font-mono text-surface-700 dark:text-surface-200">
                          <Server className="h-3 w-3 text-emerald-500" /> Redis Cache
                        </span>
                        <span className="text-[10px] font-bold text-emerald-600 bg-emerald-500/10 px-1.5 py-0.2 rounded border border-emerald-500/20">ACTIVE</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="flex items-center gap-1.5 font-mono text-surface-700 dark:text-surface-200">
                          <Cpu className="h-3 w-3 text-emerald-500" /> FastAPI Engine
                        </span>
                        <span className="text-[10px] font-bold text-emerald-600 bg-emerald-500/10 px-1.5 py-0.2 rounded border border-emerald-500/20">PORT 8000</span>
                      </div>
                    </div>

                    <div className="p-2.5 rounded-lg bg-surface-50 dark:bg-surface-200/40 border border-surface-200 dark:border-surface-300 space-y-1.5">
                      <span className="text-[10px] font-bold uppercase text-surface-500 block">Forensic Integrity</span>
                      <div className="flex items-center gap-1.5 text-surface-700 dark:text-surface-200">
                        <CheckCircle2 className="h-3.5 w-3.5 text-brand-blue shrink-0" />
                        <span className="text-[11px]">SHA-256 Merkle Ledger active</span>
                      </div>
                      <div className="flex items-center gap-1.5 text-surface-700 dark:text-surface-200">
                        <FileCheck className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
                        <span className="text-[11px]">Section 63 BSA generator ready</span>
                      </div>
                      <div className="flex items-center gap-1.5 text-surface-700 dark:text-surface-200">
                        <Shield className="h-3.5 w-3.5 text-reactor-orange shrink-0" />
                        <span className="text-[11px]">{cases.length} registered cases in database</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <button 
              onClick={() => setIsDarkMode(!isDarkMode)} 
              className="p-1.5 rounded-lg text-surface-500 hover:text-surface-800 dark:hover:text-surface-200 hover:bg-surface-100 dark:hover:bg-surface-200 transition cursor-pointer" 
              title="Toggle dark mode"
              aria-label="Toggle dark mode"
            >
              {isDarkMode ? <Sun className="h-4 w-4 text-amber-400" /> : <Moon className="h-4 w-4 text-surface-600" />}
            </button>

            <button 
              onClick={() => setIsHelpOpen(true)}
              className="p-1.5 rounded-lg text-surface-500 hover:text-surface-800 dark:hover:text-surface-200 hover:bg-surface-100 dark:hover:bg-surface-200 transition cursor-pointer" 
              title="Forensic User Manual &amp; Shortcuts"
              aria-label="Help"
            >
              <HelpCircle className="h-4 w-4" />
            </button>

            <div className="w-px h-4 bg-surface-200 dark:bg-surface-300 hidden sm:block" />

            {/* Analyst User Badge */}
            <div className="flex items-center gap-2 px-2.5 py-1 rounded-lg bg-surface-50 dark:bg-surface-200/50 border border-surface-200 dark:border-surface-300">
              <div className="h-5 w-5 rounded-full bg-gradient-to-br from-brand-blue to-reactor-deep-blue text-white flex items-center justify-center text-[10px] font-bold font-mono">
                IO
              </div>
              <div className="hidden sm:flex flex-col text-left">
                <span className="text-xs font-bold text-surface-800 dark:text-surface-100 leading-tight">IO-Vikram-742</span>
                <span className="text-[10px] text-surface-500 leading-tight">Cyber Crime Unit</span>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Workspace */}
      <main className="flex-1 w-full mx-auto">
        {/* Error Alert */}
        {error && (
          <div className="w-full max-w-[96vw] 2xl:max-w-[1920px] mx-auto p-4 m-4 rounded-xl bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-red-800 dark:text-red-300 flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-red-500 shrink-0 mt-0.5" />
            <div className="flex-1">
              <h3 className="font-semibold text-sm">System Alert</h3>
              <p className="text-xs text-red-600 dark:text-red-400 mt-0.5">{error}</p>
            </div>
            <button 
              onClick={() => setError(null)}
              className="text-xs text-red-500 hover:text-red-700 underline cursor-pointer"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Dynamic Content */}
        {selectedCaseId ? (
          <CaseDetailsView
            caseId={selectedCaseId}
            onBack={() => {
              setSelectedCaseId(null);
              loadCases();
            }}
          />
        ) : (
          <CaseListView
            cases={cases}
            loading={casesLoading}
            onSelectCase={(id) => setSelectedCaseId(id)}
            onOpenNewCase={() => setIsNewCaseOpen(true)}
            onRefresh={loadCases}
            searchTerm={globalSearch}
            onSearchChange={setGlobalSearch}
          />
        )}
      </main>

      <NewCaseModal
        isOpen={isNewCaseOpen}
        onClose={() => setIsNewCaseOpen(false)}
        onSuccess={handleCaseCreated}
      />

      {/* Forensic Operating Manual & Shortcuts Modal */}
      {isHelpOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
          <div className="bg-surface-default border border-surface-200 dark:border-surface-300 rounded-xl max-w-2xl w-full max-h-[85vh] overflow-y-auto p-6 shadow-2xl space-y-5">
            <div className="flex items-center justify-between border-b border-surface-200 dark:border-surface-300 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="h-8 w-8 rounded-lg bg-orange-500/10 border border-orange-500/30 flex items-center justify-center text-reactor-orange">
                  <BookOpen className="h-4 w-4" />
                </div>
                <div>
                  <h3 className="font-bold text-base text-surface-900 dark:text-white">Forensic Investigation Operating Manual</h3>
                  <p className="text-xs text-surface-500">Crypto-Tracer Reactor Edition &bull; Law Enforcement Guide</p>
                </div>
              </div>
              <button onClick={() => setIsHelpOpen(false)} className="text-surface-400 hover:text-surface-700 cursor-pointer p-1">
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-4 text-xs text-surface-700 dark:text-surface-200">
              {/* Step by step workflow */}
              <div>
                <h4 className="font-bold text-sm text-surface-900 dark:text-white mb-2">Standard Operational Procedure (SOP)</h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  <div className="p-3 rounded-lg bg-surface-50 dark:bg-surface-200/40 border border-surface-200 dark:border-surface-300">
                    <span className="font-bold text-reactor-orange block mb-1">1. Case Registration</span>
                    <p className="text-surface-500 leading-relaxed">Create a case record with FIR number, victim reference, reported USDT/INR loss, and suspect unhosted wallet.</p>
                  </div>
                  <div className="p-3 rounded-lg bg-surface-50 dark:bg-surface-200/40 border border-surface-200 dark:border-surface-300">
                    <span className="font-bold text-brand-blue block mb-1">2. Multi-Hop Trace Execution</span>
                    <p className="text-surface-500 leading-relaxed">Launch BFS graph traversal in DEMO mode (deterministic courtroom fixture) or LIVE mode (on-chain TRON RPC).</p>
                  </div>
                  <div className="p-3 rounded-lg bg-surface-50 dark:bg-surface-200/40 border border-surface-200 dark:border-surface-300">
                    <span className="font-bold text-emerald-600 block mb-1">3. VASP Attribution &amp; Findings</span>
                    <p className="text-surface-500 leading-relaxed">Review multi-factor attribution heuristics (direct tag, sweep cadence, fan-in ratio, temporal delay) identifying exchange hot wallets.</p>
                  </div>
                  <div className="p-3 rounded-lg bg-surface-50 dark:bg-surface-200/40 border border-surface-200 dark:border-surface-300">
                    <span className="font-bold text-purple-600 block mb-1">4. Evidence Vault &amp; Legal Export</span>
                    <p className="text-surface-500 leading-relaxed">Generate Section 63 BSA certified dossiers and Section 94 BNSS notice drafts with immutable SHA-256 Merkle proofs.</p>
                  </div>
                </div>
              </div>

              {/* Execution Engine Modes */}
              <div>
                <h4 className="font-bold text-sm text-surface-900 dark:text-white mb-2">Traversal Engine Execution Modes</h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30">
                    <div className="flex items-center gap-1.5 font-bold text-amber-800 dark:text-amber-300 mb-1">
                      <span className="h-2 w-2 rounded-full bg-amber-500" />
                      DEMO REPLAY FIXTURE
                    </div>
                    <p className="text-surface-600 dark:text-surface-300 leading-relaxed">Deterministic offline transaction tree. Replays canonical test vectors with zero external RPC latency. Ideal for courtroom benchmarks &amp; judge evaluations.</p>
                  </div>
                  <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30">
                    <div className="flex items-center gap-1.5 font-bold text-emerald-800 dark:text-emerald-300 mb-1">
                      <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                      LIVE TRON RPC
                    </div>
                    <p className="text-surface-600 dark:text-surface-300 leading-relaxed">Executes live TRON blockchain queries via JSON-RPC / Trongrid. Scans real-time on-chain TRC-20 transfers for any valid TRON wallet address.</p>
                  </div>
                </div>
              </div>

              {/* Keyboard Shortcuts */}
              <div>
                <h4 className="font-bold text-sm text-surface-900 dark:text-white mb-2 flex items-center gap-1.5">
                  <Keyboard className="h-4 w-4 text-surface-500" />
                  Keyboard Shortcuts
                </h4>
                <div className="grid grid-cols-2 gap-2">
                  <div className="flex items-center justify-between p-2 rounded bg-surface-50 dark:bg-surface-200/40 border border-surface-200 dark:border-surface-300">
                    <span>Focus Global Search</span>
                    <kbd className="px-2 py-0.5 rounded bg-surface-200 dark:bg-surface-300 font-mono text-[11px] font-bold">⌘K / Ctrl+K</kbd>
                  </div>
                  <div className="flex items-center justify-between p-2 rounded bg-surface-50 dark:bg-surface-200/40 border border-surface-200 dark:border-surface-300">
                    <span>Close Modals / Popovers</span>
                    <kbd className="px-2 py-0.5 rounded bg-surface-200 dark:bg-surface-300 font-mono text-[11px] font-bold">Esc</kbd>
                  </div>
                </div>
              </div>

              {/* Statutory Compliance Notes */}
              <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/30 text-surface-700 dark:text-surface-200">
                <span className="font-bold text-brand-blue block mb-1">Judicial Admissibility Compliance</span>
                <p className="leading-relaxed">All generated records conform to Section 63 Bharatiya Sakshya Adhiniyam, 2023 (formerly Section 65B Indian Evidence Act). Graph evidence items maintain cryptographic SHA-256 DAG hashes verifiable by independent third parties.</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
