import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(email, password);
      navigate('/');
    } catch (err) {
      setError('Invalid email or password');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-neo-surface px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-neo-dark">Meridian</h1>
          <p className="text-neo-muted mt-1">FRC Attendance</p>
        </div>

        <form onSubmit={handleSubmit} className="neo-card space-y-4">
          {error && (
            <div className="neo-alert-danger text-sm p-3 rounded-neo-sm">{error}</div>
          )}

          <div>
            <label className="neo-label">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
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
              className="neo-input"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="neo-btn neo-btn-fill-secondary w-full py-2.5 font-semibold"
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  );
}
