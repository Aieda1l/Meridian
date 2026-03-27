import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import { apiFetch, type Member } from '../api/client';

interface AuthContextValue {
  user: Member | null;
  role: string;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Member | null>(null);

  const fetchUser = useCallback(async () => {
    const token = localStorage.getItem('admin_access_token');
    if (!token) return;
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      const data = await apiFetch<Member>(`/members/${payload.sub}`);
      setUser(data);
    } catch {
      localStorage.removeItem('admin_access_token');
      setUser(null);
    }
  }, []);

  useEffect(() => { fetchUser(); }, [fetchUser]);

  const login = async (email: string, password: string) => {
    const res = await apiFetch<{ access_token: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    localStorage.setItem('admin_access_token', res.access_token);
    await fetchUser();
  };

  const logout = () => {
    localStorage.removeItem('admin_access_token');
    setUser(null);
    fetch(`${import.meta.env.VITE_API_URL || ''}/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    }).catch(() => {});
  };

  return (
    <AuthContext.Provider value={{ user, role: user?.role ?? '', isAuthenticated: !!user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
