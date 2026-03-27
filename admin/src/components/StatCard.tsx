interface StatCardProps {
  icon: string;
  label: string;
  value: string | number;
  color?: string;
}

export default function StatCard({ icon, label, value, color = 'text-navy' }: StatCardProps) {
  return (
    <div className="bg-white rounded-xl p-5 shadow-sm">
      <div className="flex items-center gap-3">
        <span className="text-2xl">{icon}</span>
        <div>
          <p className="text-xs text-gray-500 uppercase tracking-wide">{label}</p>
          <p className={`text-2xl font-bold ${color}`}>{value}</p>
        </div>
      </div>
    </div>
  );
}
