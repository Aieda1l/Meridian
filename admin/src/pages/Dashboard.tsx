import { useState, useEffect } from 'react';
import { getDashboard, type DashboardData } from '../api/client';
import StatCard from '../components/StatCard';

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);

  const refresh = () => getDashboard().then(setData).catch(() => {});

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 30_000);
    return () => clearInterval(id);
  }, []);

  if (!data) return <div className="p-6 text-neo-muted">Loading dashboard...</div>;

  return (
    <div className="p-6 space-y-6">
      <h2 className="text-2xl font-bold text-neo-dark">Dashboard</h2>

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={'\u{1F465}'} label="Active Members" value={data.active_member_count} />
        <StatCard icon={'\u{1F7E2}'} label="Checked In" value={data.checked_in_count} color="neo-text-success" />
        <StatCard icon={'\u26A0\uFE0F'} label="Flagged Sessions" value={data.flagged_session_count} color="neo-text-danger" />
        <StatCard icon={'\u23F0'} label="Cap Violations Today" value={data.hour_cap_violations_today} color="neo-text-warning" />
      </div>

      {/* Who's here */}
      <div className="neo-card">
        <h3 className="font-semibold text-neo-dark mb-3">Who's Here</h3>
        {data.checked_in_members.length === 0 ? (
          <p className="text-neo-muted text-sm">No one is currently checked in</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="neo-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>ID</th>
                  <th>Check-In</th>
                  <th>Elapsed</th>
                </tr>
              </thead>
              <tbody>
                {data.checked_in_members.map((m) => {
                  const h = Math.floor(m.duration_minutes / 60);
                  const min = m.duration_minutes % 60;
                  return (
                    <tr key={m.member_id}>
                      <td className="font-medium">{m.member_name}</td>
                      <td className="text-neo-muted">{m.member_number}</td>
                      <td className="text-neo-muted">
                        {new Date(m.check_in_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </td>
                      <td>{h}h {min}m</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Scanner statuses */}
      <div className="neo-card">
        <h3 className="font-semibold text-neo-dark mb-3">Scanners</h3>
        <div className="flex flex-wrap gap-3">
          {data.scanner_statuses.map((s) => {
            const ago = s.last_seen_at
              ? Math.floor((Date.now() - new Date(s.last_seen_at).getTime()) / 60000)
              : null;
            const online = ago !== null && ago < 2;
            return (
              <div key={s.id} className="neo-badge-soft flex items-center gap-2 px-3 py-2 text-sm">
                <span className={`w-2 h-2 rounded-full ${online ? 'bg-green-600' : 'bg-neo-muted'}`} />
                <span className="font-medium text-neo-dark">{s.name}</span>
                <span className="text-neo-muted text-xs">
                  {ago !== null ? `${ago}m ago` : 'never'}
                </span>
              </div>
            );
          })}
          {data.scanner_statuses.length === 0 && (
            <p className="text-neo-muted text-sm">No scanners registered</p>
          )}
        </div>
      </div>
    </div>
  );
}
