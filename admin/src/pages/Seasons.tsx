import { useState, useEffect, useCallback } from 'react';
import { getSeasons, updateSeason, createSeason, type Season, type CreateSeasonData } from '../api/client';
import { useToast } from '../context/ToastContext';
import Modal from '../components/Modal';

interface EditFormState {
  name: string;
  start_date: string;
  end_date: string;
  daily_hour_cap: string;
  weekly_hour_cap: string;
  season_hour_cap: string;
}

const emptyForm: EditFormState = {
  name: '',
  start_date: '',
  end_date: '',
  daily_hour_cap: '',
  weekly_hour_cap: '',
  season_hour_cap: '',
};

function seasonToForm(s: Season): EditFormState {
  return {
    name: s.name,
    start_date: s.start_date.split('T')[0],
    end_date: s.end_date.split('T')[0],
    daily_hour_cap: s.daily_hour_cap.toString(),
    weekly_hour_cap: s.weekly_hour_cap.toString(),
    season_hour_cap: s.season_hour_cap.toString(),
  };
}

export default function Seasons() {
  const [seasons, setSeasons] = useState<Season[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<Season | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<EditFormState>(emptyForm);
  const [saving, setSaving] = useState(false);
  const { toast } = useToast();

  const refresh = useCallback(() => {
    setLoading(true);
    getSeasons()
      .then(setSeasons)
      .catch(() => toast.error('Failed to load seasons'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const openEdit = (s: Season) => {
    setEditing(s);
    setCreating(false);
    setForm(seasonToForm(s));
  };

  const openCreate = () => {
    setEditing(null);
    setCreating(true);
    setForm({
      ...emptyForm,
      daily_hour_cap: '12',
      weekly_hour_cap: '40',
      season_hour_cap: '400',
    });
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const caps = {
        daily_hour_cap: parseFloat(form.daily_hour_cap),
        weekly_hour_cap: parseFloat(form.weekly_hour_cap),
        season_hour_cap: parseFloat(form.season_hour_cap),
      };

      if (Object.values(caps).some((v) => Number.isNaN(v) || v < 0)) {
        toast.error('Hour caps must be non-negative numbers');
        setSaving(false);
        return;
      }

      if (creating) {
        const payload: CreateSeasonData = {
          name: form.name,
          start_date: form.start_date,
          end_date: form.end_date,
          ...caps,
        };
        await createSeason(payload);
        toast.success('Season created');
      } else if (editing) {
        await updateSeason(editing.id, {
          name: form.name,
          start_date: form.start_date,
          end_date: form.end_date,
          ...caps,
        });
        toast.success('Season updated');
      }

      setEditing(null);
      setCreating(false);
      refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save season');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-neo-dark">Seasons &amp; Hour Caps</h2>
        <button onClick={openCreate} className="neo-btn neo-btn-fill-secondary">
          + New Season
        </button>
      </div>

      {loading ? (
        <div className="neo-card text-center py-8 text-neo-muted">Loading...</div>
      ) : seasons.length === 0 ? (
        <div className="neo-card text-center py-8 text-neo-muted">No seasons yet.</div>
      ) : (
        <div className="space-y-3">
          {seasons.map((s) => (
            <div key={s.id} className="neo-card">
              <div className="flex items-start justify-between gap-4 mb-3">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-lg font-bold text-neo-dark">{s.name}</h3>
                    {s.is_active && (
                      <span className="neo-badge-success text-xs">Active</span>
                    )}
                  </div>
                  <p className="text-sm text-neo-muted">
                    {new Date(s.start_date).toLocaleDateString()} – {new Date(s.end_date).toLocaleDateString()}
                  </p>
                </div>
                <button onClick={() => openEdit(s)} className="neo-btn text-sm">
                  Edit
                </button>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <CapCard label="Daily" value={s.daily_hour_cap} />
                <CapCard label="Weekly" value={s.weekly_hour_cap} />
                <CapCard label="Season" value={s.season_hour_cap} />
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal
        open={!!editing || creating}
        onClose={() => { setEditing(null); setCreating(false); }}
        title={creating ? 'New Season' : `Edit ${editing?.name ?? 'Season'}`}
      >
        <div className="space-y-3">
          <div>
            <label className="neo-label">Name</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              className="neo-input"
              placeholder="2026 Build Season"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="neo-label">Start date</label>
              <input
                type="date"
                value={form.start_date}
                onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value }))}
                className="neo-input"
              />
            </div>
            <div>
              <label className="neo-label">End date</label>
              <input
                type="date"
                value={form.end_date}
                onChange={(e) => setForm((f) => ({ ...f, end_date: e.target.value }))}
                className="neo-input"
              />
            </div>
          </div>
          <div className="pt-2">
            <div className="text-xs font-bold text-neo-muted uppercase tracking-wider mb-2">
              Hour Caps
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="neo-label">Daily (h)</label>
                <input
                  type="number"
                  min="0"
                  step="0.5"
                  value={form.daily_hour_cap}
                  onChange={(e) => setForm((f) => ({ ...f, daily_hour_cap: e.target.value }))}
                  className="neo-input"
                />
              </div>
              <div>
                <label className="neo-label">Weekly (h)</label>
                <input
                  type="number"
                  min="0"
                  step="0.5"
                  value={form.weekly_hour_cap}
                  onChange={(e) => setForm((f) => ({ ...f, weekly_hour_cap: e.target.value }))}
                  className="neo-input"
                />
              </div>
              <div>
                <label className="neo-label">Season (h)</label>
                <input
                  type="number"
                  min="0"
                  step="1"
                  value={form.season_hour_cap}
                  onChange={(e) => setForm((f) => ({ ...f, season_hour_cap: e.target.value }))}
                  className="neo-input"
                />
              </div>
            </div>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button
              onClick={() => { setEditing(null); setCreating(false); }}
              className="neo-btn text-neo-muted"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="neo-btn neo-btn-fill-secondary disabled:opacity-50"
            >
              {saving ? 'Saving...' : creating ? 'Create Season' : 'Save Changes'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

function CapCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="neo-card-sm text-center">
      <div className="text-xs text-neo-muted uppercase tracking-wider">{label}</div>
      <div className="text-xl font-bold text-neo-dark">{value}h</div>
    </div>
  );
}
