import { useState, useEffect } from 'react';
import { 
  Shield, 
  Database, 
  Zap, 
  Server, 
  UserCheck, 
  RefreshCw, 
  CheckCircle2, 
  AlertCircle,
  Activity,
  FileCode2
} from 'lucide-react';

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
  const [health, setHealth] = useState<HealthData | null>(null);
  const [officer, setOfficer] = useState<OfficerSession | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastCheck, setLastCheck] = useState<string>('');

  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

  const fetchSystemStatus = async () => {
    setLoading(true);
    setError(null);
    try {
      const [healthRes, officerRes] = await Promise.all([
        fetch(`${apiUrl}/health`),
        fetch(`${apiUrl}/auth/me`),
      ]);

      if (!healthRes.ok) {
        throw new Error(`Health API responded with status ${healthRes.status}`);
      }
      if (!officerRes.ok) {
        throw new Error(`Auth API responded with status ${officerRes.status}`);
      }

      const healthJson = await healthRes.json();
      const officerJson = await officerRes.json();

      setHealth(healthJson);
      setOfficer(officerJson);
      setLastCheck(new Date().toLocaleTimeString());
    } catch (err: any) {
      console.error('Failed to communicate with backend:', err);
      setError(err.message || 'Failed to connect to backend service');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSystemStatus();
  }, []);

  return (
    <div className="min-h-screen bg-police-900 text-slate-100 flex flex-col font-sans">
      {/* Top Navigation Bar */}
      <header className="border-b border-police-700/80 bg-police-800/90 px-6 py-3.5 backdrop-blur sticky top-0 z-50">
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
                <span className="px-1.5 py-0.5 text-[10px] font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 rounded">
                  PHASE 0: FOUNDATION
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Automated VASP Attribution & Forensic Trace Workstation
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            {officer && (
              <div className="flex items-center gap-2.5 px-3 py-1.5 rounded-lg bg-police-700/60 border border-police-600/50 text-xs">
                <div className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                <div>
                  <div className="font-semibold text-slate-200">{officer.name}</div>
                  <div className="text-[10px] text-slate-400">{officer.unit}</div>
                </div>
              </div>
            )}
            <button
              onClick={fetchSystemStatus}
              disabled={loading}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition disabled:opacity-50 shadow"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
              Verify Backend
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
            <div>
              <h3 className="font-semibold text-sm">Backend Connectivity Issue</h3>
              <p className="text-xs text-red-300 mt-1">{error}</p>
              <p className="text-xs text-slate-400 mt-1">
                Make sure the FastAPI backend is running at <code className="text-amber-400">{apiUrl}</code>.
              </p>
            </div>
          </div>
        )}

        {/* Phase 0 Status Banner */}
        <div className="p-5 rounded-xl bg-police-800/60 border border-police-700/80 shadow-md">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-white">System Architecture & Core Contract Verification</h2>
                <span className="text-xs text-slate-400">
                  {lastCheck ? `Checked at ${lastCheck}` : 'Checking...'}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-1">
                Phase 0 establishes the modular monolith foundation, Docker stack, PostgreSQL persistence, Redis cache/queue, and verified frontend ↔ backend communication.
              </p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-xs text-slate-400">Stack Status:</span>
              <span className={`px-2.5 py-1 text-xs font-semibold rounded-full border ${
                health?.status === 'HEALTHY' 
                  ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40' 
                  : 'bg-amber-500/20 text-amber-300 border-amber-500/40'
              }`}>
                {health?.status || 'INITIALIZING'}
              </span>
            </div>
          </div>
        </div>

        {/* 4 Service Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Card 1: FastAPI */}
          <div className="p-4 rounded-xl bg-police-800/80 border border-police-700/70 hover:border-police-600 transition">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Server className="h-4 w-4 text-blue-400" />
                <span className="text-xs font-semibold uppercase text-slate-400">API Gateway</span>
              </div>
              {health ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              ) : (
                <AlertCircle className="h-4 w-4 text-amber-400" />
              )}
            </div>
            <div className="text-sm font-bold text-white">FastAPI v0.1.0</div>
            <div className="text-xs text-slate-400 mt-1">REST OpenAPI 3.1</div>
            <div className="mt-3 pt-3 border-t border-police-700/50 flex items-center justify-between text-xs text-slate-400">
              <span>Environment:</span>
              <span className="font-mono text-slate-300">{health?.environment || 'development'}</span>
            </div>
          </div>

          {/* Card 2: PostgreSQL */}
          <div className="p-4 rounded-xl bg-police-800/80 border border-police-700/70 hover:border-police-600 transition">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Database className="h-4 w-4 text-emerald-400" />
                <span className="text-xs font-semibold uppercase text-slate-400">Relational DB</span>
              </div>
              {health?.services?.database?.status === 'HEALTHY' ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              ) : (
                <AlertCircle className="h-4 w-4 text-amber-400" />
              )}
            </div>
            <div className="text-sm font-bold text-white">PostgreSQL 16</div>
            <div className="text-xs text-slate-400 mt-1">SQLAlchemy Async Engine</div>
            <div className="mt-3 pt-3 border-t border-police-700/50 flex items-center justify-between text-xs text-slate-400">
              <span>Latency:</span>
              <span className="font-mono text-slate-300">
                {health?.services?.database?.latency_ms !== undefined 
                  ? `${health.services.database.latency_ms} ms` 
                  : 'N/A'}
              </span>
            </div>
          </div>

          {/* Card 3: Redis */}
          <div className="p-4 rounded-xl bg-police-800/80 border border-police-700/70 hover:border-police-600 transition">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Zap className="h-4 w-4 text-amber-400" />
                <span className="text-xs font-semibold uppercase text-slate-400">Cache / Queue</span>
              </div>
              {health?.services?.redis?.status === 'HEALTHY' ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              ) : (
                <AlertCircle className="h-4 w-4 text-amber-400" />
              )}
            </div>
            <div className="text-sm font-bold text-white">Redis 7 (Async)</div>
            <div className="text-xs text-slate-400 mt-1">Trace Cache & Rate Limits</div>
            <div className="mt-3 pt-3 border-t border-police-700/50 flex items-center justify-between text-xs text-slate-400">
              <span>Latency:</span>
              <span className="font-mono text-slate-300">
                {health?.services?.redis?.latency_ms !== undefined 
                  ? `${health.services.redis.latency_ms} ms` 
                  : 'N/A'}
              </span>
            </div>
          </div>

          {/* Card 4: Officer Context */}
          <div className="p-4 rounded-xl bg-police-800/80 border border-police-700/70 hover:border-police-600 transition">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <UserCheck className="h-4 w-4 text-purple-400" />
                <span className="text-xs font-semibold uppercase text-slate-400">Mock Session</span>
              </div>
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
            </div>
            <div className="text-sm font-bold text-white">{officer?.badge_number || 'CYBER-DELHI-4029'}</div>
            <div className="text-xs text-slate-400 mt-1">{officer?.role || 'INVESTIGATING_OFFICER'}</div>
            <div className="mt-3 pt-3 border-t border-police-700/50 flex items-center justify-between text-xs text-slate-400">
              <span>State:</span>
              <span className="text-emerald-400 font-semibold">AUTHENTICATED</span>
            </div>
          </div>
        </div>

        {/* Live Health JSON Inspection Panel */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="p-5 rounded-xl bg-police-800/50 border border-police-700/70">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <FileCode2 className="h-4 w-4 text-blue-400" />
                <h3 className="text-sm font-bold text-white">Live Backend Contract Payload</h3>
              </div>
              <span className="text-[11px] font-mono text-slate-400">GET /api/v1/health</span>
            </div>
            <pre className="p-3 rounded-lg bg-police-900/90 border border-police-700/50 text-xs font-mono text-emerald-300 overflow-x-auto max-h-60">
              {health ? JSON.stringify(health, null, 2) : 'Connecting...'}
            </pre>
          </div>

          <div className="p-5 rounded-xl bg-police-800/50 border border-police-700/70">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-amber-400" />
                <h3 className="text-sm font-bold text-white">Implementation Pipeline Roadmap</h3>
              </div>
              <span className="text-[11px] text-slate-400">Source: PHASES.md</span>
            </div>
            <div className="space-y-2 text-xs">
              <div className="p-2 rounded bg-police-700/40 border border-emerald-500/40 flex items-center justify-between">
                <span className="font-semibold text-emerald-300">Phase 0: Project Foundation</span>
                <span className="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[10px]">COMPLETE</span>
              </div>
              <div className="p-2 rounded bg-police-900/40 border border-police-700/40 flex items-center justify-between opacity-75">
                <span className="text-slate-300">Phase 1: Case Management & Intake</span>
                <span className="text-slate-500 text-[10px]">NEXT PHASE</span>
              </div>
              <div className="p-2 rounded bg-police-900/40 border border-police-700/40 flex items-center justify-between opacity-50">
                <span className="text-slate-400">Phase 2: TRON TRC-20 Data Ingestion</span>
                <span className="text-slate-500 text-[10px]">QUEUED</span>
              </div>
              <div className="p-2 rounded bg-police-900/40 border border-police-700/40 flex items-center justify-between opacity-50">
                <span className="text-slate-400">Phase 3-5: BFS Graph & Pruning Engine</span>
                <span className="text-slate-500 text-[10px]">QUEUED</span>
              </div>
              <div className="p-2 rounded bg-police-900/40 border border-police-700/40 flex items-center justify-between opacity-50">
                <span className="text-slate-400">Phase 6-8: Explainable VASP Attribution & BNSS 94</span>
                <span className="text-slate-500 text-[10px]">QUEUED</span>
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-police-700/50 bg-police-800/40 px-6 py-3 text-center text-xs text-slate-500">
        Crypto-Tracer SIH 2026 Prototype • Team Cipher • District Cyber Crime Cell Forensic Workstation
      </footer>
    </div>
  );
}
