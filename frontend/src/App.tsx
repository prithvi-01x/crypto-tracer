import { useState, useEffect } from 'react';
import { 
  Shield, 
  Search, 
  Bell, 
  HelpCircle, 
  Moon, 
  Sun, 
  AlertCircle,
  Command
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
      <header className="border-b border-surface-200 dark:border-surface-300 bg-surface-default dark:bg-surface-100 px-6 py-2.5 sticky top-0 z-40 shadow-xs transition-colors">
        <div className="max-w-[1440px] mx-auto flex items-center justify-between gap-4">
          
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
                 type="text" 
                 value={globalSearch}
                 onChange={(e) => {
                   setGlobalSearch(e.target.value);
                   if (selectedCaseId) {
                     setSelectedCaseId(null);
                   }
                 }}
                 placeholder="Search address (T...), transaction hash, FIR, or victim..."
                 className="w-full pl-9 pr-14 py-1.5 text-xs bg-surface-50 dark:bg-surface-200/50 border border-surface-200 dark:border-surface-300 rounded-lg text-surface-800 dark:text-surface-100 focus:outline-none focus:border-reactor-orange focus:ring-1 focus:ring-reactor-orange placeholder:text-surface-400 font-medium transition"
               />
               <div className="absolute right-2.5 top-1/2 -translate-y-1/2 flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-surface-200 dark:bg-surface-300 text-surface-500 text-[10px] font-mono">
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

            <button 
              className="p-1.5 rounded-lg text-surface-500 hover:text-surface-800 dark:hover:text-surface-200 hover:bg-surface-100 dark:hover:bg-surface-200 transition"
              title="Notifications & System Alerts"
              aria-label="Notifications"
            >
              <Bell className="h-4 w-4" />
            </button>

            <button 
              onClick={() => setIsDarkMode(!isDarkMode)} 
              className="p-1.5 rounded-lg text-surface-500 hover:text-surface-800 dark:hover:text-surface-200 hover:bg-surface-100 dark:hover:bg-surface-200 transition cursor-pointer" 
              title="Toggle dark mode"
              aria-label="Toggle dark mode"
            >
              {isDarkMode ? <Sun className="h-4 w-4 text-amber-400" /> : <Moon className="h-4 w-4 text-surface-600" />}
            </button>

            <button 
              className="p-1.5 rounded-lg text-surface-500 hover:text-surface-800 dark:hover:text-surface-200 hover:bg-surface-100 dark:hover:bg-surface-200 transition"
              title="Forensic User Manual"
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
          <div className="max-w-[1440px] mx-auto p-4 m-4 rounded-xl bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-red-800 dark:text-red-300 flex items-start gap-3">
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
    </div>
  );
}
