import { useState, useEffect, useCallback } from 'react';
import {
  getMember,
  getMemberSessions,
  getMemberHours,
  forceCheckout,
  editSession,
  type Member,
  type MemberHours,
  type MemberSessionItem,
} from '../api/client';
import { useToast } from '../context/ToastContext';
import Modal from './Modal';

function isoToLocalInput(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  const pad = (n: number) => n.toString().padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function localInputToIso(local: string): string {
  return new Date(local).toISOString();
}

interface MemberDetailProps {
  memberId: string | null;
  onClose: () => void;
  onChanged?: () => void;
}

export default function MemberDetail({ memberId, onClose, onChanged }: MemberDetailProps) {
  const [member, setMember] = useState<Member | null>(null);
  const [hours, setHours] = useState<MemberHours | null>(null);
  const [openSessions, setOpenSessions] = useState<MemberSessionItem[]>([]);
  const [recentSessions, setRecentSessions] = useState<MemberSessionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [checkingOut, setCheckingOut] = useState<string | null>(null);
  const [editing, setEditing] = useState<MemberSessionItem | null>(null);
  const [editForm, setEditForm] = useState({ check_in_at: '', check_out_at: '', status: 'closed', reason: '' });
  const [savingEdit, setSavingEdit] = useState(false);
  const { toast } = useToast();

  const refresh = useCallback(async () => {
    if (!memberId) return;
    setLoading(true);
    try {
      const [m, h, open, recent] = await Promise.all([
        getMember(memberId),
        getMemberHours(memberId).catch(() => null),
        getMemberSessions(memberId, 1, 20, 'open').catch(() => ({ items: [] })),
        getMemberSessions(memberId, 1, 20).catch(() => ({ items: [] })),
      ]);
      setMember(m);
      setHours(h);
      setOpenSessions(open.items);
      setRecentSessions(recent.items);
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

  const openEditModal = (s: MemberSessionItem) => {
    setEditing(s);
    setEditForm({
      check_in_at: isoToLocalInput(s.check_in_at),
      check_out_at: isoToLocalInput(s.check_out_at),
      status: s.status,
      reason: '',
    });
  };

  const handleSaveEdit = async () => {
    if (!editing) return;
    setSavingEdit(true);
    try {
      const payload: Record<string, unknown> = {
        status: editForm.status,
        reason: editForm.reason || undefined,
      };
      if (editForm.check_in_at) payload.check_in_at = localInputToIso(editForm.check_in_at);
      if (editForm.check_out_at) {
        payload.check_out_at = localInputToIso(editForm.check_out_at);
      } else if (editForm.status === 'open') {
        payload.check_out_at = null;
      }
      await editSession(editing.id, payload);
      toast.success('Session updated');
      setEditing(null);
      onChanged?.();
      refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update session');
    } finally {
      setSavingEdit(false);
    }
  };

  const formatDuration = (mins: number | null) => {
    if (mins == null) return 'ongoing';
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return h > 0 ? `${h}h ${m}m` : `${m}m`;
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
              Open Sessions ({openSessions.length})
            </h4>
            {openSessions.length === 0 ? (
              <p className="text-neo-muted text-sm" style={{ padding: '0.75rem 0' }}>
                No open sessions
              </p>
            ) : (
              <div className="space-y-2">
                {openSessions.map((s) => (
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
                        via {s.check_in_method} &middot; {formatDuration(s.duration_minutes)}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => openEditModal(s)}
                        className="neo-btn text-xs py-1 px-3"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleForceCheckout(s.id)}
                        disabled={checkingOut === s.id}
                        className="neo-btn text-xs py-1 px-3"
                        style={{ color: 'var(--neo-danger)', fontWeight: 600 }}
                      >
                        {checkingOut === s.id ? 'Closing...' : 'Force Checkout'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Recent Sessions (editable) */}
          <div>
            <h4 style={{
              fontSize: '0.75rem',
              fontWeight: 700,
              color: 'var(--neo-text-muted)',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              marginBottom: '0.5rem',
            }}>
              Recent Sessions
            </h4>
            {recentSessions.length === 0 ? (
              <p className="text-neo-muted text-sm" style={{ padding: '0.75rem 0' }}>
                No sessions recorded
              </p>
            ) : (
              <div className="space-y-2" style={{ maxHeight: '320px', overflowY: 'auto' }}>
                {recentSessions.map((s) => (
                  <div
                    key={s.id}
                    className="neo-card"
                    style={{
                      padding: '0.625rem 0.875rem',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: '0.5rem',
                    }}
                  >
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div className="text-xs text-neo-dark" style={{ fontWeight: 500 }}>
                        {new Date(s.check_in_at).toLocaleString()}
                        {s.check_out_at && (
                          <> &rarr; {new Date(s.check_out_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</>
                        )}
                      </div>
                      <div className="text-xs text-neo-muted">
                        <span className={`neo-badge-soft ${
                          s.status === 'flagged' ? 'neo-badge-warning' :
                          s.status === 'denied' ? 'neo-badge-danger' :
                          s.status === 'approved' || s.status === 'closed' ? 'neo-badge-success' : ''
                        }`} style={{ marginRight: '0.375rem' }}>{s.status}</span>
                        {formatDuration(s.duration_minutes)}
                      </div>
                    </div>
                    <button
                      onClick={() => openEditModal(s)}
                      className="neo-btn text-xs py-1 px-3"
                    >
                      Edit
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

      {/* Edit Session Modal */}
      {editing && (
        <Modal open={!!editing} onClose={() => setEditing(null)} title="Edit Session">
          <div className="space-y-3">
            <div>
              <label className="neo-label">Check-in time</label>
              <input
                type="datetime-local"
                value={editForm.check_in_at}
                onChange={(e) => setEditForm((f) => ({ ...f, check_in_at: e.target.value }))}
                className="neo-input"
              />
            </div>
            <div>
              <label className="neo-label">Check-out time</label>
              <input
                type="datetime-local"
                value={editForm.check_out_at}
                onChange={(e) => setEditForm((f) => ({ ...f, check_out_at: e.target.value }))}
                className="neo-input"
              />
              <p className="text-xs text-neo-muted mt-1">Leave blank and set status to "open" to reopen the session.</p>
            </div>
            <div>
              <label className="neo-label">Status</label>
              <select
                value={editForm.status}
                onChange={(e) => setEditForm((f) => ({ ...f, status: e.target.value }))}
                className="neo-select"
              >
                <option value="open">Open</option>
                <option value="closed">Closed</option>
                <option value="flagged">Flagged</option>
                <option value="approved">Approved</option>
                <option value="denied">Denied</option>
              </select>
            </div>
            <div>
              <label className="neo-label">Reason (audit log)</label>
              <input
                type="text"
                value={editForm.reason}
                onChange={(e) => setEditForm((f) => ({ ...f, reason: e.target.value }))}
                placeholder="e.g. Corrected checkout time per member request"
                className="neo-input"
              />
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <button onClick={() => setEditing(null)} className="neo-btn text-neo-muted">Cancel</button>
              <button
                onClick={handleSaveEdit}
                disabled={savingEdit}
                className="neo-btn neo-btn-fill-secondary disabled:opacity-50"
              >
                {savingEdit ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </Modal>
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
