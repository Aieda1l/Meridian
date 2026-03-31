const API_BASE = import.meta.env.VITE_API_URL || '';

/** Shared refresh promise so concurrent 401s don't trigger multiple refreshes. */
let refreshPromise: Promise<string> | null = null;

async function doRefresh(): Promise<string> {
  const refreshRes = await fetch(`${API_BASE}/auth/refresh`, {
    method: 'POST',
    credentials: 'include',
  });
  if (!refreshRes.ok) {
    throw new Error('Refresh failed');
  }
  const { access_token } = await refreshRes.json();
  localStorage.setItem('access_token', access_token);
  return access_token;
}

export async function apiFetch<T = unknown>(path: string, options: RequestInit = {}, _retried = false): Promise<T> {
  const token = localStorage.getItem('access_token');

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers as Record<string, string> | undefined),
    },
    credentials: 'include',
  });

  if (res.status === 401) {
    if (_retried) {
      localStorage.removeItem('access_token');
      window.location.href = '/login';
      throw new Error('Session expired');
    }
    try {
      if (!refreshPromise) {
        refreshPromise = doRefresh().finally(() => { refreshPromise = null; });
      }
      await refreshPromise;
      return apiFetch<T>(path, options, true);
    } catch {
      localStorage.removeItem('access_token');
      window.location.href = '/login';
      throw new Error('Session expired');
    }
  }

  if (!res.ok) {
    const text = await res.text();
    let message = text;
    try {
      const json = JSON.parse(text);
      message = json.detail || json.message || text;
    } catch {
      message = text.slice(0, 200);
    }
    throw new Error(message);
  }

  return res.json() as Promise<T>;
}
