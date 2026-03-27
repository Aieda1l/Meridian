import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { apiFetch } from '../api/client';

interface Session {
  id: string;
  check_in_at: string;
  check_out_at: string | null;
  duration_minutes: number | null;
  check_in_method: string;
  status: string;
  flag_reason: string | null;
}

interface SessionPage {
  items: Session[];
  total: number;
  page: number;
  page_size: number;
}

const STATUS_COLORS: Record<string, string> = {
  open: 'bg-success text-white',
  closed: 'bg-gray-200 text-gray-700',
  flagged: 'bg-yellow-400 text-yellow-900',
  approved: 'bg-accent text-white',
};

const METHOD_ICONS: Record<string, string> = {
  nfc: '\u{1F4F3}',
  qr: '\u{1F4F7}',
  self_report: '\u{270D}\uFE0F',
  auto_timeout: '\u23F0',
  geofence: '\u{1F4CD}',
};

export default function History() {
  const { user } = useAuth();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const PAGE_SIZE = 20;

  const fetchSessions = useCallback(async () => {
    if (!user) return;
    const data = await apiFetch<SessionPage>(
      `/members/${user.id}/sessions?page=${page}&page_size=${PAGE_SIZE}`,
    );
    setSessions(data.items);
    setTotal(data.total);
  }, [user, page]);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="p-4 space-y-3">
      <h2 className="text-xl font-bold text-navy">History</h2>

      {sessions.length === 0 ? (
        <p className="text-gray-400 text-center py-8">No sessions yet</p>
      ) : (
        <div className="space-y-2">
          {sessions.map((s) => (
            <div key={s.id} className="bg-white rounded-xl p-4 shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-navy">
                    {new Date(s.check_in_at).toLocaleDateString()}
                  </p>
                  <p className="text-sm text-gray-500">
                    {METHOD_ICONS[s.check_in_method] ?? ''}{' '}
                    {new Date(s.check_in_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    {' \u2192 '}
                    {s.check_out_at
                      ? new Date(s.check_out_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                      : 'open'}
                  </p>
                </div>

                <div className="text-right">
                  <span className={`inline-block px-2 py-0.5 text-xs font-semibold rounded-full ${STATUS_COLORS[s.status] ?? 'bg-gray-100'}`}>
                    {s.status}
                  </span>
                  {s.duration_minutes != null && (
                    <p className="text-sm text-gray-600 mt-1">
                      {Math.floor(s.duration_minutes / 60)}h {s.duration_minutes % 60}m
                    </p>
                  )}
                </div>
              </div>

              {s.flag_reason && (
                <p className="mt-2 text-xs text-yellow-700 bg-yellow-50 rounded-lg px-3 py-1">
                  {s.flag_reason}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center gap-2 pt-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-3 py-1 bg-white rounded-lg shadow-sm text-sm disabled:opacity-30"
          >
            Prev
          </button>
          <span className="px-3 py-1 text-sm text-gray-500">
            {page} / {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="px-3 py-1 bg-white rounded-lg shadow-sm text-sm disabled:opacity-30"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
