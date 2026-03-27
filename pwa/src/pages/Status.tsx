import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { apiFetch } from '../api/client';

interface Hours {
  hours_today: number;
  hours_this_week: number;
  hours_this_season: number;
  daily_cap: number;
  weekly_cap: number;
  season_cap: number;
}

function ProgressBar({ label, value, cap }: { label: string; value: number; cap: number }) {
  const pct = cap > 0 ? Math.min((value / cap) * 100, 100) : 0;
  const color = pct >= 100 ? 'bg-danger' : pct >= 80 ? 'bg-yellow-500' : 'bg-accent';

  return (
    <div className="bg-white rounded-xl p-4 shadow-sm">
      <div className="flex justify-between text-sm mb-1">
        <span className="font-medium text-gray-700">{label}</span>
        <span className="text-gray-500">
          {value.toFixed(1)} / {cap.toFixed(0)} hrs
        </span>
      </div>
      <div className="w-full h-3 bg-gray-200 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export default function Status() {
  const { user } = useAuth();
  const [hours, setHours] = useState<Hours | null>(null);

  useEffect(() => {
    if (!user) return;
    apiFetch<Hours>(`/members/${user.id}/hours`).then(setHours).catch(() => {});
  }, [user]);

  if (!hours) {
    return (
      <div className="p-4">
        <h2 className="text-xl font-bold text-navy mb-4">Hours</h2>
        <p className="text-gray-400">Loading...</p>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-3">
      <h2 className="text-xl font-bold text-navy">Hours</h2>
      <ProgressBar label="Today" value={hours.hours_today} cap={hours.daily_cap} />
      <ProgressBar label="This Week" value={hours.hours_this_week} cap={hours.weekly_cap} />
      <ProgressBar label="Season" value={hours.hours_this_season} cap={hours.season_cap} />
    </div>
  );
}
