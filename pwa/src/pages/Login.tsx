import { useState, type FormEvent } from 'react';
import { useNavigate, Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';

async function getDeviceFingerprint(): Promise<string> {
  const raw = [
    navigator.userAgent,
    `${screen.width}x${screen.height}`,
    Intl.DateTimeFormat().resolvedOptions().timeZone,
    navigator.language,
    navigator.hardwareConcurrency ?? '',
  ].join('|');
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(raw));
  return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('');
}

export default function Login() {
  const { login, isAuthenticated, loading: authLoading } = useAuth();
  const { toast } = useToast();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  // Already logged in — go straight to home
  if (!authLoading && isAuthenticated) return <Navigate to="/" replace />;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const fp = await getDeviceFingerprint();
      await login(email, password, { device_fingerprint: fp });
      navigate('/');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Invalid email or password');
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
          <div>
            <label className="neo-label">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="you@team.org"
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
            className="neo-btn neo-btn-fill-secondary w-full py-2.5 font-semibold"
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  );
}
