const API_BASE = import.meta.env.VITE_API_URL || '';

/** Shared refresh promise so concurrent 401s don't trigger multiple refreshes. */
let refreshPromise: Promise<string> | null = null;

async function doRefresh(): Promise<string> {
  const refreshRes = await fetch(`${API_BASE}/auth/refresh?client=admin`, {
    method: 'POST',
    credentials: 'include',
  });
  if (!refreshRes.ok) {
    throw new Error('Refresh failed');
  }
  const { access_token } = await refreshRes.json();
  localStorage.setItem('admin_access_token', access_token);
  return access_token;
}

export async function apiFetch<T = unknown>(path: string, options: RequestInit = {}, _retried = false): Promise<T> {
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
    if (_retried) {
      localStorage.removeItem('admin_access_token');
      window.location.href = '/admin/login';
      throw new Error('Session expired');
    }
    try {
      if (!refreshPromise) {
        refreshPromise = doRefresh().finally(() => { refreshPromise = null; });
      }
      await refreshPromise;
      return apiFetch<T>(path, options, true);
    } catch {
      localStorage.removeItem('admin_access_token');
      window.location.href = '/admin/login';
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

  if (res.status === 204) return undefined as T;
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

export const denySession = (id: string, reason?: string) =>
  apiFetch(`/sessions/${id}/deny`, {
    method: 'PATCH',
    body: JSON.stringify({ reason: reason || null }),
  });

export interface ExportOptions {
  seasonId: string;
  format: string;
  memberId?: string;
  columns?: string[];
  includeSummary?: boolean;
}

export const getExport = async (opts: ExportOptions) => {
  const token = localStorage.getItem('admin_access_token');
  const params = new URLSearchParams({
    season_id: opts.seasonId,
    format: opts.format,
  });
  if (opts.memberId) params.set('member_id', opts.memberId);
  if (opts.columns && opts.columns.length > 0) {
    params.set('columns', opts.columns.join(','));
  }
  if (opts.includeSummary === false) {
    params.set('include_summary', 'false');
  }
  const res = await fetch(
    `${API_BASE}/admin/export?${params}`,
    { headers: token ? { Authorization: `Bearer ${token}` } : {}, credentials: 'include' },
  );
  if (!res.ok) throw new Error('Export failed');
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `meridian-export.${opts.format}`;
  a.click();
  URL.revokeObjectURL(url);
};

export const forceCheckout = (sessionId: string) =>
  apiFetch<{ session_id: string; status: string; message: string }>(
    `/admin/sessions/${sessionId}/force-checkout`,
    { method: 'PATCH' },
  );

export const checkoutAll = () =>
  apiFetch<{ closed_count: number; session_ids: string[] }>(
    '/admin/checkout-all',
    { method: 'POST' },
  );

export interface MemberSessionItem {
  id: string;
  member_id: string;
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

export interface MemberSessionPage {
  items: MemberSessionItem[];
  total: number;
  page: number;
  page_size: number;
}

export const getMemberSessions = (memberId: string, page = 1, pageSize = 20, status?: string) => {
  const qs = status ? `&status=${status}` : '';
  return apiFetch<MemberSessionPage>(`/members/${memberId}/sessions?page=${page}&page_size=${pageSize}${qs}`);
};

export const getMemberHours = (memberId: string) =>
  apiFetch<MemberHours>(`/members/${memberId}/hours`);

// Geofence Zones
export const getGeofenceZones = () =>
  apiFetch<GeofenceZone[]>('/admin/geofence-zones');

export const createGeofenceZone = (data: GeofenceZoneCreate) =>
  apiFetch<GeofenceZone>('/admin/geofence-zones', { method: 'POST', body: JSON.stringify(data) });

export const updateGeofenceZone = (id: string, data: GeofenceZoneUpdate) =>
  apiFetch<GeofenceZone>(`/admin/geofence-zones/${id}`, { method: 'PATCH', body: JSON.stringify(data) });

export const deleteGeofenceZone = (id: string) =>
  apiFetch(`/admin/geofence-zones/${id}`, { method: 'DELETE' });

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

export interface MemberHours {
  member_id: string;
  hours_today: number;
  hours_this_week: number;
  hours_this_season: number;
  daily_cap: number;
  weekly_cap: number;
  season_cap: number;
}

export interface GeofenceZone {
  id: string;
  name: string;
  polygon: Array<{ lat: number; lng: number }>;
  color: string;
  scanner_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface GeofenceZoneCreate {
  name: string;
  polygon: Array<{ lat: number; lng: number }>;
  color: string;
  scanner_ids: string[];
}

export interface GeofenceZoneUpdate {
  name?: string;
  polygon?: Array<{ lat: number; lng: number }>;
  color?: string;
  scanner_ids?: string[];
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

// Notifications
export interface NotificationItem {
  id: string;
  recipient_id: string;
  notification_type: string;
  title: string;
  body: string;
  is_read: boolean;
  related_session_id: string | null;
  detail: Record<string, unknown> | null;
  created_at: string;
}

export interface NotificationPage {
  items: NotificationItem[];
  total: number;
  unread_count: number;
  page: number;
  page_size: number;
}

export const getNotifications = (page = 1, pageSize = 20, unreadOnly = false) =>
  apiFetch<NotificationPage>(`/notifications?page=${page}&page_size=${pageSize}&unread_only=${unreadOnly}`);

export const getUnreadCount = () =>
  apiFetch<{ count: number }>('/notifications/unread-count');

export const markNotificationRead = (id: string) =>
  apiFetch(`/notifications/${id}/read`, { method: 'PATCH' });

export const markAllNotificationsRead = () =>
  apiFetch('/notifications/mark-all-read', { method: 'POST' });
