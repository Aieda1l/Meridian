import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
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

const STATUS_BADGE: Record<string, string> = {
  open: 'neo-badge-success',
  closed: 'neo-badge-soft',
  flagged: 'neo-badge-warning',
  approved: 'neo-badge-info',
  denied: 'neo-badge-danger',
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
  const { toast } = useToast();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const PAGE_SIZE = 20;

  const fetchSessions = useCallback(async () => {
    if (!user) return;
    try {
      const data = await apiFetch<SessionPage>(
        `/members/${user.id}/sessions?page=${page}&page_size=${PAGE_SIZE}`,
      );
      setSessions(data.items);
      setTotal(data.total);
    } catch {
      toast.error('Failed to load session history');
    }
  }, [user, page]);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="p-4 space-y-3">
      <h2 className="text-xl font-bold text-neo-dark">History</h2>

      {sessions.length === 0 ? (
        <p className="text-neo-muted text-center py-8">No sessions yet</p>
      ) : (
        <div className="space-y-2">
          {sessions.map((s) => (
            <div key={s.id} className="neo-card-sm">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-neo-dark">
                    {new Date(s.check_in_at).toLocaleDateString()}
                  </p>
                  <p className="text-sm text-neo-muted">
                    {METHOD_ICONS[s.check_in_method] ?? ''}{' '}
                    {new Date(s.check_in_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    {' \u2192 '}
                    {s.check_out_at
                      ? new Date(s.check_out_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                      : 'open'}
                  </p>
                </div>

                <div className="text-right">
                  <span className={`neo-badge ${STATUS_BADGE[s.status] ?? 'neo-badge-soft'}`}>
                    {s.status}
                  </span>
                  {s.duration_minutes != null && (
                    <p className="text-sm text-neo-muted mt-1">
                      {Math.floor(s.duration_minutes / 60)}h {s.duration_minutes % 60}m
                    </p>
                  )}
                </div>
              </div>

              {s.flag_reason && (
                <p className="mt-2 text-xs neo-badge-warning rounded-neo-sm px-3 py-1">
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
            className="neo-btn px-3 py-1 text-sm"
          >
            Prev
          </button>
          <span className="px-3 py-1 text-sm text-neo-muted">
            {page} / {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="neo-btn px-3 py-1 text-sm"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
