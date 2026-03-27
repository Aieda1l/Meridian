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

  if (loading) return <div className="p-6 text-gray-400">Loading...</div>;

  return (
    <div className="p-6 space-y-4">
      <h2 className="text-2xl font-bold text-navy">Approvals</h2>

      {sessions.length === 0 ? (
        <div className="bg-white rounded-xl p-12 shadow-sm text-center">
          <p className="text-4xl mb-3">{'\u2705'}</p>
          <p className="text-gray-500">No flagged sessions to review</p>
        </div>
      ) : (
        <div className="space-y-3">
          {sessions.map((s) => (
            <div key={s.id} className="bg-white rounded-xl p-5 shadow-sm">
              <div className="flex items-start justify-between">
                <div>
                  <p className="font-semibold text-navy">{s.member_name ?? s.member_number}</p>
                  <p className="text-sm text-gray-500 mt-0.5">
                    {new Date(s.check_in_at).toLocaleDateString()}{' '}
                    {new Date(s.check_in_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    {' \u2192 '}
                    {s.check_out_at
                      ? new Date(s.check_out_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                      : 'no checkout'}
                  </p>
                  {s.duration_minutes != null && (
                    <p className="text-sm text-gray-500">
                      Duration: {Math.floor(s.duration_minutes / 60)}h {s.duration_minutes % 60}m
                    </p>
                  )}
                </div>

                <span className="px-3 py-1 text-xs font-semibold bg-yellow-100 text-yellow-800 rounded-full">
                  {s.flag_reason ?? 'flagged'}
                </span>
              </div>

              <div className="flex gap-2 mt-4">
                <button
                  onClick={() => handleApprove(s.id)}
                  className="px-4 py-2 bg-success text-white rounded-lg text-sm font-medium hover:bg-opacity-90 transition"
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
