import { useState, useEffect, useCallback } from 'react';
import { getAuditLog, type AuditLogEntry, type AuditLogPage } from '../api/client';
import { useToast } from '../context/ToastContext';
import DataTable from '../components/DataTable';

export default function AuditLog() {
  const [data, setData] = useState<AuditLogPage | null>(null);
  const [page, setPage] = useState(1);
  const [eventType, setEventType] = useState('');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const { toast } = useToast();
  const PAGE_SIZE = 50;

  const refresh = useCallback(() => {
    getAuditLog(page, PAGE_SIZE, eventType || undefined)
      .then(setData)
      .catch(() => toast.error('Failed to load audit log'));
  }, [page, eventType]);

  useEffect(() => { refresh(); }, [refresh]);

  const columns = [
    {
      key: 'created_at', header: 'Time',
      render: (r: AuditLogEntry) => (
        <span className="text-xs text-neo-muted">
          {new Date(r.created_at).toLocaleString()}
        </span>
      ),
      className: 'w-40',
    },
    { key: 'event_type', header: 'Event', render: (r: AuditLogEntry) => (
      <span className="px-2 py-0.5 text-xs font-mono neo-badge-soft">{r.event_type}</span>
    )},
    { key: 'actor_id', header: 'Actor', render: (r: AuditLogEntry) => (
      <span className="text-xs text-neo-muted truncate max-w-[120px] inline-block">{r.actor_id ?? '-'}</span>
    )},
    { key: 'target_id', header: 'Target', render: (r: AuditLogEntry) => (
      <span className="text-xs text-neo-muted truncate max-w-[120px] inline-block">{r.target_id ?? '-'}</span>
    )},
    { key: 'ip', header: 'IP', render: (r: AuditLogEntry) => (
      <span className="text-xs text-neo-muted">{r.ip_address ?? '-'}</span>
    )},
    {
      key: 'detail', header: 'Detail',
      render: (r: AuditLogEntry) => r.detail ? (
        <button
          onClick={(e) => { e.stopPropagation(); setExpandedId(expandedId === r.id ? null : r.id); }}
          className="text-xs text-accent hover:underline"
        >
          {expandedId === r.id ? 'hide' : 'show'}
        </button>
      ) : <span className="text-xs text-neo-muted">-</span>,
    },
  ];

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-neo-dark">Audit Log</h2>
        <select
          value={eventType}
          onChange={(e) => { setEventType(e.target.value); setPage(1); }}
          className="neo-select"
        >
          <option value="">All events</option>
          {['auth_login_failed', 'member_created', 'member_updated', 'member_deleted',
            'pass_transfer_authorized', 'season_created', 'geofence_exit', 'session_approved',
          ].map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>

      <DataTable
        columns={columns}
        data={data?.items ?? []}
        keyField="id"
        page={page}
        totalPages={data ? Math.ceil(data.total / PAGE_SIZE) : 1}
        onPageChange={setPage}
        loading={!data}
      />

      {/* Expanded detail */}
      {expandedId && data?.items.find((i) => i.id === expandedId)?.detail && (
        <div className="neo-card p-4">
          <pre className="text-xs text-neo-gray overflow-x-auto">
            {JSON.stringify(data.items.find((i) => i.id === expandedId)!.detail, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
