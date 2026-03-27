import { Routes, Route, Navigate, NavLink } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Home from './pages/Home';
import Status from './pages/Status';
import History from './pages/History';
import Login from './pages/Login';

function ProtectedLayout() {
  const { isAuthenticated, user, logout } = useAuth();

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  return (
    <div className="min-h-screen bg-surface flex flex-col">
      {/* Header */}
      <header className="bg-navy text-white px-4 py-3 flex items-center justify-between">
        <span className="font-bold text-lg">Meridian</span>
        <div className="flex items-center gap-3">
          <span className="text-sm opacity-80">{user?.name}</span>
          <button onClick={logout} className="text-xs opacity-70 hover:opacity-100">
            Logout
          </button>
        </div>
      </header>

      {/* Content */}
      <main className="flex-1 overflow-y-auto pb-20">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/status" element={<Status />} />
          <Route path="/history" element={<History />} />
        </Routes>
      </main>

      {/* Bottom nav */}
      <nav className="fixed bottom-0 inset-x-0 bg-white border-t border-gray-200 flex safe-bottom">
        {[
          { to: '/', label: 'Home', icon: '\u{1F3E0}' },
          { to: '/status', label: 'Hours', icon: '\u{1F4CA}' },
          { to: '/history', label: 'History', icon: '\u{1F4CB}' },
        ].map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `flex-1 flex flex-col items-center py-2 text-xs transition ${isActive ? 'text-navy font-semibold' : 'text-gray-400'}`
            }
          >
            <span className="text-xl">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/*" element={<ProtectedLayout />} />
      </Routes>
    </AuthProvider>
  );
}
