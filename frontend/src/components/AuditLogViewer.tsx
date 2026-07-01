import { useState, useEffect } from 'react';
import { systemApi } from '../services/api';
import { AuditLogEntry } from '../types';
import { Shield, Link, Clock, Hash, AlertTriangle, CheckCircle, FileText, Lock } from 'lucide-react';

export default function AuditLogViewer() {
  // isDemo removed — AuditLogViewer renders the same content in all modes;
  // demo data is provided as a fallback inside loadLogs()'s catch block.
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedLog, setSelectedLog] = useState<AuditLogEntry | null>(null);
  const [chainValid, setChainValid] = useState(true);

  const loadLogs = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await systemApi.getAuditLogs(undefined, 50);
      const entries = data.logs || [];
      setLogs(entries);
      
      // Verify chain integrity
      let valid = true;
      for (let i = 1; i < entries.length; i++) {
        if (entries[i].prev_hash !== entries[i - 1].hash) {
          valid = false;
          break;
        }
      }
      setChainValid(valid);
    } catch (e: any) {
      setError('Failed to load audit logs. Backend may be offline.');
      // Fallback demo data
      setLogs(getDemoAuditLogs());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLogs();
  }, []);

  const getEventIcon = (type: string) => {
    switch (type) {
      case 'shield_block': return <Shield className="w-4 h-4 text-error" />;
      case 'shield_flag': return <AlertTriangle className="w-4 h-4 text-amber-500" />;
      case 'hitl_approval': return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'hitl_interrupt': return <Clock className="w-4 h-4 text-amber-500" />;
      case 'consent_grant': return <Lock className="w-4 h-4 text-primary" />;
      case 'agent_decision': return <FileText className="w-4 h-4 text-secondary" />;
      default: return <FileText className="w-4 h-4 text-on-surface-variant" />;
    }
  };

  const getEventColor = (type: string) => {
    switch (type) {
      case 'shield_block': return 'bg-error/10 border-error/20 text-error dark:text-red-400';
      case 'shield_flag': return 'bg-amber-500/10 border-amber-500/20 text-amber-600 dark:text-amber-400';
      case 'hitl_approval': return 'bg-green-500/10 border-green-500/20 text-green-600 dark:text-green-400';
      case 'hitl_interrupt': return 'bg-amber-500/10 border-amber-500/20 text-amber-600 dark:text-amber-400';
      case 'consent_grant': return 'bg-primary/10 border-primary/20 text-primary dark:text-primary-fixed-dim';
      default: return 'bg-surface-container dark:bg-dark-surface-container border-outline-variant/30 text-on-surface';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-headline-md text-headline-md text-primary dark:text-primary-fixed-dim">
            Immutable Audit Trail
          </h2>
          <p className="text-sm text-on-surface-variant dark:text-[#8a9ab8] mt-1">
            SHA-256 + prev_hash chain. Tamper-evident for RBI FREE-AI compliance.
          </p>
        </div>
        <div className={`
          flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium
          ${chainValid ? 'bg-green-500/10 text-green-600' : 'bg-error/10 text-error'}
        `}>
          {chainValid ? <CheckCircle className="w-3.5 h-3.5" /> : <AlertTriangle className="w-3.5 h-3.5" />}
          Chain {chainValid ? 'Valid' : 'Broken'}
        </div>
      </div>

      {/* Chain visualization */}
      {logs.length > 1 && (
        <div className="glass bg-surface/80 dark:bg-[#131f35]/90 border border-outline-variant/30 rounded-xl p-4 overflow-x-auto">
          <div className="flex items-center gap-1 min-w-max">
            {logs.slice(0, 8).map((log, i) => (
              <div key={i} className="flex items-center gap-1">
                <div 
                  className="w-8 h-8 rounded-full flex items-center justify-center text-[10px] font-bold cursor-pointer hover:scale-110 transition"
                  style={{ 
                    background: i === 0 ? '#00447C' : `rgba(0, 68, 124, ${Math.max(0.3, 1 - i * 0.1)})`,
                    color: 'white'
                  }}
                  onClick={() => setSelectedLog(log)}
                  title={log.event_type}
                >
                  {i + 1}
                </div>
                {i < Math.min(logs.length, 8) - 1 && (
                  <Link className="w-3 h-3 text-on-surface-variant opacity-50" />
                )}
              </div>
            ))}
            {logs.length > 8 && (
              <span className="text-xs text-on-surface-variant ml-1">+{logs.length - 8} more</span>
            )}
          </div>
        </div>
      )}

      {/* Log entries */}
      <div className="space-y-2">
        {loading && (
          <div className="text-center py-8 text-on-surface-variant">
            <div className="animate-spin w-6 h-6 border-2 border-primary border-t-transparent rounded-full mx-auto mb-2" />
            Loading audit chain...
          </div>
        )}

        {error && (
          <div className="text-center py-6 bg-error/5 border border-error/20 rounded-xl text-error text-sm">
            {error}
          </div>
        )}

        {!loading && logs.length === 0 && (
          <div className="text-center py-8 text-on-surface-variant">
            No audit events yet. Interact with Sarthi to generate events.
          </div>
        )}

        {logs.map((log, index) => (
          <div
            key={index}
            onClick={() => setSelectedLog(log)}
            className={`
              glass border rounded-xl p-4 cursor-pointer transition hover:shadow-md
              ${getEventColor(log.event_type)}
              ${selectedLog?.hash === log.hash ? 'ring-2 ring-primary/30' : ''}
            `}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-3">
                {getEventIcon(log.event_type)}
                <div>
                  <p className="text-sm font-semibold">{log.event_type}</p>
                  <p className="text-xs opacity-70">
                    {log.agent_name} • {new Date(log.timestamp * 1000).toLocaleString()}
                  </p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-[10px] font-mono opacity-50">{log.hash.slice(0, 16)}...</p>
              </div>
            </div>

            {log.decision && Object.keys(log.decision).length > 0 && (
              <div className="mt-2 pl-8">
                <p className="text-xs opacity-80">
                  Decision: {JSON.stringify(log.decision).slice(0, 100)}...
                </p>
              </div>
            )}

            {/* Hash chain link */}
            <div className="mt-2 flex items-center gap-2 text-[10px] opacity-50">
              <Hash className="w-3 h-3" />
              <span className="font-mono">prev: {log.prev_hash.slice(0, 20)}...</span>
            </div>
          </div>
        ))}
      </div>

      {/* Detail Modal */}
      {selectedLog && (
        <div 
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
          onClick={() => setSelectedLog(null)}
        >
          <div 
            className="bg-white dark:bg-[#0f1729] rounded-xl p-6 w-full max-w-lg max-h-[80vh] overflow-y-auto shadow-2xl flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-primary">Audit Event Detail</h3>
              <button 
                onClick={() => setSelectedLog(null)}
                className="p-2 rounded-full hover:bg-gray-100 dark:hover:bg-gray-800 text-on-surface-variant transition"
                aria-label="Close"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-sm">
              <div className="grid grid-cols-3 gap-2">
                <span className="text-on-surface-variant">Event Type:</span>
                <span className="col-span-2 font-medium">{selectedLog.event_type}</span>
              </div>
              <div className="grid grid-cols-3 gap-2">
                <span className="text-on-surface-variant">Agent:</span>
                <span className="col-span-2 font-medium">{selectedLog.agent_name}</span>
              </div>
              <div className="grid grid-cols-3 gap-2">
                <span className="text-on-surface-variant">Session:</span>
                <span className="col-span-2 font-mono text-xs">{selectedLog.session_id}</span>
              </div>
              <div className="grid grid-cols-3 gap-2">
                <span className="text-on-surface-variant">Timestamp:</span>
                <span className="col-span-2">{new Date(selectedLog.timestamp * 1000).toISOString()}</span>
              </div>

              <div className="border-t border-outline-variant/30 pt-3">
                <span className="text-on-surface-variant text-xs uppercase tracking-wider">Hash</span>
                <p className="font-mono text-xs break-all mt-1 bg-surface-container dark:bg-[#1a2840] p-2 rounded">{selectedLog.hash}</p>
              </div>

              <div className="border-t border-outline-variant/30 pt-3">
                <span className="text-on-surface-variant text-xs uppercase tracking-wider">Previous Hash</span>
                <p className="font-mono text-xs break-all mt-1 bg-surface-container dark:bg-[#1a2840] p-2 rounded">{selectedLog.prev_hash}</p>
              </div>

              <div className="border-t border-outline-variant/30 pt-3">
                <span className="text-on-surface-variant text-xs uppercase tracking-wider">Decision</span>
                <pre className="mt-1 text-xs bg-surface-container dark:bg-[#1a2840] p-2 rounded overflow-x-auto whitespace-pre-wrap break-words">
                  {JSON.stringify(selectedLog.decision, null, 2)}
                </pre>
              </div>
            </div>
            
            <div className="mt-6 pt-4 border-t border-outline-variant/30">
              <button
                onClick={() => setSelectedLog(null)}
                className="w-full py-3 rounded-lg bg-[#00447C] text-white font-medium hover:bg-[#003366] transition shadow"
              >
                Back to Audit Logs
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Demo audit data for fallback
function getDemoAuditLogs(): AuditLogEntry[] {
  return [
    {
      event_type: 'agent_decision',
      session_id: 'demo_001',
      agent_name: 'supervisor',
      decision: { action: 'route_intent', intent: 'account_open', confidence: 0.92 },
      timestamp: Date.now() / 1000 - 300,
      timestamp_iso: new Date().toISOString(),
      hash: 'a1b2c3d4-e5f6-a1b2-c3d4-e5f6a1b2c3d4',
      prev_hash: '00000000-0000-0000-0000-000000000000'
    },
    {
      event_type: 'shield_flag',
      session_id: 'demo_001',
      agent_name: 'shield',
      decision: { action: 'pii_scrubbed', patterns: ['aadhaar', 'pan'] },
      timestamp: Date.now() / 1000 - 280,
      timestamp_iso: new Date().toISOString(),
      hash: 'b2c3d4e5-f6a1-b2c3-d4e5-f6a1b2c3d4e5',
      prev_hash: 'a1b2c3d4-e5f6-a1b2-c3d4-e5f6a1b2c3d4'
    },
    {
      event_type: 'hitl_interrupt',
      session_id: 'demo_001',
      agent_name: 'acquisition',
      decision: { action: 'v_kyc_required', reason: 'loan_amount_exceeds_50k' },
      timestamp: Date.now() / 1000 - 100,
      timestamp_iso: new Date().toISOString(),
      hash: 'c3d4e5f6-a1b2-c3d4-e5f6-a1b2c3d4e5f6',
      prev_hash: 'b2c3d4e5-f6a1-b2c3-d4e5-f6a1b2c3d4e5'
    }
  ];
}
