# Meridian

Full-stack attendance tracking system for FRC robotics teams. Members check in and out via NFC tap or rotating QR code on Apple/Google Wallet passes. The system tracks hours with configurable caps, supports geofence-based auto-checkout, offline scanner mode, self-reported checkouts with admin approval, and CSV/PDF exports.

## Architecture

```
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  Admin SPA   │   │   PWA/App    │   │   Scanner    │
│  React+Vite  │   │ React+Cap.   │   │ PyQt6 Kiosk  │
└──────┬───────┘   └──────┬───────┘   └──────┬───────┘
       │                  │                   │
       └──────────────────┼───────────────────┘
                          │ HTTPS
                ┌─────────▼─────────┐
                │   FastAPI Backend  │
                │  (Railway.app)     │
                ├────────┬──────────┤
                │ PostgreSQL  Redis  │
                └────────┴──────────┘
```

| Component | Stack |
|-----------|-------|
| **Backend** | Python 3.12, FastAPI, SQLAlchemy 2.0 async, Alembic, PostgreSQL 16 |
| **Admin Dashboard** | React 18, Vite, TypeScript, Tailwind CSS |
| **Member PWA** | React 18, Vite, TypeScript, Tailwind CSS, Capacitor.js |
| **Scanner Kiosk** | Python, PyQt6, pyscard (NFC), OpenCV + pyzbar (QR), PyInstaller |
| **Shared** | Shared React contexts (auth, toasts) and design tokens |
| **Cache / Rate Limit** | Redis |
| **Hosting** | Railway.app |

## Features

- **NFC + QR check-in/out** — Wallet passes with HMAC-signed NFC payloads and TOTP-rotating QR codes (30s window, replay prevention via Redis)
- **Apple Wallet & Google Wallet** — PKCS#7-signed .pkpass generation; Google Wallet REST API with JWT save links
- **Geofencing** — Server-validated polygon boundary with configurable buffer and coordinate validation; 90-second grace period before auto-checkout
- **Hour caps** — Daily, weekly, and season caps with 80% and 100% threshold warnings via push notifications
- **Offline scanner mode** — AES-256-GCM encrypted local cache (random per-scanner salt), SQLite event queue with max size cap, automatic sync on reconnect
- **Self-reported checkouts** — Members submit missed checkouts through the PWA; flagged for admin approval
- **Auto-timeout** — Cron endpoint closes sessions open >12 hours, flagged for review
- **Season rollover** — Admin creates new season; old sessions auto-closed, new cap counters start fresh
- **CSV/PDF export** — Reportlab-generated PDFs with styled tables and subtotals; Excel-compatible CSV with BOM
- **Audit trail** — Immutable `admin_events` log for every state change (logins, member CRUD, pass transfers, approvals)
- **PII encryption** — All names, emails, and phones encrypted at rest with pgcrypto `pgp_sym_encrypt`
- **Push notifications** — APNs (wallet pass updates) and FCM (Android/PWA alerts)

## Project Structure

```
Meridian/
├── backend/                   # FastAPI backend
│   ├── app/
│   │   ├── api/routers/       # auth, members, passes, scanner, geofence, sessions, admin
│   │   ├── core/              # config, database, redis, security, encryption, rate_limit
│   │   ├── models/            # SQLAlchemy models (member, session, season, scanner, etc.)
│   │   ├── schemas/           # Pydantic request/response schemas
│   │   ├── services/          # apple_pass, google_pass, audit, export, hour_caps, push, scan_validation
│   │   ├── migrations/        # Alembic migrations
│   │   └── main.py
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── .env.example
├── shared/                    # Shared code & design tokens
│   ├── auth-client/           # Shared React auth context + toast provider
│   │   ├── useAuth.tsx        # Configurable auth provider factory
│   │   └── ToastContext.tsx   # Toast notification context
│   ├── design-tokens.json
│   └── neumorphism.css
├── scanner/                   # Windows desktop scanner kiosk
│   ├── src/                   # PyQt6 neumorphic UI, NFC/QR readers, offline manager
│   │   ├── api_client.py      # HTTP client with typed ApiError exceptions
│   │   ├── exceptions.py      # ApiError for structured HTTP error handling
│   │   ├── offline.py         # AES-GCM cache + SQLite queue (persistent conn, max size cap)
│   │   ├── qr_reader.py       # Thread-safe QR reader with mutex-protected pause flag
│   │   └── ...
│   ├── config.json
│   ├── requirements.txt
│   └── build.spec             # PyInstaller single-exe bundling
├── pwa/                       # Member companion app (PWA + Capacitor)
│   └── src/                   # React pages: Home, Status (hour bars), History
├── admin/                     # Admin dashboard SPA
│   └── src/                   # React pages: Dashboard, Members, Approvals, Reports, Audit Log
└── railway.toml               # Railway deployment config
```

## API Endpoints

