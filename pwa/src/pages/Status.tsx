import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
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
  const barColor = pct >= 100 ? 'bg-danger' : pct >= 80 ? 'bg-warning' : 'bg-accent';

  return (
    <div className="neo-card-sm">
      <div className="flex justify-between text-sm mb-2">
        <span className="font-semibold text-neo-gray">{label}</span>
        <span className="text-neo-muted">
          {value.toFixed(1)} / {cap.toFixed(0)} hrs
        </span>
      </div>
      <div className="neo-progress">
        <div
          className={`neo-progress-bar ${barColor}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export default function Status() {
  const { user } = useAuth();
  const { toast } = useToast();
  const [hours, setHours] = useState<Hours | null>(null);

  useEffect(() => {
    if (!user) return;
    apiFetch<Hours>(`/members/${user.id}/hours`)
      .then(setHours)
      .catch(() => toast.error('Failed to load hours'));
  }, [user]);

  if (!hours) {
    return (
      <div className="p-4">
        <h2 className="text-xl font-bold text-neo-dark mb-4">Hours</h2>
        <p className="text-neo-muted">Loading...</p>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-3">
      <h2 className="text-xl font-bold text-neo-dark">Hours</h2>
      <ProgressBar label="Today" value={hours.hours_today} cap={hours.daily_cap} />
      <ProgressBar label="This Week" value={hours.hours_this_week} cap={hours.weekly_cap} />
      <ProgressBar label="Season" value={hours.hours_this_season} cap={hours.season_cap} />
    </div>
  );
}
