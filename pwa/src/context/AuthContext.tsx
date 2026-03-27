import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import { apiFetch } from '../api/client';

interface User {
  id: string;
  member_number: string;
  name: string;
  email: string;
  role: string;
}

interface AuthContextValue {
  user: User | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);

  const fetchUser = useCallback(async () => {
    const token = localStorage.getItem('access_token');
    if (!token) return;
    try {
      // Decode member id from JWT payload
      const payload = JSON.parse(atob(token.split('.')[1]));
      const data = await apiFetch<User>(`/members/${payload.sub}`);
      setUser(data);
    } catch {
      localStorage.removeItem('access_token');
      setUser(null);
    }
  }, []);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  const login = async (email: string, password: string) => {
    const res = await apiFetch<{ access_token: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    localStorage.setItem('access_token', res.access_token);
    await fetchUser();
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    setUser(null);
    fetch(`${import.meta.env.VITE_API_URL || ''}/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    }).catch(() => {});
  };

  return (
    <AuthContext.Provider value={{ user, isAuthenticated: !!user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
