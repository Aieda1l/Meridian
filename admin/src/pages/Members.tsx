import { useState, useEffect, useCallback } from 'react';
import { getMembers, createMember, type Member, type MemberPage, type CreateMemberData } from '../api/client';
import { useToast } from '../context/ToastContext';
import DataTable from '../components/DataTable';
import Modal from '../components/Modal';

export default function Members() {
  const [data, setData] = useState<MemberPage | null>(null);
  const [page, setPage] = useState(1);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState<CreateMemberData>({
    member_number: '', name: '', email: '', phone: '', password: '', role: 'student',
  });
  const [saving, setSaving] = useState(false);
  const { toast } = useToast();

  const PAGE_SIZE = 50;

  const refresh = useCallback(() => {
    getMembers(page, PAGE_SIZE).then(setData).catch(() => toast.error('Failed to load members'));
  }, [page]);

  useEffect(() => { refresh(); }, [refresh]);

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
        <button
          onClick={() => setShowAdd(true)}
          className="neo-btn neo-btn-fill-secondary"
        >
          + Add Member
        </button>
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
    </div>
  );
}
