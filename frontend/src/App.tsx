import { useState, useEffect } from 'react';
import { 
  Shield, 
  Search,
  Bell,
  HelpCircle,
  Moon,
  Sun,
  AlertCircle
} from 'lucide-react';
import type { CaseItem } from './types/case';
import { getCases } from './api/cases';
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

  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDarkMode]);


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
    <div className="min-h-screen bg-surface-50 text-surface-800 flex flex-col font-sans">
      {/* Top Navigation Bar */}
      <header className="border-b border-surface-200 bg-surface-default px-6 py-3 sticky top-0 z-40">
        <div className="max-w-[1440px] mx-auto flex items-center justify-between gap-4">
          
          {/* Brand */}
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded text-brand-blue flex items-center justify-center">
              <Shield className="h-6 w-6" />
            </div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-[15px] text-surface-800">Crypto-Tracer | Blockchain Forensic Investigation</span>
            </div>
          </div>

          {/* Center Nav / Global Search (simplified) */}
          <div className="hidden md:flex flex-1 max-w-lg items-center px-4">
             <div className="relative w-full">
               <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-surface-400" />
               <input 
                 type="text" 
                 placeholder="Search address, transaction hash, FIR, or victim..."
                 className="w-full pl-9 pr-4 py-1.5 text-lg bg-surface-50 border border-surface-200 rounded text-surface-800 focus:outline-none focus:border-brand-blue focus:ring-1 focus:ring-brand-blue placeholder:text-surface-400"
               />
             </div>
          </div>

          {/* Right Utilities */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-emerald-50 border border-emerald-100">
              <div className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-base font-semibold text-emerald-700">LIVE TRON RPC</span>
            </div>
            
            <button className="text-surface-500 hover:text-surface-800">
              <Bell className="h-4 w-4" />
            </button>
                        <button onClick={() => setIsDarkMode(!isDarkMode)} className="text-surface-500 hover:text-surface-800">
              {isDarkMode ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
            <button className="text-surface-500 hover:text-surface-800">
              <HelpCircle className="h-4 w-4" />
            </button>

            <div className="flex items-center gap-2 px-3 py-1.5 rounded bg-surface-50 border border-surface-200">
              <div className="h-5 w-5 rounded-full bg-brand-light flex items-center justify-center">
                <span className="text-base font-bold text-brand-blue">IA</span>
              </div>
              <div className="text-base font-medium text-surface-700">Investigator Analyst</div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Workspace */}
      <main className="flex-1 w-full mx-auto">
        {/* Error Alert */}
        {error && (
          <div className="max-w-[1440px] mx-auto p-4 m-4 rounded bg-red-50 border border-red-200 text-red-800 flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-red-500 shrink-0 mt-0.5" />
            <div className="flex-1">
              <h3 className="font-semibold text-lg">System Alert</h3>
              <p className="text-base text-red-600 mt-1">{error}</p>
            </div>
            <button 
              onClick={() => setError(null)}
              className="text-base text-red-500 hover:text-red-700 underline"
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
          <div className="max-w-[1440px] mx-auto p-6">
            <CaseListView
              cases={cases}
              loading={casesLoading}
              onSelectCase={(id) => setSelectedCaseId(id)}
              onOpenNewCase={() => setIsNewCaseOpen(true)}
              onRefresh={loadCases}
            />
          </div>
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
