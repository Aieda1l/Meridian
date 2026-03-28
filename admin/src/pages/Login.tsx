import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';

export default function Login() {
  const { login } = useAuth();
  const { toast } = useToast();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(email, password);
      navigate('/');
    } catch {
      toast.error('Invalid credentials or insufficient permissions');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-neo-surface px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-neo-dark">Meridian</h1>
          <p className="text-neo-muted mt-1">Admin Dashboard</p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="bg-neo-surface rounded-neo-xl border border-light p-8 space-y-5 shadow-neo"
        >
          <div>
            <label className="neo-label">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="admin@team.org"
              className="neo-input"
            />
          </div>

          <div>
            <label className="neo-label">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder="Password"
              className="neo-input"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="neo-btn neo-btn-fill-secondary w-full justify-center py-3"
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  );
}
