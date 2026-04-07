import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { useGeofence } from '../hooks/useGeofence';
import { apiFetch } from '../api/client';

interface Session {
  id: string;
  check_in_at: string;
  scanner_id: string | null;
  status: string;
}

export default function Home() {
  const { user } = useAuth();
  const { toast } = useToast();
  const [openSession, setOpenSession] = useState<Session | null>(null);
  const [elapsed, setElapsed] = useState('0:00');
  const [showSelfReport, setShowSelfReport] = useState(false);
  const [reportTime, setReportTime] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const prevSessionRef = useRef<Session | null>(null);

  const fetchOpenSession = useCallback(async () => {
    if (!user) return;
    try {
      const data = await apiFetch<{ items: Session[] }>(
        `/members/${user.id}/sessions?status=open&page_size=1`,
      );
      const current = data.items.length > 0 ? data.items[0] : null;

      // Detect auto-checkout: session went from open to gone
      if (prevSessionRef.current && !current) {
        toast.warning('You were automatically checked out.');
      }
      prevSessionRef.current = current;
      setOpenSession(current);
    } catch {
      setOpenSession(null);
    }
  }, [user, toast]);

  useGeofence({
    isCheckedIn: !!openSession,
    memberId: user?.id ?? '',
    sessionId: openSession?.id,
    scannerId: openSession?.scanner_id,
    onCheckout: fetchOpenSession,
  });

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
    setSubmitting(true);
    try {
      await apiFetch(`/sessions/${openSession.id}/self-report`, {
        method: 'PATCH',
        body: JSON.stringify({ checkout_at: new Date(reportTime).toISOString() }),
      });
      setShowSelfReport(false);
      setReportTime('');
      toast.success('Checkout report submitted for review');
      await fetchOpenSession();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to submit');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="p-4 space-y-4">
      <h2 className="text-xl font-bold text-neo-dark">Home</h2>

      {/* Status Card */}
      <div className={`neo-card ${openSession ? 'border-success/30' : ''}`}>
        <div className="text-center">
          <div className={`inline-block px-4 py-1 rounded-full text-sm font-semibold mb-3 ${openSession ? 'neo-badge-success' : 'neo-badge-soft'}`}>
            {openSession ? 'Checked In' : 'Not Checked In'}
          </div>

          {openSession ? (
            <>
              <p className="text-4xl font-bold text-neo-dark">{elapsed}</p>
              <p className="text-neo-muted mt-1">
                since {new Date(openSession.check_in_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </p>
            </>
          ) : (
            <p className="text-neo-muted">Scan your pass at a scanner to check in</p>
          )}
        </div>
      </div>

      {/* Self-report button */}
      {openSession && (
        <button
          onClick={() => setShowSelfReport(true)}
          className="neo-btn w-full py-3 font-medium"
        >
          Self-Report Checkout
        </button>
      )}

      {/* Self-report modal */}
      {showSelfReport && (
        <div className="neo-modal-overlay p-4">
          <div className="neo-modal space-y-4">
            <h3 className="text-lg font-bold text-neo-dark">Self-Report Checkout</h3>
            <p className="text-sm text-neo-muted">
              Enter the time you left. This will be flagged for admin review.
            </p>

            <input
              type="datetime-local"
              value={reportTime}
              onChange={(e) => setReportTime(e.target.value)}
              className="neo-input"
            />

            <div className="flex gap-3">
              <button
                onClick={() => setShowSelfReport(false)}
                className="neo-btn flex-1 py-2 font-medium"
              >
                Cancel
              </button>
              <button
                onClick={handleSelfReport}
                disabled={submitting || !reportTime}
                className="neo-btn neo-btn-fill-secondary flex-1 py-2 font-medium"
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
