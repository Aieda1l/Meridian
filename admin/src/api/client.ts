const API_BASE = import.meta.env.VITE_API_URL || '';

export async function apiFetch<T = unknown>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('admin_access_token');

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
      localStorage.setItem('admin_access_token', access_token);
      return apiFetch<T>(path, options);
    }
    localStorage.removeItem('admin_access_token');
    window.location.href = '/admin/login';
    throw new Error('Session expired');
  }

  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<T>;
}

// Convenience helpers

export const getDashboard = () => apiFetch<DashboardData>('/admin/dashboard');

export const getMembers = (page = 1, pageSize = 50) =>
  apiFetch<MemberPage>(`/members?page=${page}&page_size=${pageSize}`);

export const getMember = (id: string) => apiFetch<Member>(`/members/${id}`);

export const createMember = (data: CreateMemberData) =>
  apiFetch('/auth/register', { method: 'POST', body: JSON.stringify(data) });

export const updateMember = (id: string, data: Partial<Member>) =>
  apiFetch(`/members/${id}`, { method: 'PATCH', body: JSON.stringify(data) });

export const deleteMember = (id: string) =>
  apiFetch(`/members/${id}`, { method: 'DELETE' });

export const transferPass = (id: string) =>
  apiFetch(`/members/${id}/transfer-pass`, { method: 'POST' });

export const getSeasons = () => apiFetch<Season[]>('/admin/seasons');

export const createSeason = (data: CreateSeasonData) =>
  apiFetch('/admin/seasons', { method: 'POST', body: JSON.stringify(data) });

export const updateSeason = (id: string, data: Partial<Season>) =>
  apiFetch(`/admin/seasons/${id}`, { method: 'PATCH', body: JSON.stringify(data) });

export const getSessions = (params: string) =>
  apiFetch<SessionPage>(`/sessions?${params}`);

export const approveSession = (id: string) =>
  apiFetch(`/sessions/${id}/approve`, { method: 'PATCH' });

export const getExport = async (seasonId: string, format: string, memberId?: string) => {
  const token = localStorage.getItem('admin_access_token');
  const qs = memberId ? `&member_id=${memberId}` : '';
  const res = await fetch(
    `${API_BASE}/admin/export?season_id=${seasonId}&format=${format}${qs}`,
    { headers: token ? { Authorization: `Bearer ${token}` } : {}, credentials: 'include' },
  );
  if (!res.ok) throw new Error('Export failed');
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `meridian-export.${format}`;
  a.click();
  URL.revokeObjectURL(url);
};

export const getAuditLog = (page = 1, pageSize = 50, eventType?: string) => {
  const qs = eventType ? `&event_type=${eventType}` : '';
  return apiFetch<AuditLogPage>(`/admin/audit-log?page=${page}&page_size=${pageSize}${qs}`);
};

// Types

export interface DashboardData {
  active_member_count: number;
  checked_in_count: number;
  checked_in_members: CheckedInMember[];
  flagged_session_count: number;
  hour_cap_violations_today: number;
  scanner_statuses: ScannerStatus[];
}

export interface CheckedInMember {
  member_id: string;
  member_name: string;
  member_number: string;
  check_in_at: string;
  duration_minutes: number;
}

export interface ScannerStatus {
  id: string;
  name: string;
  last_seen_at: string | null;
}

export interface Member {
  id: string;
  member_number: string;
  name: string;
  email: string;
  phone: string | null;
  role: string;
  is_active: boolean;
  device_platform: string;
  pass_serial: string | null;
  season_id: string | null;
  created_at: string;
}

export interface MemberPage {
  items: Member[];
  total: number;
  page: number;
  page_size: number;
}

export interface CreateMemberData {
  member_number: string;
  name: string;
  email: string;
  phone?: string;
  password: string;
  role: string;
  season_id?: string;
}

export interface Season {
  id: string;
  name: string;
  start_date: string;
  end_date: string;
  is_active: boolean;
  daily_hour_cap: number;
  weekly_hour_cap: number;
  season_hour_cap: number;
  created_at: string;
}

export interface CreateSeasonData {
  name: string;
  start_date: string;
  end_date: string;
  daily_hour_cap?: number;
  weekly_hour_cap?: number;
  season_hour_cap?: number;
}

export interface SessionItem {
  id: string;
  member_id: string;
  member_name: string | null;
  member_number: string;
  season_id: string;
  check_in_at: string;
  check_out_at: string | null;
  duration_minutes: number | null;
  check_in_method: string;
  check_out_method: string | null;
  status: string;
  flag_reason: string | null;
  created_at: string;
}

export interface SessionPage {
  items: SessionItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface AuditLogEntry {
  id: string;
  actor_id: string | null;
  event_type: string;
  target_id: string | null;
  detail: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

export interface AuditLogPage {
  items: AuditLogEntry[];
  total: number;
  page: number;
  page_size: number;
}
