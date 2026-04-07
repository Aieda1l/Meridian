import { useEffect, useRef } from 'react';
import { apiFetch } from '../api/client';
import { Capacitor, registerPlugin } from '@capacitor/core';

// Using 'any' type to avoid TS errors if the community package types don't exactly align.
const BackgroundGeolocation = registerPlugin<any>('BackgroundGeolocation');

/**
 * Web fallback for BackgroundGeolocation using navigator.geolocation.
 * Only used when the native Capacitor plugin is unavailable (i.e. running in a browser).
 */
const WebGeolocationFallback = {
  _nextId: 1,
  _watchers: new Map<string, number>(),

  addWatcher(
    _options: any,
    callback: (position: any, err: any) => void,
  ): Promise<string> {
    return new Promise((resolve, reject) => {
      if (!('geolocation' in navigator)) {
        reject(new Error('Geolocation API not available in this browser'));
        return;
      }
      const id = String(this._nextId++);
      const nativeId = navigator.geolocation.watchPosition(
        (pos) => {
          callback(
            {
              latitude: pos.coords.latitude,
              longitude: pos.coords.longitude,
              accuracy: pos.coords.accuracy,
            },
            null,
          );
        },
        (err) => {
          callback(null, err);
        },
        { enableHighAccuracy: true, maximumAge: 10_000, timeout: 30_000 },
      );
      this._watchers.set(id, nativeId);
      resolve(id);
    });
  },

  removeWatcher({ id }: { id: string }): void {
    const nativeId = this._watchers.get(id);
    if (nativeId != null) {
      navigator.geolocation.clearWatch(nativeId);
      this._watchers.delete(id);
    }
  },
};

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

function getGeolocationProvider() {
  if (Capacitor.isNativePlatform()) {
    return BackgroundGeolocation;
  }
  console.log('[Geofence] Native plugin unavailable — using web geolocation fallback');
  return WebGeolocationFallback;
}

export function useGeofence({ isCheckedIn, memberId, sessionId, scannerId, onCheckout }: UseGeofenceOpts) {
  const outsideCount = useRef(0);
  const watchId = useRef<string | null>(null);
  const configRef = useRef<GeofenceConfig | null>(null);
  const memberIdRef = useRef(memberId);
  const sessionIdRef = useRef(sessionId);
  const onCheckoutRef = useRef(onCheckout);
  memberIdRef.current = memberId;
  sessionIdRef.current = sessionId;
  onCheckoutRef.current = onCheckout;

  useEffect(() => {
    const geo = getGeolocationProvider();

    if (!isCheckedIn || !memberId) {
      outsideCount.current = 0;
      configRef.current = null;
      if (watchId.current != null) {
        geo.removeWatcher({ id: watchId.current });
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
        let permissionDeniedReported = false;
        outsideCount.current = 0;

        geo.addWatcher(
          {
            backgroundMessage: 'Meridian is tracking your shop attendance.',
            backgroundTitle: 'Meridian Tracking Active',
            requestPermissions: true,
            stale: false,
            distanceFilter: 10,
          },
          (position: any, err: any) => {
            if (err) {
              console.warn('[Geofence] Geolocation error:', err);
              // Report location permission denial to backend (code 1 = PERMISSION_DENIED)
              if (err.code === 1 && !permissionDeniedReported) {
                permissionDeniedReported = true;
                apiFetch('/geofence/location-denied', {
                  method: 'POST',
                  body: JSON.stringify({ member_id: memberIdRef.current }),
                }).catch((e) => console.warn('[Geofence] Failed to report permission denial:', e));
              }
              return;
            }
            if (!position) return;
            if (!configRef.current) return;
            const point: LatLng = {
              lat: position.latitude,
              lng: position.longitude,
            };
            const inside = isInsideAnyZone(point, configRef.current);

            console.log(
              '[Geofence] Position:', point.lat?.toFixed(5), point.lng?.toFixed(5),
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
                    accuracy_meters: position.accuracy || 10,
                  }),
                })
                  .then(() => {
                    console.log('[Geofence] Exit reported — backend will auto-checkout after grace period');
                    if (pollTimer) clearInterval(pollTimer);
                    const grace = configRef.current?.grace_period_seconds ?? 90;
                    pollTimer = setInterval(() => {
                      onCheckoutRef.current?.();
                    }, Math.min(grace * 1000 / 3, 15_000));
                  })
                  .catch((error) => {
                    console.warn('[Geofence] Exit report failed:', error);
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
                }).catch((error) => console.warn('[Geofence] Return report failed:', error));
              }
            }
          }
        ).then((id: string) => {
          if (cancelled) {
            geo.removeWatcher({ id });
          } else {
            watchId.current = id;
          }
        });
      })
      .catch((err) => {
        console.warn('[Geofence] Failed to load config:', err);
      });

    return () => {
      cancelled = true;
      if (pollTimer) clearInterval(pollTimer);
      if (watchId.current != null) {
        geo.removeWatcher({ id: watchId.current });
        watchId.current = null;
      }
    };
  }, [isCheckedIn, memberId, scannerId]);
}
