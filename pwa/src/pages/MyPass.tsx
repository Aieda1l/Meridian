import { useState, useEffect, useCallback, useMemo } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { useAuth } from '../context/AuthContext';
import { apiFetch } from '../api/client';

// ---------------------------------------------------------------------------
// Minimal TOTP implementation (RFC 6238 — SHA-1, 6 digits, 30s step)
// ---------------------------------------------------------------------------

async function hmacSha1(keyBytes: Uint8Array, message: Uint8Array): Promise<Uint8Array> {
  const key = await crypto.subtle.importKey('raw', keyBytes, { name: 'HMAC', hash: 'SHA-1' }, false, ['sign']);
  const sig = await crypto.subtle.sign('HMAC', key, message);
  return new Uint8Array(sig);
}

function base32Decode(input: string): Uint8Array {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  const cleaned = input.replace(/=+$/, '').toUpperCase();
  let bits = '';
  for (const ch of cleaned) {
    const val = alphabet.indexOf(ch);
    if (val === -1) continue;
    bits += val.toString(2).padStart(5, '0');
  }
  const bytes = new Uint8Array(Math.floor(bits.length / 8));
  for (let i = 0; i < bytes.length; i++) {
    bytes[i] = parseInt(bits.slice(i * 8, i * 8 + 8), 2);
  }
  return bytes;
}

async function generateTOTP(secret: string): Promise<string> {
  const key = base32Decode(secret);
  const epoch = Math.floor(Date.now() / 1000);
  const counter = Math.floor(epoch / 30);

  const counterBytes = new Uint8Array(8);
  let tmp = counter;
  for (let i = 7; i >= 0; i--) {
    counterBytes[i] = tmp & 0xff;
    tmp = Math.floor(tmp / 256);
  }

  const hash = await hmacSha1(key, counterBytes);
  const offset = hash[hash.length - 1] & 0x0f;
  const code =
    ((hash[offset] & 0x7f) << 24) |
    ((hash[offset + 1] & 0xff) << 16) |
    ((hash[offset + 2] & 0xff) << 8) |
    (hash[offset + 3] & 0xff);

  return (code % 1_000_000).toString().padStart(6, '0');
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface PassData {
  serial: string;
  totp_secret: string;
}

export default function MyPass() {
  const { user } = useAuth();
  const [passData, setPassData] = useState<PassData | null>(null);
  const [totpCode, setTotpCode] = useState('------');
  const [secondsLeft, setSecondsLeft] = useState(30);
  const [error, setError] = useState('');

  // Fetch pass data once
  useEffect(() => {
    if (!user) return;
    apiFetch<PassData>(`/members/${user.id}/qr-code`)
      .then(setPassData)
      .catch(() => setError('No pass found. Contact an admin.'));
  }, [user]);

  // Generate TOTP codes on a timer
  const refreshCode = useCallback(async () => {
    if (!passData) return;
    const code = await generateTOTP(passData.totp_secret);
    setTotpCode(code);
  }, [passData]);

  useEffect(() => {
    if (!passData) return;
    refreshCode();
    const id = setInterval(() => {
      refreshCode();
    }, 1000);
    return () => clearInterval(id);
  }, [passData, refreshCode]);

  // Countdown timer
  useEffect(() => {
    const tick = () => {
      const epoch = Math.floor(Date.now() / 1000);
      setSecondsLeft(30 - (epoch % 30));
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  const qrValue = useMemo(() => {
    if (!passData || totpCode === '------') return '';
    return `frcattend://totp?serial=${passData.serial}&code=${totpCode}`;
  }, [passData, totpCode]);

  if (error) {
    return (
      <div className="p-4 space-y-4">
        <h2 className="text-xl font-bold text-neo-dark">My Pass</h2>
        <div className="neo-card text-center">
          <p className="text-neo-muted">{error}</p>
        </div>
      </div>
    );
  }

  if (!passData) {
    return (
      <div className="p-4 space-y-4">
        <h2 className="text-xl font-bold text-neo-dark">My Pass</h2>
        <div className="neo-card text-center">
          <p className="text-neo-muted">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-4">
      <h2 className="text-xl font-bold text-neo-dark">My Pass</h2>

      {/* QR Code Card */}
      <div className="neo-card flex flex-col items-center space-y-4">
        <p className="text-sm text-neo-muted">Show this to a scanner to check in/out</p>

        <div className="bg-white p-4 rounded-xl shadow-neo-inset">
          {qrValue ? (
            <QRCodeSVG value={qrValue} size={220} level="M" />
          ) : (
            <div className="w-[220px] h-[220px] flex items-center justify-center text-neo-muted">
              Generating...
            </div>
          )}
        </div>

        {/* Countdown ring */}
        <div className="flex items-center gap-3">
          <div className="relative w-10 h-10">
            <svg className="w-10 h-10 -rotate-90" viewBox="0 0 40 40">
              <circle cx="20" cy="20" r="16" fill="none" stroke="var(--neo-border)" strokeWidth="3" />
              <circle
                cx="20" cy="20" r="16" fill="none"
                stroke="var(--neo-accent)"
                strokeWidth="3"
                strokeDasharray={`${(secondsLeft / 30) * 100.53} 100.53`}
                strokeLinecap="round"
              />
            </svg>
            <span className="absolute inset-0 flex items-center justify-center text-xs font-bold text-neo-dark">
              {secondsLeft}
            </span>
          </div>
          <span className="text-sm text-neo-muted">Code refreshes in {secondsLeft}s</span>
        </div>

        <p className="font-mono text-2xl tracking-[0.3em] text-neo-dark font-bold">
          {totpCode}
        </p>
      </div>

      {/* Wallet pass install */}
      <div className="neo-card space-y-3">
        <h3 className="font-semibold text-neo-dark">Install Wallet Pass</h3>
        <p className="text-sm text-neo-muted">
          Add your pass to Apple Wallet or Google Wallet for NFC tap check-in and a rotating QR code on your lock screen.
        </p>
        <button
          onClick={async () => {
            try {
              const token = localStorage.getItem('access_token');
              const res = await fetch(
                `${import.meta.env.VITE_API_URL || ''}/passes/download/${user!.id}`,
                { headers: token ? { Authorization: `Bearer ${token}` } : {}, credentials: 'include' },
              );
              if (!res.ok) throw new Error('Download failed');

              const ct = res.headers.get('content-type') || '';
              if (ct.includes('json')) {
                // Google Wallet — returns a save link
                const { save_url } = await res.json();
                window.open(save_url, '_blank');
              } else {
                // Apple Wallet — returns .pkpass blob
                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'meridian.pkpass';
                a.click();
                URL.revokeObjectURL(url);
              }
            } catch {
              // toast would be nice but we don't import it here to keep it simple
              alert('Failed to download pass. Try again later.');
            }
          }}
          className="neo-btn neo-btn-fill-secondary w-full py-3 font-medium"
        >
          Add to Wallet
        </button>
      </div>
    </div>
  );
}
