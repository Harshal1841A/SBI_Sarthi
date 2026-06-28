import { useState, useEffect } from 'react';
import { ThemeProvider } from './hooks/ThemeContext';
import { DemoModeProvider } from './hooks/DemoModeContext';
import { TopAppBar } from './components/TopAppBar';
import { WellnessHub } from './components/WellnessHub';
import { KYCWizard } from './components/KYCWizard';
import { ComplianceCenter } from './components/ComplianceCenter';
import { VoiceWaveformOrb } from './components/VoiceWaveformOrb';
import { BottomNavBar } from './components/BottomNavBar';
import DemoBanner from './components/DemoBanner';
import LoanWorkflow from './components/LoanWorkflow';
import VoiceDemo from './components/VoiceDemo';
import AuditLogViewer from './components/AuditLogViewer';
import ChatInterface from './components/ChatInterface';
import SupervisorDashboard from './components/SupervisorDashboard';
import { systemApi } from './services/api';

type NavTab = 'home' | 'assistant' | 'supervisor' | 'security' | 'workflow' | 'voice' | 'audit';

// ─────────────────────────────────────────────────────────────────
// Health Banner
// ─────────────────────────────────────────────────────────────────
function BackendBanner({ status }: { status: 'checking' | 'up' | 'down' }) {
  if (status === 'checking') return null;
  if (status === 'up') return null;

  return (
    <div className="fixed top-16 left-0 right-0 z-40 flex justify-center px-4 pt-2 pointer-events-none">
      <div className="flex items-center gap-2 bg-error/90 text-white text-xs font-medium px-4 py-2 rounded-full shadow-lg pointer-events-auto animate-fade-in">
        <span className="material-symbols-outlined text-[14px]">wifi_off</span>
        Backend offline — some features unavailable
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────
// Security / Shield view
// ─────────────────────────────────────────────────────────────────
function SecurityView() {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await systemApi.getStats();
      setStats(data);
    } catch (e: any) {
      setError('Could not reach backend. Ensure the server is running.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  return (
    <section className="space-y-4 animate-slide-up">
      <div className="flex items-center justify-between px-1 mb-2">
        <h2 className="font-headline-md text-headline-md text-primary dark:text-primary-fixed-dim">
          Security & Shield
        </h2>
        <button
          id="security-refresh-btn"
          onClick={load}
          disabled={loading}
          className="flex items-center gap-1 text-xs bg-surface-container-low dark:bg-[#1a2840] border border-outline-variant/30 px-3 py-1.5 rounded-full text-on-surface-variant dark:text-outline-variant hover:bg-surface-container transition"
        >
          <span className={`material-symbols-outlined text-[14px] ${loading ? 'animate-spin' : ''}`}>refresh</span>
          Refresh
        </button>
      </div>

      {/* Shield cards */}
      <div className="grid grid-cols-2 gap-3">
        {[
          { icon: 'security', label: 'Input Defense', value: '24 Signatures', color: 'text-secondary dark:text-secondary-fixed-dim' },
          { icon: 'verified_user', label: 'Output Guard', value: 'Active', color: 'text-primary dark:text-primary-fixed-dim' },
          { icon: 'gpp_maybe', label: 'Block Rate', value: '100%', color: 'text-[#14B8A6]' },
          { icon: 'policy', label: 'RBI Aligned', value: 'Enforced', color: 'text-tertiary dark:text-tertiary-fixed-dim' },
        ].map((card) => (
          <div key={card.label} className="glass bg-surface/80 dark:bg-[#131f35]/90 border border-outline-variant/30 dark:border-[#2a3a55]/50 rounded-xl p-4">
            <span className={`material-symbols-outlined text-[22px] ${card.color}`} style={{ fontVariationSettings: "'FILL' 1" }}>{card.icon}</span>
            <p className="font-label-md text-on-surface-variant dark:text-[#b0bcd6] mt-2">{card.label}</p>
            <p className={`font-headline-md text-body-md font-bold ${card.color}`}>{card.value}</p>
          </div>
        ))}
      </div>

      {/* Live stats from backend */}
      <div className="glass bg-surface/80 dark:bg-[#131f35]/90 border border-outline-variant/30 dark:border-[#2a3a55]/50 rounded-xl p-5">
        <h3 className="font-headline-md text-body-md font-semibold text-primary dark:text-primary-fixed-dim mb-4">
          Live System Stats
        </h3>

        {loading && (
          <div className="flex items-center gap-2 text-on-surface-variant dark:text-[#8a9ab8]">
            <span className="material-symbols-outlined text-[16px] animate-spin">progress_activity</span>
            <span className="text-sm">Loading…</span>
          </div>
        )}

        {error && (
          <div className="flex items-start gap-2 bg-error/10 border border-error/30 rounded-lg p-3">
            <span className="material-symbols-outlined text-error text-[18px]">warning</span>
            <p className="text-sm text-error">{error}</p>
          </div>
        )}

        {stats && !loading && (
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: 'Active Sessions', value: stats.active_sessions ?? 0 },
              { label: 'HITL Pending',    value: stats.hitl_pending ?? 0 },
              { label: 'Cache Entries',   value: stats.cache?.size ?? '—' },
            ].map((stat) => (
              <div key={stat.label} className="text-center">
                <p className="text-2xl font-bold text-primary dark:text-primary-fixed-dim">{stat.value}</p>
                <p className="font-label-sm text-on-surface-variant dark:text-[#8a9ab8] mt-0.5">{stat.label}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Audit log shortcut */}
      <ComplianceCenter />
    </section>
  );
}

// ─────────────────────────────────────────────────────────────────
// Home view
// ─────────────────────────────────────────────────────────────────
function HomeView({ backendStatus }: { backendStatus: 'checking' | 'up' | 'down' }) {
  const now = new Date();
  const hour = now.getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';

  return (
    <main className="pt-20 px-4 space-y-6 max-w-lg mx-auto pb-36 animate-slide-up">
      {/* Hero */}
      <section className="mt-4">
        <p className="font-label-md text-label-md text-on-surface-variant dark:text-[#b0bcd6] mb-1">
          {greeting} 👋
        </p>
        <h2 className="font-headline-lg-mobile text-headline-lg-mobile text-primary dark:text-primary-fixed-dim">
          Your Financial Orbit
        </h2>
        {backendStatus === 'up' && (
          <div className="flex items-center gap-1.5 mt-1">
            <div className="w-1.5 h-1.5 rounded-full bg-secondary animate-pulse" />
            <span className="font-label-sm text-[10px] text-secondary dark:text-secondary-fixed-dim font-semibold tracking-wider">SYSTEM ONLINE</span>
          </div>
        )}
      </section>

      <KYCWizard />
      <WellnessHub />
      <ComplianceCenter />
    </main>
  );
}

// ─────────────────────────────────────────────────────────────────
// Root App
// ─────────────────────────────────────────────────────────────────
function App() {
  const [activeTab, setActiveTab] = useState<NavTab>('home');
  const [backendStatus, setBackendStatus] = useState<'checking' | 'up' | 'down'>('checking');

  // Check backend health and auto-fetch demo tokens on mount if not present
  useEffect(() => {
    systemApi.getHealth()
      .then(() => {
        setBackendStatus('up');
        // Check sessionStorage first (migrated), fall back to localStorage (legacy)
        const hasToken = sessionStorage.getItem('sarthi_token') || localStorage.getItem('sarthi_token');
        const hasSup = sessionStorage.getItem('sarthi_supervisor_token') || localStorage.getItem('sarthi_supervisor_token');
        if (!hasToken || !hasSup) {
          systemApi.getDemoToken().then(data => {
            // Write to sessionStorage (per BUG-16 migration) — not localStorage
            if (data.api_token) {
              sessionStorage.setItem('sarthi_token', data.api_token);
              localStorage.removeItem('sarthi_token');
            }
            if (data.supervisor_token) {
              sessionStorage.setItem('sarthi_supervisor_token', data.supervisor_token);
              localStorage.removeItem('sarthi_supervisor_token');
            }
          }).catch(console.error);
        }
      })
      .catch(() => setBackendStatus('down'));
  }, []);

  return (
    <ThemeProvider>
      <DemoModeProvider>
        <div className="min-h-screen bg-[#f4f6fc] dark:bg-[#0a0f1e] text-on-surface dark:text-[#e4eafc] transition-colors duration-300">
          <TopAppBar />
          <DemoBanner />
          <BackendBanner status={backendStatus} />

          {/* Views */}
          {activeTab === 'home' && (
            <HomeView backendStatus={backendStatus} />
          )}

          {activeTab === 'assistant' && (
            <div className="pt-20 px-4 max-w-lg mx-auto pb-36 h-screen animate-slide-up">
              <div className="h-[calc(100vh-200px)] flex flex-col">
                <ChatInterface onVoiceClick={() => setActiveTab('voice')} />
              </div>
            </div>
          )}

          {activeTab === 'workflow' && (
            <div className="pt-20 px-4 max-w-lg mx-auto pb-36 animate-slide-up">
              <LoanWorkflow />
            </div>
          )}

          {activeTab === 'voice' && (
            <div className="pt-20 px-4 max-w-lg mx-auto pb-36 animate-slide-up">
              <VoiceDemo />
            </div>
          )}

          {activeTab === 'supervisor' && (
            <div className="pt-20 px-4 max-w-4xl mx-auto pb-36 animate-slide-up">
              <SupervisorDashboard />
            </div>
          )}

          {activeTab === 'audit' && (
            <div className="pt-20 px-4 max-w-lg mx-auto pb-36 animate-slide-up">
              <AuditLogViewer />
            </div>
          )}

          {activeTab === 'security' && (
            <div className="pt-20 px-4 max-w-lg mx-auto pb-36">
              <SecurityView />
            </div>
          )}

          {/* Voice Orb — only on home and assistant tabs */}
          {(activeTab === 'home' || activeTab === 'assistant') && (
            <VoiceWaveformOrb />
          )}

          <BottomNavBar activeTab={activeTab} onTabChange={setActiveTab} />
        </div>
      </DemoModeProvider>
    </ThemeProvider>
  );
}

export default App;
