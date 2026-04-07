import { useState, useEffect } from 'react';
import { Routes, Route, Navigate, NavLink } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import { apiFetch } from './api/client';
import Home from './pages/Home';
import Status from './pages/Status';
import History from './pages/History';
import Messages from './pages/Messages';
import Login from './pages/Login';

function ProtectedLayout() {
  const { isAuthenticated, loading, user, logout } = useAuth();
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;

    const fetchCount = async () => {
      try {
        const { count } = await apiFetch<{ count: number }>('/notifications/unread-count');
        if (!cancelled) setUnreadCount(count);
      } catch {
        // Silently ignore
      }
    };

    fetchCount();
    const id = setInterval(fetchCount, 30_000);
    return () => { cancelled = true; clearInterval(id); };
  }, [user]);

  if (loading) {
    return (
      <div className="min-h-screen bg-neo-surface flex items-center justify-center">
        <p className="text-neo-muted">Loading...</p>
      </div>
    );
  }

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
          <Route path="/messages" element={<Messages onUnreadChange={setUnreadCount} />} />
        </Routes>
      </main>

      {/* Bottom nav */}
      <nav className="fixed bottom-0 inset-x-0 bg-neo-surface border-t border-light flex safe-bottom shadow-neo-sm">
        {[
          { to: '/', label: 'Home', icon: '\u{1F3E0}' },
          { to: '/status', label: 'Hours', icon: '\u{1F4CA}' },
          { to: '/history', label: 'History', icon: '\u{1F4CB}' },
          { to: '/messages', label: 'Messages', icon: '\u{1F514}' },
        ].map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `neo-nav-item flex-1 flex flex-col items-center py-2 text-xs ${isActive ? 'active' : ''}`
            }
          >
            <span className="text-xl relative">
              {item.icon}
              {item.to === '/messages' && unreadCount > 0 && (
                <span className="absolute -top-1 -right-2 bg-accent text-neo-white text-[9px] font-bold w-4 h-4 rounded-full flex items-center justify-center">
                  {unreadCount > 9 ? '9+' : unreadCount}
                </span>
              )}
            </span>
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
