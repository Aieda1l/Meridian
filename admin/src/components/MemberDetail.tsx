import { useState, useEffect, useCallback } from 'react';
import {
  getMember,
  getMemberSessions,
  getMemberHours,
  forceCheckout,
  type Member,
  type MemberHours,
  type MemberSessionItem,
} from '../api/client';
import { useToast } from '../context/ToastContext';
import Modal from './Modal';

interface MemberDetailProps {
  memberId: string | null;
  onClose: () => void;
  onChanged?: () => void;
}

export default function MemberDetail({ memberId, onClose, onChanged }: MemberDetailProps) {
  const [member, setMember] = useState<Member | null>(null);
  const [hours, setHours] = useState<MemberHours | null>(null);
  const [sessions, setSessions] = useState<MemberSessionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [checkingOut, setCheckingOut] = useState<string | null>(null);
  const { toast } = useToast();

  const refresh = useCallback(async () => {
    if (!memberId) return;
    setLoading(true);
    try {
      const [m, h, s] = await Promise.all([
        getMember(memberId),
        getMemberHours(memberId).catch(() => null),
        getMemberSessions(memberId, 1, 20, 'open').catch(() => ({ items: [] })),
      ]);
      setMember(m);
      setHours(h);
      setSessions(s.items);
    } catch {
      toast.error('Failed to load member details');
    } finally {
      setLoading(false);
    }
  }, [memberId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleForceCheckout = async (sessionId: string) => {
    setCheckingOut(sessionId);
    try {
      await forceCheckout(sessionId);
      toast.success('Session closed successfully');
      onChanged?.();
      refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to close session');
    } finally {
      setCheckingOut(null);
    }
  };

  if (!memberId) return null;

  return (
    <Modal open={!!memberId} onClose={onClose} title={loading ? 'Loading...' : (member?.name || 'Member Detail')}>
      {loading ? (
        <div className="py-8 text-center text-neo-muted">Loading...</div>
      ) : member ? (
        <div className="space-y-5">
          {/* Info Grid */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(2, 1fr)',
            gap: '0.75rem',
          }}>
            <InfoItem label="Member #" value={member.member_number} />
            <InfoItem label="Role" value={
              <span className={`neo-badge-soft ${
                member.role === 'admin' ? 'neo-badge-danger' : member.role === 'mentor' ? 'neo-badge-warning' : ''
              }`}>{member.role}</span>
            } />
            <InfoItem label="Email" value={member.email} />
            <InfoItem label="Phone" value={member.phone || '—'} />
            <InfoItem label="Status" value={
              <span className={member.is_active ? 'neo-badge-success' : 'neo-badge-soft'}>
                {member.is_active ? 'Active' : 'Inactive'}
              </span>
            } />
            <InfoItem label="Joined" value={new Date(member.created_at).toLocaleDateString()} />
          </div>

          {/* Hours Summary */}
          {hours && (
            <div>
              <h4 style={{
                fontSize: '0.75rem',
                fontWeight: 700,
                color: 'var(--neo-text-muted)',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                marginBottom: '0.5rem',
              }}>
                Hours
              </h4>
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(3, 1fr)',
                gap: '0.5rem',
              }}>
                <HourCard label="Today" value={hours.hours_today} cap={hours.daily_cap} />
                <HourCard label="This Week" value={hours.hours_this_week} cap={hours.weekly_cap} />
                <HourCard label="Season" value={hours.hours_this_season} cap={hours.season_cap} />
              </div>
            </div>
          )}

          {/* Open Sessions */}
          <div>
            <h4 style={{
              fontSize: '0.75rem',
              fontWeight: 700,
              color: 'var(--neo-text-muted)',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              marginBottom: '0.5rem',
            }}>
              Open Sessions ({sessions.length})
            </h4>
            {sessions.length === 0 ? (
              <p className="text-neo-muted text-sm" style={{ padding: '0.75rem 0' }}>
                No open sessions
              </p>
            ) : (
              <div className="space-y-2">
                {sessions.map((s) => (
                  <div
                    key={s.id}
                    className="neo-card"
                    style={{
                      padding: '0.75rem 1rem',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}
                  >
                    <div>
                      <div className="text-sm font-medium text-neo-dark">
                        Checked in {new Date(s.check_in_at).toLocaleString()}
                      </div>
                      <div className="text-xs text-neo-muted">
                        via {s.check_in_method} &middot; {s.duration_minutes != null ? `${s.duration_minutes} min` : 'ongoing'}
                      </div>
                    </div>
                    <button
                      onClick={() => handleForceCheckout(s.id)}
                      disabled={checkingOut === s.id}
                      className="neo-btn text-xs py-1 px-3"
                      style={{ color: 'var(--neo-danger)', fontWeight: 600 }}
                    >
                      {checkingOut === s.id ? 'Closing...' : 'Force Checkout'}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="py-8 text-center text-neo-muted">Member not found</div>
      )}
    </Modal>
  );
}

function InfoItem({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <div style={{
        fontSize: '0.6875rem',
        fontWeight: 600,
        color: 'var(--neo-text-muted)',
        textTransform: 'uppercase',
        letterSpacing: '0.04em',
        marginBottom: '0.125rem',
      }}>
        {label}
      </div>
      <div style={{ fontSize: '0.875rem', color: 'var(--neo-text)' }}>
        {value}
      </div>
    </div>
  );
}

function HourCard({ label, value, cap }: { label: string; value: number; cap: number }) {
  const pct = cap > 0 ? Math.min((value / cap) * 100, 100) : 0;
  const overCap = value >= cap && cap > 0;

  return (
    <div className="neo-card" style={{ padding: '0.625rem 0.75rem', textAlign: 'center' }}>
      <div style={{
        fontSize: '1.25rem',
        fontWeight: 700,
        color: overCap ? 'var(--neo-danger)' : 'var(--neo-text)',
      }}>
        {value.toFixed(1)}
      </div>
      <div style={{
        fontSize: '0.6875rem',
        color: 'var(--neo-text-muted)',
        marginBottom: '0.375rem',
      }}>
        {label} / {cap}h
      </div>
      <div style={{
        height: '4px',
        borderRadius: '2px',
        backgroundColor: 'var(--neo-border-light)',
        overflow: 'hidden',
      }}>
        <div style={{
          height: '100%',
          width: `${pct}%`,
          borderRadius: '2px',
          backgroundColor: overCap ? 'var(--neo-danger)' : 'var(--neo-secondary)',
          transition: 'width 0.3s ease',
        }} />
      </div>
    </div>
  );
}
