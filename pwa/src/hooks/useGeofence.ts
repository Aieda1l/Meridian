import { useEffect, useRef } from 'react';
import { apiFetch } from '../api/client';

interface LatLng {
  lat: number;
  lng: number;
}

interface Zone {
  id: string;
  name: string;
  polygon: LatLng[];
}

interface GeofenceConfig {
  polygon: LatLng[];
  zones?: Zone[];
  grace_period_seconds: number;
  buffer_meters: number;
}

function isPointInBufferedPolygon(point: LatLng, polygon: LatLng[], bufferMeters: number): boolean {
  // 1. Check if strictly inside
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const xi = polygon[i].lat, yi = polygon[i].lng;
    const xj = polygon[j].lat, yj = polygon[j].lng;
    const intersect =
      yi > point.lng !== yj > point.lng &&
      point.lat < ((xj - xi) * (point.lng - yi)) / (yj - yi) + xi;
    if (intersect) inside = !inside;
  }
  if (inside) return true;

  // 2. Check distance to edges (accounting for buffer)
  if (bufferMeters <= 0) return false;
  const latRad = point.lat * Math.PI / 180;
  const bufferDegrees = bufferMeters / (111320 * Math.cos(latRad));
  const bufferDegreesSq = bufferDegrees * bufferDegrees;

  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const v = polygon[j];
    const w = polygon[i];
    const l2 = (w.lng - v.lng) ** 2 + (w.lat - v.lat) ** 2;
    let dx, dy;
    if (l2 === 0) {
      dx = point.lng - v.lng;
      dy = point.lat - v.lat;
    } else {
      let t = ((point.lng - v.lng) * (w.lng - v.lng) + (point.lat - v.lat) * (w.lat - v.lat)) / l2;
      t = Math.max(0, Math.min(1, t));
      dx = point.lng - (v.lng + t * (w.lng - v.lng));
      dy = point.lat - (v.lat + t * (w.lat - v.lat));
    }
    if (dx * dx + dy * dy <= bufferDegreesSq) {
      return true;
    }
  }

  return false;
}

function isInsideAnyZone(point: LatLng, cfg: GeofenceConfig): boolean {
  const buffer = cfg.buffer_meters || 0;
  if (cfg.zones && cfg.zones.length > 0) {
    return cfg.zones.some((z) => z.polygon.length >= 3 && isPointInBufferedPolygon(point, z.polygon, buffer));
  }
  if (cfg.polygon.length >= 3) {
    return isPointInBufferedPolygon(point, cfg.polygon, buffer);
  }
  return true; // No zones configured — don't trigger exit
}

interface UseGeofenceOpts {
  isCheckedIn: boolean;
  memberId: string;
  sessionId?: string | null;
  scannerId?: string | null;
  onCheckout?: () => void;
}

export function useGeofence({ isCheckedIn, memberId, sessionId, scannerId, onCheckout }: UseGeofenceOpts) {
  const outsideCount = useRef(0);
  const watchId = useRef<number | null>(null);
  const configRef = useRef<GeofenceConfig | null>(null);
  const memberIdRef = useRef(memberId);
  const sessionIdRef = useRef(sessionId);
  const onCheckoutRef = useRef(onCheckout);
  memberIdRef.current = memberId;
  sessionIdRef.current = sessionId;
  onCheckoutRef.current = onCheckout;

  useEffect(() => {
    if (!isCheckedIn || !memberId || !navigator.geolocation) {
      outsideCount.current = 0;
      configRef.current = null;
      if (watchId.current != null) {
        navigator.geolocation.clearWatch(watchId.current);
        watchId.current = null;
      }
      return;
    }

    let cancelled = false;
    let pollTimer: ReturnType<typeof setInterval> | null = null;

    const qs = scannerId ? `?scanner_id=${encodeURIComponent(scannerId)}` : '';
    apiFetch<GeofenceConfig>(`/geofence/config${qs}`)
      .then((cfg) => {
        configRef.current = cfg;
        console.log('[Geofence] Config loaded:', cfg.zones?.length ?? 0, 'zones, grace:', cfg.grace_period_seconds, 's');

        const hasZones = (cfg.zones && cfg.zones.length > 0) || cfg.polygon.length >= 3;
        if (!hasZones) {
          console.log('[Geofence] No zones configured — skipping watch');
          return;
        }

        if (cancelled) return;
        let isFirstReading = true;
        let exitReported = false;
        outsideCount.current = 0;

        watchId.current = navigator.geolocation.watchPosition(
          (position) => {
            if (!configRef.current) return;
            const point: LatLng = {
              lat: position.coords.latitude,
              lng: position.coords.longitude,
            };
            const inside = isInsideAnyZone(point, configRef.current);

            console.log(
              '[Geofence] Position:', point.lat.toFixed(5), point.lng.toFixed(5),
              '| Inside:', inside,
              '| Exit reported:', exitReported,
            );

            if (!inside) {
              if (exitReported) return;
              outsideCount.current++;
              const threshold = isFirstReading ? 1 : 2;
              isFirstReading = false;
              if (outsideCount.current >= threshold) {
                console.log('[Geofence] Triggering exit report');
                exitReported = true;
                outsideCount.current = 0;
                apiFetch('/geofence/exit', {
                  method: 'POST',
                  body: JSON.stringify({
                    member_id: memberIdRef.current,
                    latitude: point.lat,
                    longitude: point.lng,
                    accuracy_meters: position.coords.accuracy,
                  }),
                })
                  .then(() => {
                    console.log('[Geofence] Exit reported — backend will auto-checkout after grace period');
                    // Clear any existing poll timer to prevent duplicates
                    if (pollTimer) clearInterval(pollTimer);
                    // Poll session state so UI updates when backend closes the session
                    const grace = configRef.current?.grace_period_seconds ?? 90;
                    pollTimer = setInterval(() => {
                      onCheckoutRef.current?.();
                    }, Math.min(grace * 1000 / 3, 15_000));
                  })
                  .catch((err) => {
                    console.warn('[Geofence] Exit report failed:', err);
                    exitReported = false; // allow retry
                  });
              }
            } else {
              isFirstReading = false;
              outsideCount.current = 0;
              if (exitReported) {
                console.log('[Geofence] Returned inside — cancelling exit');
                exitReported = false;
                if (pollTimer) {
                  clearInterval(pollTimer);
                  pollTimer = null;
                }
                apiFetch('/geofence/return', {
                  method: 'POST',
                  body: JSON.stringify({ member_id: memberIdRef.current }),
                }).catch((err) => console.warn('[Geofence] Return report failed:', err));
              }
            }
          },
          (err) => {
            console.warn('[Geofence] Geolocation error:', err.message);
          },
          { enableHighAccuracy: true, timeout: 30000 },
        );
      })
      .catch((err) => {
        console.warn('[Geofence] Failed to load config:', err);
      });

    return () => {
      cancelled = true;
      if (pollTimer) clearInterval(pollTimer);
      if (watchId.current != null) {
        navigator.geolocation.clearWatch(watchId.current);
        watchId.current = null;
      }
    };
  }, [isCheckedIn, memberId, scannerId]);
}
