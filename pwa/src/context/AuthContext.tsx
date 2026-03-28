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
  loading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const STORAGE_KEY_TOKEN = 'access_token';
const STORAGE_KEY_USER = 'meridian_user';

/** Restore cached user from localStorage (instant, no network). */
function getCachedUser(): User | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_USER);
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

function cacheUser(u: User | null) {
  if (u) {
    localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(u));
  } else {
    localStorage.removeItem(STORAGE_KEY_USER);
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  // Restore cached user instantly so the UI doesn't flash to the login page
  const [user, setUser] = useState<User | null>(getCachedUser);
  const [loading, setLoading] = useState(true);

  const fetchUser = useCallback(async () => {
    const token = localStorage.getItem(STORAGE_KEY_TOKEN);
    if (!token) {
      setUser(null);
      cacheUser(null);
      setLoading(false);
      return;
    }
    try {
      // Decode member id from JWT payload
      const payload = JSON.parse(atob(token.split('.')[1]));
      const data = await apiFetch<User>(`/members/${payload.sub}`);
      setUser(data);
      cacheUser(data);
    } catch {
      localStorage.removeItem(STORAGE_KEY_TOKEN);
      setUser(null);
      cacheUser(null);
    } finally {
      setLoading(false);
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
    localStorage.setItem(STORAGE_KEY_TOKEN, res.access_token);
    await fetchUser();
  };

  const logout = () => {
    localStorage.removeItem(STORAGE_KEY_TOKEN);
    setUser(null);
    cacheUser(null);
    fetch(`${import.meta.env.VITE_API_URL || ''}/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    }).catch(() => {});
  };

  return (
    <AuthContext.Provider value={{ user, loading, isAuthenticated: !!user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