| Route | Auth | Description |
|-------|------|-------------|
| `POST /auth/login` | Public | Email + password login |
| `POST /auth/refresh` | Cookie | Rotate tokens |
| `POST /auth/logout` | — | Clear refresh cookie |
| `POST /auth/register` | Admin | Create member + TOTP secret + pass serial |
| `GET /members` | Admin | Paginated member list (decrypted PII) |
| `GET /members/{id}` | Admin/Self | Member detail |
| `PATCH /members/{id}` | Admin | Update member |
| `DELETE /members/{id}` | Admin | Soft delete |
| `POST /members/{id}/transfer-pass` | Admin | Clear device binding |
| `GET /members/{id}/hours` | Admin/Self | Daily/weekly/season hour totals |
| `GET /members/{id}/sessions` | Admin/Self | Paginated session history |
| `POST /scanner/checkin` | Scanner | NFC/QR check-in |
| `POST /scanner/checkout` | Scanner | NFC/QR checkout + hour cap eval |
| `GET /scanner/cache` | Scanner | Signed member cache snapshot |
| `POST /scanner/heartbeat` | Scanner | Connectivity + cache staleness check |
| `POST /scanner/flush-queue` | Scanner | Sync offline events |
| `POST /geofence/exit` | Member | Report leaving shop boundary |
| `POST /geofence/return` | Member | Cancel pending geofence checkout |
| `POST /geofence/checkout` | Member | Close session after grace period |
| `GET /geofence/config` | Member | Shop polygon + grace period |
| `GET /sessions` | Admin | Filterable session list |
| `PATCH /sessions/{id}/approve` | Admin | Approve flagged session |
| `PATCH /sessions/{id}/self-report` | Member | Submit self-reported checkout |
| `POST /sessions/auto-timeout` | Cron | Close stale sessions |
| `GET /admin/dashboard` | Admin/Mentor | Live stats + who's here |
| `GET/POST /admin/seasons` | Admin | Season CRUD + rollover |
| `GET /admin/export` | Admin/Mentor | CSV or PDF download |
| `GET /admin/audit-log` | Admin | Paginated audit trail |
| `POST/DELETE /passes/register/...` | Apple | PassKit device registration |
| `GET /passes/latest/...` | Apple | Updated .pkpass fetch |
| `GET /passes/download/{id}` | Member | Download pass (.pkpass or Google Wallet link) |

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 18+
- PostgreSQL 16 with `pgcrypto` extension
- Redis 7+

### Backend

```bash
cd backend
cp .env.example .env           # Fill in values
pip install -e .
alembic upgrade head
uvicorn app.main:app --reload
```

### Admin Dashboard

```bash
cd admin
npm install
echo "VITE_API_URL=http://localhost:8000" > .env
npm run dev                    # http://localhost:5173/admin
```

### PWA

```bash
cd pwa
npm install
echo "VITE_API_URL=http://localhost:8000" > .env
npm run dev                    # http://localhost:5174
```

### Scanner

```bash
cd scanner
pip install -r requirements.txt
# Set api_key in config.json (never commit real keys!)
python -m src.app
# Or build exe: pyinstaller build.spec
```

## Deployment (Railway)

1. Connect the GitHub repo to Railway
2. Railway auto-detects `backend/Dockerfile`
3. Add a PostgreSQL and Redis service
4. Set all env vars from `.env.example` in the Railway dashboard
5. Deploy — health check at `/health`

For the frontend SPAs, build and serve as static files or deploy separately (Vercel, Netlify, etc.).

## Security

- All PII (names, emails, phones) encrypted at rest with `pgp_sym_encrypt`
- UUIDs for all primary keys (no sequential IDs)
- TOTP QR codes rotate every 30 seconds with replay prevention
- NFC payloads signed with HMAC-SHA256 and validated with proper URL parsing and strict format checks
- JWT access tokens (15 min) + httpOnly refresh cookies (7 days)
- Scanner API key authentication cached in Redis (SHA-256 hashed keys, 1-hour TTL — raw keys never stored)
- Offline cache encrypted with AES-256-GCM (key derived from scanner API key via PBKDF2, random per-scanner salt)
- Rate limiting on auth endpoints (10/min)
- `DEBUG_SKIP_SCAN_VALIDATION` blocked in production by a model validator (rejects non-localhost DATABASE_URL)
- Geofence coordinates validated server-side (lat/lng range checks, minimum polygon points)
- Session state machine enforces open-to-closed transitions (prevents double-close)
- Concurrent token refresh requests coalesced to prevent race conditions
- API error responses parsed as structured JSON (server internals not leaked to clients)
- Scanner kiosk uses typed `ApiError` exceptions with status codes (no string-matching on error messages)
- QR reader thread uses mutex-protected pause flag to prevent race conditions
- Offline event queue capped at 10,000 entries to prevent unbounded disk growth

## License

Private — all rights reserved.
