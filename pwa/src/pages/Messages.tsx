import { useState, useEffect, useCallback, useRef } from 'react';
import {
  getNotifications,
  markNotificationRead,
  markAllNotificationsRead,
  type NotificationItem,
} from '../api/client';
import { useToast } from '../context/ToastContext';

const TYPE_ICONS: Record<string, string> = {
  session_approved: '\u2705',
  session_denied: '\u274C',
  geofence_checkout: '\u{1F4CD}',
  auto_timeout: '\u23F0',
};

interface MessagesProps {
  onUnreadChange?: (count: number) => void;
}

export default function Messages({ onUnreadChange }: MessagesProps) {
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [unreadCount, setUnreadCount] = useState(0);
  const { toast } = useToast();
  const PAGE_SIZE = 20;

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getNotifications(page, PAGE_SIZE);
      setNotifications(data.items);
      setTotal(data.total);
      updateUnread(data.unread_count);
    } catch {
      toast.error('Failed to load notifications');
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => { refresh(); }, [refresh]);

  const onUnreadRef = useRef(onUnreadChange);
  onUnreadRef.current = onUnreadChange;

  const updateUnread = (count: number) => {
    setUnreadCount(count);
    onUnreadRef.current?.(count);
  };

  const handleMarkRead = async (id: string) => {
    try {
      await markNotificationRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n)),
      );
      updateUnread(Math.max(0, unreadCount - 1));
    } catch {
      toast.error('Failed to mark as read');
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await markAllNotificationsRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      updateUnread(0);
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

  if (loading) return <div className="p-4 text-neo-muted text-center py-8">Loading...</div>;

  return (
    <div className="p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-neo-dark">
          Messages
          {unreadCount > 0 && (
            <span className="ml-2 text-xs font-normal neo-badge-warning">{unreadCount} new</span>
          )}
        </h2>
        {unreadCount > 0 && (
          <button onClick={handleMarkAllRead} className="neo-btn text-xs py-1 px-2">
            Mark all read
          </button>
        )}
      </div>

      {notifications.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-3xl mb-2">{'\u{1F4EC}'}</p>
          <p className="text-neo-muted">No messages yet</p>
        </div>
      ) : (
        <div className="space-y-2">
          {notifications.map((n) => (
            <div
              key={n.id}
              className={`neo-card-sm cursor-pointer ${n.is_read ? 'opacity-60' : ''}`}
              onClick={() => !n.is_read && handleMarkRead(n.id)}
            >
              <div className="flex items-start gap-3">
                <span className="text-lg mt-0.5">
                  {TYPE_ICONS[n.notification_type] ?? '\u{1F514}'}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <p className={`text-sm text-neo-dark ${!n.is_read ? 'font-semibold' : ''}`}>
                      {n.title}
                    </p>
                    <span className="text-[11px] text-neo-muted whitespace-nowrap ml-2">
                      {timeAgo(n.created_at)}
                    </span>
                  </div>
                  <p className="text-xs text-neo-muted mt-0.5">{n.body}</p>
                </div>
                {!n.is_read && (
                  <span className="w-2 h-2 rounded-full bg-accent flex-shrink-0 mt-2" />
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
            className="neo-btn px-3 py-1 text-sm"
          >
            Prev
          </button>
          <span className="px-3 py-1 text-sm text-neo-muted">
            {page} / {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="neo-btn px-3 py-1 text-sm"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
