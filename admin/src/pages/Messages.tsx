import { useState, useEffect, useCallback } from 'react';
import {
  getNotifications,
  markNotificationRead,
  markAllNotificationsRead,
  type NotificationItem,
} from '../api/client';
import { useToast } from '../context/ToastContext';
import { useUnread } from '../context/UnreadContext';

const TYPE_ICONS: Record<string, string> = {
  location_permission_denied: '\u{1F6A8}',
  geofence_exit: '\u26A0\uFE0F',
  session_approved: '\u2705',
  session_denied: '\u274C',
  geofence_checkout: '\u{1F4CD}',
  auto_timeout: '\u23F0',
};

export default function Messages() {
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [unreadCount, setLocalUnread] = useState(0);
  const { setUnreadCount: setGlobalUnread } = useUnread();
  const { toast } = useToast();
  const PAGE_SIZE = 20;

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getNotifications(page, PAGE_SIZE);
      setNotifications(data.items);
      setTotal(data.total);
      setLocalUnread(data.unread_count);
      setGlobalUnread(data.unread_count);
    } catch {
      toast.error('Failed to load notifications');
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => { refresh(); }, [refresh]);

  const handleMarkRead = async (id: string) => {
    try {
      await markNotificationRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n)),
      );
      const newCount = Math.max(0, unreadCount - 1);
      setLocalUnread(newCount);
      setGlobalUnread(newCount);
    } catch {
      toast.error('Failed to mark as read');
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await markAllNotificationsRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setLocalUnread(0);
      setGlobalUnread(0);
      toast.success('All notifications marked as read');
    } catch {
      toast.error('Failed to mark all as read');
    }
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);

  const timeAgo = (dateStr: string) => {
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  };

  if (loading) return <div className="p-6 text-neo-muted">Loading...</div>;

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-neo-dark">
          Messages
          {unreadCount > 0 && (
            <span className="ml-2 text-sm font-normal neo-badge-warning">{unreadCount} unread</span>
          )}
        </h2>
        {unreadCount > 0 && (
          <button onClick={handleMarkAllRead} className="neo-btn text-sm">
            Mark all read
          </button>
        )}
      </div>

      {notifications.length === 0 ? (
        <div className="neo-card p-12 text-center">
          <p className="text-4xl mb-3">{'\u{1F4EC}'}</p>
          <p className="text-neo-muted">No notifications yet</p>
        </div>
      ) : (
        <div className="space-y-2">
          {notifications.map((n) => (
            <div
              key={n.id}
              className={`neo-card p-4 cursor-pointer transition-opacity ${n.is_read ? 'opacity-60' : ''}`}
              onClick={() => !n.is_read && handleMarkRead(n.id)}
            >
              <div className="flex items-start gap-3">
                <span className="text-xl mt-0.5">
                  {TYPE_ICONS[n.notification_type] ?? '\u{1F514}'}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <p className={`font-semibold text-neo-dark ${!n.is_read ? '' : 'font-normal'}`}>
                      {n.title}
                    </p>
                    <span className="text-xs text-neo-muted whitespace-nowrap ml-2">
                      {timeAgo(n.created_at)}
                    </span>
                  </div>
                  <p className="text-sm text-neo-muted mt-0.5">{n.body}</p>
                </div>
                {!n.is_read && (
                  <span className="w-2.5 h-2.5 rounded-full bg-accent flex-shrink-0 mt-2" />
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex justify-center gap-2 pt-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="neo-btn px-4 py-1.5 text-sm"
          >
            Prev
          </button>
          <span className="px-3 py-1.5 text-sm text-neo-muted">
            {page} / {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="neo-btn px-4 py-1.5 text-sm"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
