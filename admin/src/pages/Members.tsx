import { useState, useEffect, useCallback } from 'react';
import { getMembers, createMember, checkoutAll, getSeasons, importMembers, type Member, type MemberPage, type CreateMemberData, type Season, type ImportResult } from '../api/client';
import { useToast } from '../context/ToastContext';
import DataTable from '../components/DataTable';
import Modal from '../components/Modal';
import MemberDetail from '../components/MemberDetail';

export default function Members() {
  const [data, setData] = useState<MemberPage | null>(null);
  const [page, setPage] = useState(1);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState<CreateMemberData>({
    member_number: '', name: '', email: '', phone: '', password: '', role: 'student',
  });
  const [saving, setSaving] = useState(false);
  const [selectedMemberId, setSelectedMemberId] = useState<string | null>(null);
  const [checkingOutAll, setCheckingOutAll] = useState(false);
  const [seasons, setSeasons] = useState<Season[]>([]);
  const [showImport, setShowImport] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [importing, setImporting] = useState(false);
  const { toast } = useToast();

  const PAGE_SIZE = 50;

  const refresh = useCallback(() => {
    getMembers(page, PAGE_SIZE).then(setData).catch(() => toast.error('Failed to load members'));
  }, [page]);

  useEffect(() => { refresh(); }, [refresh]);

  useEffect(() => {
    getSeasons().then(setSeasons).catch(() => {});
  }, []);

  const handleCreate = async () => {
    setSaving(true);
    try {
      await createMember(form);
      setShowAdd(false);
      setForm({ member_number: '', name: '', email: '', phone: '', password: '', role: 'student' });
      toast.success('Member created successfully');
      refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create member');
    } finally {
      setSaving(false);
    }
  };

  const handleCheckoutAll = async () => {
    if (!confirm('Close all open sessions? This will force-checkout every currently checked-in member.')) return;
    setCheckingOutAll(true);
    try {
      const res = await checkoutAll();
      toast.success(`${res.closed_count} session${res.closed_count === 1 ? '' : 's'} closed`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to checkout all');
    } finally {
      setCheckingOutAll(false);
    }
  };

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    try {
      const result = await importMembers(file);
      setImportResult(result);
      setShowImport(true);
      toast.success(`${result.total_imported} member(s) imported`);
      refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Import failed');
    } finally {
      setImporting(false);
      e.target.value = '';
    }
  };

  const columns = [
    { key: 'name', header: 'Name', render: (r: Member) => <span className="font-medium text-neo-dark">{r.name}</span> },
    { key: 'member_number', header: 'ID', render: (r: Member) => r.member_number },
    {
      key: 'role', header: 'Role',
      render: (r: Member) => (
        <span className={`neo-badge-soft ${
          r.role === 'admin' ? 'neo-badge-danger' : r.role === 'mentor' ? 'neo-badge-warning' : ''
        }`}>{r.role}</span>
      ),
    },
    {
      key: 'is_active', header: 'Status',
      render: (r: Member) => (
        <span className={r.is_active ? 'neo-badge-success' : 'neo-badge-soft'}>
          {r.is_active ? 'Active' : 'Inactive'}
        </span>
      ),
    },
    {
      key: 'created_at', header: 'Joined',
      render: (r: Member) => new Date(r.created_at).toLocaleDateString(),
    },
  ];

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-neo-dark">Members</h2>
        <div className="flex gap-3">
          <button
            onClick={handleCheckoutAll}
            disabled={checkingOutAll}
            className="neo-btn text-sm"
            style={{ color: 'var(--neo-danger)', fontWeight: 600 }}
          >
            {checkingOutAll ? 'Closing...' : 'Log Out All'}
          </button>
          <label className={`neo-btn cursor-pointer ${importing ? 'opacity-50' : ''}`}>
            {importing ? 'Importing...' : 'CSV Import'}
            <input type="file" accept=".csv" onChange={handleImport} className="hidden" disabled={importing} />
          </label>
          <button
            onClick={() => setShowAdd(true)}
            className="neo-btn neo-btn-fill-secondary"
          >
            + Add Member
          </button>
        </div>
      </div>

      <DataTable
        columns={columns}
        data={data?.items ?? []}
        keyField="id"
        page={page}
        totalPages={data ? Math.ceil(data.total / PAGE_SIZE) : 1}
        onPageChange={setPage}
        onRowClick={(row) => setSelectedMemberId(row.id)}
        loading={!data}
      />

      <Modal open={showAdd} onClose={() => setShowAdd(false)} title="Add Member">
        <div className="space-y-3">
          {(['member_number', 'name', 'email', 'phone', 'password'] as const).map((field) => (
            <div key={field}>
              <label className="neo-label capitalize">
                {field.replace('_', ' ')}
              </label>
              <input
                type={field === 'password' ? 'password' : field === 'email' ? 'email' : 'text'}
                value={(form as Record<string, string>)[field]}
                onChange={(e) => setForm((f) => ({ ...f, [field]: e.target.value }))}
                className="neo-input"
              />
            </div>
          ))}
          <div>
            <label className="neo-label">Role</label>
            <select
              value={form.role}
              onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}
              className="neo-select"
            >
              <option value="student">Student</option>
              <option value="mentor">Mentor</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          <div>
            <label className="neo-label">Season</label>
            <select
              value={form.season_id || ''}
              onChange={(e) => setForm((f) => ({ ...f, season_id: e.target.value || undefined }))}
              className="neo-select"
            >
              <option value="">Auto (active season)</option>
              {seasons.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}{s.is_active ? ' (active)' : ''}
                </option>
              ))}
            </select>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button onClick={() => setShowAdd(false)} className="neo-btn text-neo-muted">Cancel</button>
            <button
              onClick={handleCreate}
              disabled={saving}
              className="neo-btn neo-btn-fill-secondary disabled:opacity-50"
            >
              {saving ? 'Creating...' : 'Create Member'}
            </button>
          </div>
        </div>
      </Modal>

      <MemberDetail
        memberId={selectedMemberId}
        onClose={() => setSelectedMemberId(null)}
        onChanged={refresh}
      />

      <Modal open={showImport} onClose={() => { setShowImport(false); setImportResult(null); }} title="Import Results">
        {importResult && (
          <div className="space-y-3 max-h-96 overflow-y-auto">
            <p className="text-sm text-neo-muted">
              {importResult.total_imported} imported, {importResult.total_errors} error(s)
            </p>
            {importResult.imported.length > 0 && (
              <div>
                <h4 className="font-semibold text-neo-dark text-sm mb-1">Created Members</h4>
                <table className="w-full text-xs">
                  <thead><tr className="text-left text-neo-muted"><th className="pr-2">ID</th><th className="pr-2">Name</th><th className="pr-2">Password</th></tr></thead>
                  <tbody>
                    {importResult.imported.map((m) => (
                      <tr key={m.member_number}>
                        <td className="pr-2 py-0.5">{m.member_number}</td>
                        <td className="pr-2 py-0.5">{m.name}</td>
                        <td className="pr-2 py-0.5 font-mono">{m.password}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {importResult.errors.length > 0 && (
              <div>
                <h4 className="font-semibold text-neo-dark text-sm mb-1">Errors</h4>
                {importResult.errors.map((e, i) => (
                  <p key={i} className="text-xs text-danger">Row {e.row}: {e.error} ({e.member_number})</p>
                ))}
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
