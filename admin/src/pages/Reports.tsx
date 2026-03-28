import { useState, useEffect } from 'react';
import { getSeasons, getExport, type Season } from '../api/client';
import { useToast } from '../context/ToastContext';

export default function Reports() {
  const [seasons, setSeasons] = useState<Season[]>([]);
  const [seasonId, setSeasonId] = useState('');
  const [format, setFormat] = useState<'csv' | 'pdf'>('csv');
  const [exporting, setExporting] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    getSeasons().then((s) => {
      setSeasons(s);
      const active = s.find((x) => x.is_active);
      if (active) setSeasonId(active.id);
    }).catch(() => toast.error('Failed to load seasons'));
  }, []);

  const handleExport = async () => {
    if (!seasonId) return;
    setExporting(true);
    try {
      await getExport(seasonId, format);
      toast.success(`${format.toUpperCase()} report downloaded`);
    } catch {
      toast.error('Export failed. Please try again.');
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      <h2 className="text-2xl font-bold text-neo-dark">Reports</h2>

      <div className="neo-card p-6 space-y-4 max-w-md">
        <div>
          <label className="neo-label">Season</label>
          <select
            value={seasonId}
            onChange={(e) => setSeasonId(e.target.value)}
            className="neo-select"
          >
            <option value="">Select season...</option>
            {seasons.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} {s.is_active ? '(active)' : ''}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="neo-label">Format</label>
          <div className="flex gap-3">
            {(['csv', 'pdf'] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFormat(f)}
                className={`flex-1 py-2 rounded-neo-lg text-sm font-medium transition ${
                  format === f
                    ? 'shadow-neo-inset text-accent font-semibold'
                    : 'neo-btn text-neo-muted'
                }`}
              >
                {f.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        <button
          onClick={handleExport}
          disabled={!seasonId || exporting}
          className="neo-btn neo-btn-fill-secondary w-full disabled:opacity-50"
        >
          {exporting ? 'Generating...' : 'Download Report'}
        </button>
      </div>
    </div>
  );
}
