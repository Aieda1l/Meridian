import { useState, useEffect } from 'react';
import { getSeasons, getExport, type Season } from '../api/client';

export default function Reports() {
  const [seasons, setSeasons] = useState<Season[]>([]);
  const [seasonId, setSeasonId] = useState('');
  const [format, setFormat] = useState<'csv' | 'pdf'>('csv');
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    getSeasons().then((s) => {
      setSeasons(s);
      const active = s.find((x) => x.is_active);
      if (active) setSeasonId(active.id);
    }).catch(() => {});
  }, []);

  const handleExport = async () => {
    if (!seasonId) return;
    setExporting(true);
    try {
      await getExport(seasonId, format);
    } catch {
      /* empty */
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      <h2 className="text-2xl font-bold text-navy">Reports</h2>

      <div className="bg-white rounded-xl p-6 shadow-sm space-y-4 max-w-md">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Season</label>
          <select
            value={seasonId}
            onChange={(e) => setSeasonId(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg outline-none"
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
          <label className="block text-sm font-medium text-gray-700 mb-1">Format</label>
          <div className="flex gap-3">
            {(['csv', 'pdf'] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFormat(f)}
                className={`flex-1 py-2 rounded-lg text-sm font-medium border transition ${
                  format === f
                    ? 'bg-navy text-white border-navy'
                    : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'
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
          className="w-full py-2.5 bg-accent text-white rounded-lg font-medium text-sm disabled:opacity-50 hover:bg-opacity-90 transition"
        >
          {exporting ? 'Generating...' : 'Download Report'}
        </button>
      </div>
    </div>
  );
}
