import { useState, useEffect } from 'react';
import { getSeasons, getMembers, getExport, type Season, type Member } from '../api/client';
import { useToast } from '../context/ToastContext';

// Column definitions matching backend ALL_COLUMNS keys
const EXPORT_COLUMNS = [
  { key: 'member_number',    label: 'Member Number' },
  { key: 'name',             label: 'Name' },
  { key: 'role',             label: 'Role' },
  { key: 'date',             label: 'Date' },
  { key: 'check_in_time',    label: 'Check-In Time' },
  { key: 'check_out_time',   label: 'Check-Out Time' },
  { key: 'duration_minutes', label: 'Duration (min)' },
  { key: 'method',           label: 'Scan Method' },
  { key: 'status',           label: 'Session Status' },
  { key: 'flag_reason',      label: 'Flag Reason' },
] as const;

const ALL_KEYS = EXPORT_COLUMNS.map((c) => c.key);

export default function Reports() {
  const [seasons, setSeasons] = useState<Season[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [seasonId, setSeasonId] = useState('');
  const [memberId, setMemberId] = useState('');
  const [format, setFormat] = useState<'csv' | 'pdf'>('csv');
  const [exporting, setExporting] = useState(false);
  const [selectedCols, setSelectedCols] = useState<Set<string>>(new Set(ALL_KEYS));
  const [includeSummary, setIncludeSummary] = useState(true);
  const [optionsOpen, setOptionsOpen] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    getSeasons()
      .then((s) => {
        setSeasons(s);
        const active = s.find((x) => x.is_active);
        if (active) setSeasonId(active.id);
      })
      .catch(() => toast.error('Failed to load seasons'));

    getMembers(1, 500)
      .then((p) => setMembers(p.items))
      .catch(() => toast.error('Failed to load members'));
  }, []);

  const toggleCol = (key: string) => {
    setSelectedCols((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        if (next.size > 1) next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const allSelected = selectedCols.size === ALL_KEYS.length;

  const toggleAll = () => {
    if (allSelected) {
      setSelectedCols(new Set(['member_number']));
    } else {
      setSelectedCols(new Set(ALL_KEYS));
    }
  };

  const handleExport = async () => {
    if (!seasonId) return;
    setExporting(true);
    try {
      const columns = allSelected ? undefined : [...selectedCols];
      await getExport({
        seasonId,
        format,
        memberId: memberId || undefined,
        columns,
        includeSummary,
      });
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

      <div className="neo-card p-6 space-y-5 max-w-lg">
        {/* Season */}
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

        {/* Member filter */}
        <div>
          <label className="neo-label">Member (optional)</label>
          <select
            value={memberId}
            onChange={(e) => setMemberId(e.target.value)}
            className="neo-select"
          >
            <option value="">All members</option>
            {members.map((m) => (
              <option key={m.id} value={m.id}>
                #{m.member_number} — {m.name}
              </option>
            ))}
          </select>
        </div>

        {/* Format */}
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

        {/* ── Neumorphic accordion: Export Options ─────────────────── */}
        <div className="neo-accordion">
          <div className="neo-accordion-item">
            <button
              type="button"
              className="neo-accordion-header"
              aria-expanded={optionsOpen}
              onClick={() => setOptionsOpen(!optionsOpen)}
            >
              <span>Export Options</span>
              <span className="neo-accordion-icon">
                {/* Chevron SVG — rotates via CSS when aria-expanded="true" */}
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                     stroke="currentColor" strokeWidth="2.5"
                     strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </span>
            </button>

            <div className="neo-accordion-body" data-open={optionsOpen}>
              <div className="neo-accordion-inner">
                <div className="neo-accordion-content" style={{ paddingTop: '0.25rem' }}>

                  {/* Column header + toggle all */}
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    marginBottom: '0.75rem',
                  }}>
                    <span style={{
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      color: 'var(--neo-text-muted)',
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em',
                    }}>
                      Columns
                    </span>
                    <button
                      type="button"
                      onClick={toggleAll}
                      style={{
                        background: 'none',
                        border: 'none',
                        padding: 0,
                        fontSize: '0.8125rem',
                        fontWeight: 600,
                        color: 'var(--neo-secondary)',
                        cursor: 'pointer',
                        fontFamily: 'var(--neo-font)',
                      }}
                    >
                      {allSelected ? 'Deselect All' : 'Select All'}
                    </button>
                  </div>

                  {/* Column checkboxes — 2-column grid */}
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(2, 1fr)',
                    gap: '0.5rem 1rem',
                  }}>
                    {EXPORT_COLUMNS.map((col) => (
                      <label key={col.key} className="neo-check">
                        <input
                          type="checkbox"
                          checked={selectedCols.has(col.key)}
                          onChange={() => toggleCol(col.key)}
                        />
                        <span className="neo-check-label">{col.label}</span>
                      </label>
                    ))}
                  </div>

                  {/* Divider */}
                  <div style={{
                    borderTop: '1px solid var(--neo-border-light)',
                    margin: '0.875rem 0 0.75rem',
                  }} />

                  {/* Summary toggle */}
                  <label className="neo-check">
                    <input
                      type="checkbox"
                      checked={includeSummary}
                      onChange={() => setIncludeSummary(!includeSummary)}
                    />
                    <span className="neo-check-label">Include member hour totals summary</span>
                  </label>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Download button */}
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
