const API_BASE = import.meta.env.VITE_API_URL || '';

export async function apiFetch<T = unknown>(path: string, options: RequestInit = {}): Promise<T> {
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
    const refreshRes = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
    });
    if (refreshRes.ok) {
      const { access_token } = await refreshRes.json();
      localStorage.setItem('access_token', access_token);
      return apiFetch<T>(path, options);
    }
    localStorage.removeItem('access_token');
    window.location.href = '/login';
    throw new Error('Session expired');
  }

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text);
  }

  return res.json() as Promise<T>;
}
