import { useState, useEffect } from 'react';
import { 
  Shield, 
  Database, 
  Zap, 
  Server, 
  UserCheck, 
  RefreshCw, 
  AlertCircle,
  Activity,
  FileCode2,
  FolderLock,
  Plus
} from 'lucide-react';
import type { CaseItem } from './types/case';
import { getCases } from './api/cases';
import { CaseListView } from './components/cases/CaseListView';
import { CaseDetailsView } from './components/cases/CaseDetailsView';
import { NewCaseModal } from './components/cases/NewCaseModal';

interface ServiceHealth {
  status: string;
  latency_ms?: number;
  error?: string | null;
}

interface HealthData {
  status: string;
  app: string;
  environment: string;
  version: string;
  timestamp: string;
  services: {
    database: ServiceHealth;
    redis: ServiceHealth;
  };
}

interface OfficerSession {
  officer_id: string;
  name: string;
  badge_number: string;
  unit: string;
  role: string;
  is_authenticated: boolean;
}

export default function App() {
  const [activeTab, setActiveTab] = useState<'investigations' | 'diagnostics'>('investigations');
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [casesLoading, setCasesLoading] = useState<boolean>(true);
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [isNewCaseOpen, setIsNewCaseOpen] = useState<boolean>(false);

  const [health, setHealth] = useState<HealthData | null>(null);
  const [officer, setOfficer] = useState<OfficerSession | null>(null);
  const [loadingHealth, setLoadingHealth] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const apiUrl = import.meta.env.VITE_API_URL || '/api/v1';

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

  const fetchDiagnostics = async () => {
    setLoadingHealth(true);
    try {
      const [healthRes, officerRes] = await Promise.all([
        fetch(`${apiUrl}/health`),
        fetch(`${apiUrl}/auth/me`),
      ]);

      if (healthRes.ok) {
        const hJson = await healthRes.json();
        setHealth(hJson);
      }
      if (officerRes.ok) {
        const oJson = await officerRes.json();
        setOfficer(oJson);
      }
    } catch (err: any) {
      console.error('Health check failed:', err);
    } finally {
      setLoadingHealth(false);
    }
  };

  useEffect(() => {
    loadCases();
    fetchDiagnostics();
  }, []);

  const handleCaseCreated = (newCaseId: string) => {
    loadCases();
    setSelectedCaseId(newCaseId);
    setActiveTab('investigations');
  };

  return (
    <div className="min-h-screen bg-police-900 text-slate-100 flex flex-col font-sans">
      {/* Top Navigation Bar */}
      <header className="border-b border-police-700/80 bg-police-800/90 px-6 py-3 backdrop-blur sticky top-0 z-40">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg bg-blue-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
              <Shield className="h-5 w-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold tracking-wider text-base text-white">CRYPTO-TRACER</span>
                <span className="px-1.5 py-0.5 text-[10px] font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30 rounded">
                  SIH 2026 #SIH26182
                </span>
                <span className="px-1.5 py-0.5 text-[10px] font-semibold bg-blue-500/20 text-blue-300 border border-blue-500/30 rounded">
                  PHASE 5: GRAPH WORKSTATION
                </span>
              </div>
              <p className="text-xs text-slate-400">
                District Cyber Crime Cell • Forensic Investigation Workstation
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* View Switcher */}
            <div className="flex rounded-lg bg-police-900 p-1 border border-police-700/70 text-xs">
              <button
                onClick={() => {
                  setActiveTab('investigations');
                }}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-md font-semibold transition ${
                  activeTab === 'investigations'
                    ? 'bg-blue-600 text-white shadow'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <FolderLock className="h-3.5 w-3.5" />
                Case Workspace
              </button>
              <button
                onClick={() => setActiveTab('diagnostics')}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-md font-semibold transition ${
                  activeTab === 'diagnostics'
                    ? 'bg-police-700 text-white shadow'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <Activity className="h-3.5 w-3.5" />
                Stack Health
              </button>
            </div>

            {officer && (
              <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-police-700/60 border border-police-600/50 text-xs">
                <div className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                <div>
                  <div className="font-semibold text-slate-200">{officer.name}</div>
                  <div className="text-[10px] text-slate-400">{officer.unit}</div>
                </div>
              </div>
            )}

            <button
              onClick={() => setIsNewCaseOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition shadow-lg shadow-blue-500/20"
            >
              <Plus className="h-4 w-4" />
              New Case
            </button>
          </div>
        </div>
      </header>

      {/* Main Workspace */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 space-y-6">
        {/* Error Alert */}
        {error && (
          <div className="p-4 rounded-xl bg-red-950/50 border border-red-800 text-red-200 flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-red-400 shrink-0 mt-0.5" />
            <div className="flex-1">
              <h3 className="font-semibold text-sm">System Alert</h3>
              <p className="text-xs text-red-300 mt-1">{error}</p>
            </div>
            <button 
              onClick={() => setError(null)}
              className="text-xs text-red-400 hover:text-white underline"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Dynamic Content based on active view */}
        {activeTab === 'investigations' ? (
          selectedCaseId ? (
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
            />
          )
        ) : (
          /* Diagnostics View (Preserved from Phase 0) */
          <div className="space-y-6">
            <div className="p-5 rounded-xl bg-police-800/60 border border-police-700/80 shadow-md flex items-center justify-between">
              <div>
                <h2 className="text-base font-bold text-white">Stack Infrastructure Verification</h2>
                <p className="text-xs text-slate-400 mt-1">
                  Active connection to PostgreSQL relational store, Redis in-memory broker, and FastAPI modular monolith.
                </p>
              </div>
              <button
                onClick={fetchDiagnostics}
                disabled={loadingHealth}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded bg-police-700 hover:bg-police-600 text-white"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${loadingHealth ? 'animate-spin' : ''}`} />
                Re-check Health
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="p-4 rounded-xl bg-police-800/80 border border-police-700/70">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold uppercase text-slate-400">FastAPI</span>
                  <Server className="h-4 w-4 text-blue-400" />
                </div>
                <div className="text-sm font-bold text-white">v0.1.0 Online</div>
                <div className="text-xs text-slate-400 mt-1">{health?.environment || 'development'}</div>
              </div>

              <div className="p-4 rounded-xl bg-police-800/80 border border-police-700/70">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold uppercase text-slate-400">PostgreSQL</span>
                  <Database className="h-4 w-4 text-emerald-400" />
                </div>
                <div className="text-sm font-bold text-white">
                  {health?.services?.database?.status === 'HEALTHY' ? 'Connected' : 'Degraded'}
                </div>
                <div className="text-xs text-slate-400 mt-1">
                  Latency: {health?.services?.database?.latency_ms ?? 'N/A'} ms
                </div>
              </div>

              <div className="p-4 rounded-xl bg-police-800/80 border border-police-700/70">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold uppercase text-slate-400">Redis</span>
                  <Zap className="h-4 w-4 text-amber-400" />
                </div>
                <div className="text-sm font-bold text-white">
                  {health?.services?.redis?.status === 'HEALTHY' ? 'Connected' : 'Degraded'}
                </div>
                <div className="text-xs text-slate-400 mt-1">
                  Latency: {health?.services?.redis?.latency_ms ?? 'N/A'} ms
                </div>
              </div>

              <div className="p-4 rounded-xl bg-police-800/80 border border-police-700/70">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold uppercase text-slate-400">Officer Context</span>
                  <UserCheck className="h-4 w-4 text-purple-400" />
                </div>
                <div className="text-sm font-bold text-white">{officer?.badge_number || 'CYBER-DELHI-4029'}</div>
                <div className="text-xs text-slate-400 mt-1">{officer?.role || 'INVESTIGATING_OFFICER'}</div>
              </div>
            </div>

            <div className="p-5 rounded-xl bg-police-800/50 border border-police-700/70">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <FileCode2 className="h-4 w-4 text-blue-400" />
                  <h3 className="text-sm font-bold text-white">Live Health Payload</h3>
                </div>
                <span className="text-xs font-mono text-slate-400">GET /api/v1/health</span>
              </div>
              <pre className="p-3 rounded-lg bg-police-900/90 border border-police-700/50 text-xs font-mono text-emerald-300 overflow-x-auto max-h-60">
                {health ? JSON.stringify(health, null, 2) : 'Connecting...'}
              </pre>
            </div>
          </div>
        )}
      </main>

      {/* New Case Modal */}
      <NewCaseModal
        isOpen={isNewCaseOpen}
        onClose={() => setIsNewCaseOpen(false)}
        onSuccess={handleCaseCreated}
      />

      {/* Footer */}
      <footer className="border-t border-police-700/50 bg-police-800/40 px-6 py-3 text-center text-xs text-slate-500">
        Crypto-Tracer SIH 2026 Prototype • Team Cipher • District Cyber Crime Cell Forensic Workstation
      </footer>
    </div>
  );
}
