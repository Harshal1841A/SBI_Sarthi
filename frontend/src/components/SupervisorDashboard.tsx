import { useState, useEffect, useCallback } from 'react';
import { supervisorApi } from '../services/api';
import { HITLThread, HITLDecision } from '../types';
import { 
  CheckCircle, XCircle, Clock, 
  User, MessageSquare, RefreshCw, Loader2
} from 'lucide-react';

export default function SupervisorDashboard() {
  const [threads, setThreads] = useState<HITLThread[]>([]);
  const [loading, setLoading] = useState(false);
  const [approving, setApproving] = useState<string | null>(null);
  const [approverId, setApproverId] = useState('officer_001');
  const [rejectionReason, setRejectionReason] = useState('');
  const [showRejectModal, setShowRejectModal] = useState<string | null>(null);
  const [stats, setStats] = useState({ total: 0, approved: 0, rejected: 0, pending: 0 });

  const fetchPending = useCallback(async () => {
    setLoading(true);
    try {
      const data = await supervisorApi.getPendingThreads();
      setThreads(data);
      // FIX M-7: total must only GROW — never reset to current pending count.
      // On first load, seed total from the number of pending items so the counter
      // starts at a sensible non-zero value. After that, only approved/rejected
      // handlers increment it so it acts as a cumulative "processed today" metric.
      setStats(prev => ({
        ...prev,
        pending: data.length,
        // Only set total on first load (when it's still 0)
        total: prev.total === 0 ? data.length : prev.total
      }));
    } catch (err) {
      console.error('Failed to fetch pending threads:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPending();
    const interval = setInterval(fetchPending, 5000); // Poll every 5 seconds
    return () => clearInterval(interval);
  }, [fetchPending]);

  const handleApprove = async (threadId: string) => {
    setApproving(threadId);
    try {
      const decision: HITLDecision = {
        approved: true,
        approver_id: approverId
      };
      await supervisorApi.approveThread(threadId, decision);
      setStats(prev => ({ ...prev, approved: prev.approved + 1, total: prev.total + 1, pending: Math.max(0, prev.pending - 1) }));
      await fetchPending();
    } catch (err: any) {
      console.error('Approval failed:', err);
      if (err?.response?.status === 403 || sessionStorage.getItem('sarthi_demo_active') === 'true') {
        alert('Approval requires SBI officer credentials (Demo read-only mode)');
      }
    } finally {
      setApproving(null);
    }
  };

  const handleReject = async (threadId: string) => {
    setApproving(threadId);
    try {
      const decision: HITLDecision = {
        approved: false,
        reason: rejectionReason || 'Rejected by supervisor',
        approver_id: approverId
      };
      await supervisorApi.approveThread(threadId, decision);
      setStats(prev => ({ ...prev, rejected: prev.rejected + 1, total: prev.total + 1, pending: Math.max(0, prev.pending - 1) }));
      setShowRejectModal(null);
      setRejectionReason('');
      await fetchPending();
    } catch (err: any) {
      console.error('Rejection failed:', err);
      if (err?.response?.status === 403 || sessionStorage.getItem('sarthi_demo_active') === 'true') {
        alert('Approval requires SBI officer credentials (Demo read-only mode)');
      }
    } finally {
      setApproving(null);
    }
  };

  const getRiskColor = (score: number) => {
    if (score >= 0.7) return 'bg-red-100 text-red-700 border-red-200';
    if (score >= 0.4) return 'bg-amber-100 text-amber-700 border-amber-200';
    return 'bg-green-100 text-green-700 border-green-200';
  };


  return (
    <div className="bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden">
      {/* Header */}
      <div className="bg-[#00447C] text-white px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold">Supervisor Dashboard</h2>
            <p className="text-sm text-blue-200">Human-in-the-Loop Approval Queue</p>
          </div>
          <button
            onClick={fetchPending}
            disabled={loading}
            className="p-2 rounded-lg bg-white/20 hover:bg-white/30 transition disabled:opacity-50"
          >
            <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4 p-4 border-b border-gray-200">
        <div className="text-center">
          <p className="text-2xl font-bold text-[#00447C]">{stats.total}</p>
          <p className="text-xs text-gray-500">Total Today</p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-bold text-green-600">{stats.approved}</p>
          <p className="text-xs text-gray-500">Approved</p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-bold text-red-600">{stats.rejected}</p>
          <p className="text-xs text-gray-500">Rejected</p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-bold text-amber-600">{stats.pending}</p>
          <p className="text-xs text-gray-500">Pending</p>
        </div>
      </div>

      {/* Officer ID */}
      <div className="px-4 py-2 border-b border-gray-200 bg-gray-50">
        <label className="text-xs text-gray-500">Officer ID:</label>
        <input
          type="text"
          value={approverId}
          onChange={(e) => setApproverId(e.target.value)}
          className="ml-2 text-sm px-2 py-1 rounded border border-gray-300 focus:outline-none focus:ring-1 focus:ring-[#00447C]"
        />
      </div>

      {/* Threads List */}
      <div className="max-h-[500px] overflow-y-auto">
        {threads.length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            <CheckCircle className="w-12 h-12 mx-auto mb-2 opacity-50" />
            <p>No pending approvals</p>
            <p className="text-sm">All caught up!</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {threads.map((thread) => (
              <div key={thread.thread_id} className="p-4 hover:bg-gray-50 transition">
                {/* Thread Header */}
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <User className="w-4 h-4 text-gray-400" />
                    <span className="text-sm font-medium text-gray-700 break-all">
                      {thread.user_id || thread.thread_id.slice(0, 12)}
                    </span>
                    <span className={`text-xs px-2 py-0.5 rounded-full border whitespace-nowrap ${getRiskColor(thread.risk_score || 0)}`}>
                      Risk: {((thread.risk_score || 0) * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div className="flex items-center gap-1 text-xs text-gray-400">
                    <Clock className="w-3 h-3" />
                    {thread.timestamp ? new Date(thread.timestamp).toLocaleTimeString() : 'Now'}
                  </div>
                </div>

                {/* Context */}
                <div className="bg-gray-50 rounded-lg p-2 mb-2">
                  <div className="flex items-center gap-1 text-xs text-gray-500 mb-1">
                    <MessageSquare className="w-3 h-3" />
                    <span>Context:</span>
                  </div>
                  <p className="text-sm text-gray-700 break-words">
                    Intent: <strong>{thread.intent}</strong> | 
                    Channel: {thread.channel} | 
                    Language: {thread.language}
                  </p>
                  {thread.interrupt_reason && (
                    <p className="text-xs text-amber-600 mt-1 break-words">
                      Reason: {thread.interrupt_reason}
                    </p>
                  )}
                  {thread.onboarding_step && (
                    <p className="text-xs text-gray-500 mt-1 break-words">
                      Step: {thread.onboarding_step}
                    </p>
                  )}
                </div>

                {/* Messages Preview */}
                {thread.customer_context && thread.customer_context.length > 0 && (
                  <div className="text-xs text-gray-500 mb-3 space-y-1">
                    {thread.customer_context.slice(-2).map((ctx: any, i: number) => (
                      <div key={i} className="line-clamp-2 break-words">
                        <span className="font-medium">{ctx.role}:</span> {ctx.content}
                      </div>
                    ))}
                  </div>
                )}

                {/* Actions */}
                <div className="flex gap-2">
                  <button
                    onClick={() => handleApprove(thread.thread_id)}
                    disabled={approving === thread.thread_id}
                    className="flex-1 flex items-center justify-center gap-1 bg-green-600 hover:bg-green-700 text-white text-sm py-2 rounded-lg transition disabled:opacity-50"
                  >
                    {approving === thread.thread_id ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <CheckCircle className="w-4 h-4" />
                    )}
                    Approve
                  </button>
                  <button
                    onClick={() => setShowRejectModal(thread.thread_id)}
                    disabled={approving === thread.thread_id}
                    className="flex-1 flex items-center justify-center gap-1 bg-red-600 hover:bg-red-700 text-white text-sm py-2 rounded-lg transition disabled:opacity-50"
                  >
                    <XCircle className="w-4 h-4" />
                    Reject
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Reject Modal */}
      {showRejectModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-96 shadow-2xl">
            <h3 className="text-lg font-semibold mb-3">Rejection Reason</h3>
            <textarea
              value={rejectionReason}
              onChange={(e) => setRejectionReason(e.target.value)}
              placeholder="Enter reason for rejection..."
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#00447C] mb-4"
              rows={3}
            />
            <div className="flex gap-2">
              <button
                onClick={() => setShowRejectModal(null)}
                className="flex-1 py-2 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 transition"
              >
                Cancel
              </button>
              <button
                onClick={() => handleReject(showRejectModal)}
                className="flex-1 py-2 rounded-lg bg-red-600 text-white hover:bg-red-700 transition"
              >
                Confirm Reject
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
