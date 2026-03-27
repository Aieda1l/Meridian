import { useState, useEffect, useCallback } from 'react';
import { getMembers, createMember, type Member, type MemberPage, type CreateMemberData } from '../api/client';
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
  const [error, setError] = useState('');

  const PAGE_SIZE = 50;

  const refresh = useCallback(() => {
    getMembers(page, PAGE_SIZE).then(setData).catch(() => {});
  }, [page]);

  useEffect(() => { refresh(); }, [refresh]);

  const handleCreate = async () => {
    setError('');
    setSaving(true);
    try {
      await createMember(form);
      setShowAdd(false);
      setForm({ member_number: '', name: '', email: '', phone: '', password: '', role: 'student' });
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed');
    } finally {
      setSaving(false);
    }
  };

  const columns = [
    { key: 'name', header: 'Name', render: (r: Member) => <span className="font-medium">{r.name}</span> },
    { key: 'member_number', header: 'ID', render: (r: Member) => r.member_number },
    {
      key: 'role', header: 'Role',
      render: (r: Member) => (
        <span className={`px-2 py-0.5 text-xs font-semibold rounded-full ${
          r.role === 'admin' ? 'bg-navy text-white' : r.role === 'mentor' ? 'bg-accent text-white' : 'bg-gray-200'
        }`}>{r.role}</span>
      ),
    },
    {
      key: 'is_active', header: 'Status',
      render: (r: Member) => (
        <span className={`px-2 py-0.5 text-xs font-semibold rounded-full ${r.is_active ? 'bg-success/20 text-success' : 'bg-gray-200 text-gray-500'}`}>
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
        <h2 className="text-2xl font-bold text-navy">Members</h2>
        <button
          onClick={() => setShowAdd(true)}
          className="px-4 py-2 bg-navy text-white rounded-lg text-sm font-medium hover:bg-opacity-90 transition"
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
          {error && <div className="bg-red-50 text-danger text-sm p-3 rounded-lg">{error}</div>}
          {(['member_number', 'name', 'email', 'phone', 'password'] as const).map((field) => (
            <div key={field}>
              <label className="block text-sm font-medium text-gray-700 mb-1 capitalize">
                {field.replace('_', ' ')}
              </label>
              <input
                type={field === 'password' ? 'password' : field === 'email' ? 'email' : 'text'}
                value={(form as Record<string, string>)[field]}
                onChange={(e) => setForm((f) => ({ ...f, [field]: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-accent"
              />
            </div>
          ))}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Role</label>
            <select
              value={form.role}
              onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg outline-none"
            >
              <option value="student">Student</option>
              <option value="mentor">Mentor</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button onClick={() => setShowAdd(false)} className="px-4 py-2 text-gray-600 text-sm">Cancel</button>
            <button
              onClick={handleCreate}
              disabled={saving}
              className="px-4 py-2 bg-navy text-white rounded-lg text-sm font-medium disabled:opacity-50"
            >
              {saving ? 'Creating...' : 'Create Member'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
