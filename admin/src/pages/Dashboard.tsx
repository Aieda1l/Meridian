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

  if (!data) return <div className="p-6 text-gray-400">Loading dashboard...</div>;

  return (
    <div className="p-6 space-y-6">
      <h2 className="text-2xl font-bold text-navy">Dashboard</h2>

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={'\u{1F465}'} label="Active Members" value={data.active_member_count} />
        <StatCard icon={'\u{1F7E2}'} label="Checked In" value={data.checked_in_count} color="text-success" />
        <StatCard icon={'\u26A0\uFE0F'} label="Flagged Sessions" value={data.flagged_session_count} color="text-danger" />
        <StatCard icon={'\u23F0'} label="Cap Violations Today" value={data.hour_cap_violations_today} color="text-yellow-600" />
      </div>

      {/* Who's here */}
      <div className="bg-white rounded-xl shadow-sm p-5">
        <h3 className="font-semibold text-navy mb-3">Who's Here</h3>
        {data.checked_in_members.length === 0 ? (
          <p className="text-gray-400 text-sm">No one is currently checked in</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-500 uppercase">
                  <th className="pb-2">Name</th>
                  <th className="pb-2">ID</th>
                  <th className="pb-2">Check-In</th>
                  <th className="pb-2">Elapsed</th>
                </tr>
              </thead>
              <tbody>
                {data.checked_in_members.map((m) => {
                  const h = Math.floor(m.duration_minutes / 60);
                  const min = m.duration_minutes % 60;
                  return (
                    <tr key={m.member_id} className="border-t border-gray-50">
                      <td className="py-2 font-medium">{m.member_name}</td>
                      <td className="py-2 text-gray-500">{m.member_number}</td>
                      <td className="py-2 text-gray-500">
                        {new Date(m.check_in_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </td>
                      <td className="py-2">{h}h {min}m</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Scanner statuses */}
      <div className="bg-white rounded-xl shadow-sm p-5">
        <h3 className="font-semibold text-navy mb-3">Scanners</h3>
        <div className="flex flex-wrap gap-3">
          {data.scanner_statuses.map((s) => {
            const ago = s.last_seen_at
              ? Math.floor((Date.now() - new Date(s.last_seen_at).getTime()) / 60000)
              : null;
            const online = ago !== null && ago < 2;
            return (
              <div key={s.id} className="flex items-center gap-2 px-3 py-2 bg-surface rounded-lg text-sm">
                <span className={`w-2 h-2 rounded-full ${online ? 'bg-success' : 'bg-gray-300'}`} />
                <span className="font-medium">{s.name}</span>
                <span className="text-gray-400 text-xs">
                  {ago !== null ? `${ago}m ago` : 'never'}
                </span>
              </div>
            );
          })}
          {data.scanner_statuses.length === 0 && (
            <p className="text-gray-400 text-sm">No scanners registered</p>
          )}
        </div>
      </div>
    </div>
  );
}
