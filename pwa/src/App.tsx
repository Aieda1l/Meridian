import { Routes, Route, Navigate, NavLink } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import Home from './pages/Home';
import Status from './pages/Status';
import History from './pages/History';
import Login from './pages/Login';

function ProtectedLayout() {
  const { isAuthenticated, user, logout } = useAuth();

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  return (
    <div className="min-h-screen bg-neo-surface flex flex-col">
      {/* Header */}
      <header className="neo-card-sm flex items-center justify-between rounded-none border-x-0 border-t-0">
        <span className="font-bold text-lg text-neo-dark">Meridian</span>
        <div className="flex items-center gap-3">
          <span className="text-sm text-neo-muted">{user?.name}</span>
          <button onClick={logout} className="neo-btn text-xs py-1 px-2">
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
      <nav className="fixed bottom-0 inset-x-0 bg-neo-surface border-t border-light flex safe-bottom shadow-neo-sm">
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
              `neo-nav-item flex-1 flex flex-col items-center py-2 text-xs ${isActive ? 'active' : ''}`
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
      <ToastProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/*" element={<ProtectedLayout />} />
        </Routes>
      </ToastProvider>
    </AuthProvider>
  );
}
