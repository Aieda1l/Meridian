import { useState, useEffect, useCallback } from 'react';
import { getSessions, approveSession, denySession, type SessionItem } from '../api/client';
import { useToast } from '../context/ToastContext';

export default function Approvals() {
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [denyTarget, setDenyTarget] = useState<string | null>(null);
  const [denyReason, setDenyReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const { toast } = useToast();

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getSessions('status=flagged&page_size=100');
      setSessions(data.items);
    } catch {
      toast.error('Failed to load flagged sessions');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const handleApprove = async (id: string) => {
    try {
      await approveSession(id);
      setSessions((prev) => prev.filter((s) => s.id !== id));
      toast.success('Session approved');
    } catch {
      toast.error('Failed to approve session');
    }
  };

  const handleDeny = async () => {
    if (!denyTarget) return;
    setSubmitting(true);
    try {
      await denySession(denyTarget, denyReason || undefined);
      setSessions((prev) => prev.filter((s) => s.id !== denyTarget));
      toast.success('Session denied');
      setDenyTarget(null);
      setDenyReason('');
    } catch {
      toast.error('Failed to deny session');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <div className="p-6 text-neo-muted">Loading...</div>;

  return (
    <div className="p-6 space-y-4">
      <h2 className="text-2xl font-bold text-neo-dark">Approvals</h2>

      {sessions.length === 0 ? (
        <div className="neo-card p-12 text-center">
          <p className="text-4xl mb-3">{'\u2705'}</p>
          <p className="text-neo-muted">No flagged sessions to review</p>
        </div>
      ) : (
        <div className="space-y-3">
          {sessions.map((s) => (
            <div key={s.id} className="neo-card p-5">
              <div className="flex items-start justify-between">
                <div>
                  <p className="font-semibold text-neo-dark">{s.member_name ?? s.member_number}</p>
                  <p className="text-sm text-neo-muted mt-0.5">
                    {new Date(s.check_in_at).toLocaleDateString()}{' '}
                    {new Date(s.check_in_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    {' \u2192 '}
                    {s.check_out_at
                      ? new Date(s.check_out_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                      : 'no checkout'}
                  </p>
                  {s.duration_minutes != null && (
                    <p className="text-sm text-neo-muted">
                      Duration: {Math.floor(s.duration_minutes / 60)}h {s.duration_minutes % 60}m
                    </p>
                  )}
                </div>

                <span className="neo-badge-warning">
                  {s.flag_reason ?? 'flagged'}
                </span>
              </div>

              <div className="flex gap-2 mt-4">
                <button
                  onClick={() => handleApprove(s.id)}
                  className="neo-btn neo-btn-success"
                >
                  Approve
                </button>
                <button
                  onClick={() => setDenyTarget(s.id)}
                  className="neo-btn neo-btn-danger"
                >
                  Deny
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Deny reason modal */}
      {denyTarget && (
        <div className="neo-modal-overlay">
          <div className="neo-modal space-y-4">
            <h3 className="text-lg font-bold text-neo-dark">Deny Session</h3>
            <p className="text-sm text-neo-muted">
              Optionally provide a reason for denying this session. The student will be notified.
            </p>

            <textarea
              value={denyReason}
              onChange={(e) => setDenyReason(e.target.value)}
              placeholder="Reason (optional)"
              className="neo-input w-full"
              rows={3}
            />

            <div className="flex gap-3">
              <button
                onClick={() => { setDenyTarget(null); setDenyReason(''); }}
                className="neo-btn flex-1"
              >
                Cancel
              </button>
              <button
                onClick={handleDeny}
                disabled={submitting}
                className="neo-btn neo-btn-danger flex-1"
              >
                {submitting ? 'Denying...' : 'Deny Session'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
