import { NavLink } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: '\u{1F4CA}' },
  { to: '/members', label: 'Members', icon: '\u{1F465}' },
  { to: '/approvals', label: 'Approvals', icon: '\u2705' },
  { to: '/reports', label: 'Reports', icon: '\u{1F4C4}' },
  { to: '/geofences', label: 'Geofences', icon: '\u{1F4CD}', adminOnly: true },
  { to: '/audit-log', label: 'Audit Log', icon: '\u{1F50D}', adminOnly: true },
];

export default function Sidebar() {
  const { user, role, logout } = useAuth();

  return (
    <aside className="w-60 neo-sidebar flex flex-col h-screen sticky top-0">
      <div className="p-5 border-b border-light">
        <h1 className="text-xl font-bold text-neo-dark">Meridian</h1>
        <p className="text-xs text-neo-muted mt-0.5">Admin Dashboard</p>
      </div>

      <nav className="flex-1 py-4 space-y-1 px-3">
        {NAV_ITEMS.filter((item) => !item.adminOnly || role === 'admin').map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `neo-nav-item ${isActive ? 'active' : ''}`
            }
          >
            <span>{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="p-4 border-t border-light">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-9 h-9 rounded-full bg-accent flex items-center justify-center text-xs font-bold text-neo-white shadow-neo-sm">
            {user?.name?.charAt(0).toUpperCase() ?? '?'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-neo-dark truncate">{user?.name}</p>
            <span className="text-[10px] bg-neo-surface-d text-neo-gray px-1.5 py-0.5 rounded-full font-semibold">{role}</span>
          </div>
        </div>
        <button
          onClick={logout}
          className="neo-btn neo-btn-danger w-full text-xs py-1.5 justify-center"
        >
          Sign Out
        </button>
      </div>
    </aside>
  );
}
