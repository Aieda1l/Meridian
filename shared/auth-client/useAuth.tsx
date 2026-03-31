/**
 * Shared authentication context and hook.
 *
 * Both the PWA and admin dashboard import from here to avoid duplicating
 * JWT parsing, token refresh, and localStorage caching logic.
 *
 * Usage:
 *   import { createAuthProvider, useAuth } from '../../shared/auth-client/useAuth';
 *   const { AuthProvider } = createAuthProvider({ storageKeyToken: '...', storageKeyUser: '...' });
 */
import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface User {
  id: string;
  member_number: string;
  name: string;
  email: string;
  role: string;
  [key: string]: unknown;
}

interface AuthContextValue {
  user: User | null;
  role: string;
  loading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

interface AuthConfig {
  /** localStorage key for the access token (e.g. 'access_token' or 'admin_access_token') */
  storageKeyToken: string;
  /** localStorage key for cached user data */
  storageKeyUser: string;
  /** apiFetch function from the app's api/client module */
  apiFetch: <T = unknown>(path: string, options?: RequestInit) => Promise<T>;
  /** Base API URL for the logout call */
  apiBaseUrl?: string;
  /** Path to redirect to on logout */
  logoutRedirect?: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getCachedUser(key: string): User | null {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

function cacheUser(key: string, u: User | null) {
  if (u) {
    localStorage.setItem(key, JSON.stringify(u));
  } else {
    localStorage.removeItem(key);
  }
}

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

const AuthContext = createContext<AuthContextValue | null>(null);

export function createAuthProvider(config: AuthConfig) {
  const {
    storageKeyToken,
    storageKeyUser,
    apiFetch,
    apiBaseUrl = '',
  } = config;

  function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<User | null>(() => getCachedUser(storageKeyUser));
    const [loading, setLoading] = useState(true);

    const fetchUser = useCallback(async () => {
      const token = localStorage.getItem(storageKeyToken);
      if (!token) {
        setUser(null);
        cacheUser(storageKeyUser, null);
        setLoading(false);
        return;
      }
      try {
        const parts = token.split('.');
        if (parts.length !== 3) throw new Error('Invalid token structure');
        let base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
        const pad = base64.length % 4;
        if (pad) base64 += '='.repeat(4 - pad);
        const payload = JSON.parse(window.atob(base64));
        const data = await apiFetch<User>(`/members/${payload.sub}`);
        setUser(data);
        cacheUser(storageKeyUser, data);
      } catch {
        localStorage.removeItem(storageKeyToken);
        setUser(null);
        cacheUser(storageKeyUser, null);
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
      localStorage.setItem(storageKeyToken, res.access_token);
      await fetchUser();
    };

    const logout = () => {
      localStorage.removeItem(storageKeyToken);
      setUser(null);
      cacheUser(storageKeyUser, null);
      const base = apiBaseUrl || (typeof import.meta !== 'undefined' ? (import.meta as any).env?.VITE_API_URL || '' : '');
      fetch(`${base}/auth/logout`, {
        method: 'POST',
        credentials: 'include',
      }).catch(() => {});
    };

    return (
      <AuthContext.Provider
        value={{
          user,
          role: user?.role ?? '',
          loading,
          isAuthenticated: !!user,
          login,
          logout,
        }}
      >
        {children}
      </AuthContext.Provider>
    );
  }

  return { AuthProvider };
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
