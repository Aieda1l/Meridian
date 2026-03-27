import { NavLink } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: '\u{1F4CA}' },
  { to: '/members', label: 'Members', icon: '\u{1F465}' },
  { to: '/approvals', label: 'Approvals', icon: '\u2705' },
  { to: '/reports', label: 'Reports', icon: '\u{1F4C4}' },
  { to: '/audit-log', label: 'Audit Log', icon: '\u{1F50D}', adminOnly: true },
];

export default function Sidebar() {
  const { user, role, logout } = useAuth();

  return (
    <aside className="w-60 bg-navy text-white flex flex-col min-h-screen">
      <div className="p-5 border-b border-white/10">
        <h1 className="text-xl font-bold">Meridian</h1>
        <p className="text-xs text-white/50 mt-0.5">Admin Dashboard</p>
      </div>

      <nav className="flex-1 py-4 space-y-1 px-3">
        {NAV_ITEMS.filter((item) => !item.adminOnly || role === 'admin').map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition ${
                isActive ? 'bg-white/15 font-semibold' : 'text-white/70 hover:bg-white/5'
              }`
            }
          >
            <span>{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="p-4 border-t border-white/10">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-8 h-8 rounded-full bg-accent flex items-center justify-center text-xs font-bold">
            {user?.name?.charAt(0).toUpperCase() ?? '?'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">{user?.name}</p>
            <span className="text-[10px] bg-white/20 px-1.5 py-0.5 rounded-full">{role}</span>
          </div>
        </div>
        <button
          onClick={logout}
          className="w-full text-xs text-white/50 hover:text-white transition py-1"
        >
          Sign Out
        </button>
      </div>
    </aside>
  );
}
