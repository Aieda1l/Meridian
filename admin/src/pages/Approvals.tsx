import { useState, useEffect, useCallback } from 'react';
import { getSessions, approveSession, type SessionItem } from '../api/client';

export default function Approvals() {
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getSessions('status=flagged&page_size=100');
      setSessions(data.items);
    } catch {
      /* empty */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const handleApprove = async (id: string) => {
    try {
      await approveSession(id);
      setSessions((prev) => prev.filter((s) => s.id !== id));
    } catch {
      /* empty */
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
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
