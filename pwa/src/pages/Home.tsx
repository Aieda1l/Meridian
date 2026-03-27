import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { useGeofence } from '../hooks/useGeofence';
import { apiFetch } from '../api/client';

interface Session {
  id: string;
  check_in_at: string;
  status: string;
}

export default function Home() {
  const { user } = useAuth();
  const [openSession, setOpenSession] = useState<Session | null>(null);
  const [elapsed, setElapsed] = useState('0:00');
  const [showSelfReport, setShowSelfReport] = useState(false);
  const [reportTime, setReportTime] = useState('');
  const [reportError, setReportError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useGeofence(!!openSession, user?.id ?? '');

  const fetchOpenSession = useCallback(async () => {
    if (!user) return;
    try {
      const data = await apiFetch<{ items: Session[] }>(
        `/members/${user.id}/sessions?status=open&page_size=1`,
      );
      setOpenSession(data.items.length > 0 ? data.items[0] : null);
    } catch {
      setOpenSession(null);
    }
  }, [user]);

  useEffect(() => {
    fetchOpenSession();
    const id = setInterval(fetchOpenSession, 30_000);
    return () => clearInterval(id);
  }, [fetchOpenSession]);

  // Live elapsed timer
  useEffect(() => {
    if (!openSession) {
      setElapsed('0:00');
      return;
    }
    const tick = () => {
      const start = new Date(openSession.check_in_at).getTime();
      const diff = Math.floor((Date.now() - start) / 1000);
      const h = Math.floor(diff / 3600);
      const m = Math.floor((diff % 3600) / 60);
      setElapsed(`${h}:${m.toString().padStart(2, '0')}`);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [openSession]);

  const handleSelfReport = async () => {
    if (!openSession || !reportTime) return;
    setReportError('');
    setSubmitting(true);
    try {
      await apiFetch(`/sessions/${openSession.id}/self-report`, {
        method: 'PATCH',
        body: JSON.stringify({ checkout_at: new Date(reportTime).toISOString() }),
      });
      setShowSelfReport(false);
      setReportTime('');
      await fetchOpenSession();
    } catch (err) {
      setReportError(err instanceof Error ? err.message : 'Failed to submit');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="p-4 space-y-4">
      <h2 className="text-xl font-bold text-navy">Home</h2>

      {/* Status Card */}
      <div className={`rounded-2xl p-6 shadow-md ${openSession ? 'bg-success/10 border border-success/30' : 'bg-white'}`}>
        <div className="text-center">
          <div className={`inline-block px-4 py-1 rounded-full text-sm font-semibold mb-3 ${openSession ? 'bg-success text-white' : 'bg-gray-200 text-gray-600'}`}>
            {openSession ? 'Checked In' : 'Not Checked In'}
          </div>

          {openSession ? (
            <>
              <p className="text-4xl font-bold text-navy">{elapsed}</p>
              <p className="text-gray-500 mt-1">
                since {new Date(openSession.check_in_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </p>
            </>
          ) : (
            <p className="text-gray-500">Scan your pass at a scanner to check in</p>
          )}
        </div>
      </div>

      {/* Self-report button */}
      {openSession && (
        <button
          onClick={() => setShowSelfReport(true)}
          className="w-full py-3 bg-white border border-gray-200 rounded-xl text-navy font-medium shadow-sm hover:bg-gray-50 transition"
        >
          Self-Report Checkout
        </button>
      )}

      {/* Self-report modal */}
      {showSelfReport && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl p-6 w-full max-w-sm space-y-4">
            <h3 className="text-lg font-bold text-navy">Self-Report Checkout</h3>
            <p className="text-sm text-gray-500">
              Enter the time you left. This will be flagged for admin review.
            </p>

            {reportError && (
              <div className="bg-red-50 text-danger text-sm p-3 rounded-lg">{reportError}</div>
            )}

            <input
              type="datetime-local"
              value={reportTime}
              onChange={(e) => setReportTime(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-accent"
            />

            <div className="flex gap-3">
              <button
                onClick={() => setShowSelfReport(false)}
                className="flex-1 py-2 border border-gray-300 rounded-lg text-gray-600 font-medium"
              >
                Cancel
              </button>
              <button
                onClick={handleSelfReport}
                disabled={submitting || !reportTime}
                className="flex-1 py-2 bg-navy text-white rounded-lg font-medium disabled:opacity-50"
              >
                {submitting ? 'Submitting...' : 'Submit'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
