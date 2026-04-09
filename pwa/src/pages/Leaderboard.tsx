import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { apiFetch } from '../api/client';

interface LeaderboardEntry {
  rank: number;
  member_id: string;
  member_number: string;
  name: string;
  total_hours: number;
}

interface LeaderboardData {
  season_name: string;
  entries: LeaderboardEntry[];
}

export default function Leaderboard() {
  const { user } = useAuth();
  const [data, setData] = useState<LeaderboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<LeaderboardData>('/members/leaderboard')
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const podiumColors = ['text-yellow-500', 'text-gray-400', 'text-amber-600'];

  return (
    <div className="p-4 space-y-4">
      <h2 className="text-xl font-bold text-neo-dark">Leaderboard</h2>
      {data && (
        <p className="text-sm text-neo-muted">{data.season_name}</p>
      )}

      {loading ? (
        <div className="neo-card text-center">
          <p className="text-neo-muted">Loading...</p>
        </div>
      ) : !data || data.entries.length === 0 ? (
        <div className="neo-card text-center">
          <p className="text-neo-muted">No attendance data yet this season.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {data.entries.map((entry) => {
            const isMe = entry.member_id === user?.id;
            return (
              <div
                key={entry.member_id}
                className={`neo-card-sm flex items-center gap-3 ${isMe ? 'border-accent/40' : ''}`}
              >
                <div className={`w-8 text-center font-bold text-lg ${entry.rank <= 3 ? podiumColors[entry.rank - 1] : 'text-neo-muted'}`}>
                  {entry.rank <= 3 ? ['1st', '2nd', '3rd'][entry.rank - 1] : `#${entry.rank}`}
                </div>
                <div className="flex-1 min-w-0">
                  <p className={`font-medium truncate ${isMe ? 'text-accent' : 'text-neo-dark'}`}>
                    {entry.name}
                    {isMe && <span className="text-xs ml-1">(you)</span>}
                  </p>
                  <p className="text-xs text-neo-muted">{entry.member_number}</p>
                </div>
                <div className="text-right">
                  <p className="font-bold text-neo-dark">{entry.total_hours}h</p>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
