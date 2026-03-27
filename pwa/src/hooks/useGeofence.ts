import { useEffect, useRef } from 'react';
import { Geolocation } from '@capacitor/geolocation';
import { apiFetch } from '../api/client';

interface LatLng {
  lat: number;
  lng: number;
}

function isInsidePolygon(point: LatLng, polygon: LatLng[]): boolean {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const xi = polygon[i].lat, yi = polygon[i].lng;
    const xj = polygon[j].lat, yj = polygon[j].lng;
    const intersect =
      yi > point.lng !== yj > point.lng &&
      point.lat < ((xj - xi) * (point.lng - yi)) / (yj - yi) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}

export function useGeofence(isCheckedIn: boolean, memberId: string) {
  const outsideCount = useRef(0);
  const watchId = useRef<string | null>(null);
  const config = useRef<{ polygon: LatLng[]; grace_period_seconds: number } | null>(null);

  useEffect(() => {
    apiFetch<{ polygon: LatLng[]; grace_period_seconds: number; buffer_meters: number }>(
      '/geofence/config',
    )
      .then((c) => {
        config.current = c;
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!isCheckedIn || !config.current) {
      outsideCount.current = 0;
      if (watchId.current) {
        Geolocation.clearWatch({ id: watchId.current });
        watchId.current = null;
      }
      return;
    }

    const start = async () => {
      watchId.current = await Geolocation.watchPosition(
        { enableHighAccuracy: true, timeout: 30000 },
        (position) => {
          if (!position || !config.current) return;
          const point: LatLng = {
            lat: position.coords.latitude,
            lng: position.coords.longitude,
          };
          const inside = isInsidePolygon(point, config.current.polygon);

          if (!inside) {
            outsideCount.current++;
            if (outsideCount.current >= 2) {
              apiFetch('/geofence/exit', {
                method: 'POST',
                body: JSON.stringify({
                  member_id: memberId,
                  latitude: point.lat,
                  longitude: point.lng,
                  accuracy_meters: position.coords.accuracy,
                }),
              }).catch(() => {});
              outsideCount.current = 0;
            }
          } else {
            if (outsideCount.current > 0) {
              apiFetch('/geofence/return', {
                method: 'POST',
                body: JSON.stringify({ member_id: memberId }),
              }).catch(() => {});
            }
            outsideCount.current = 0;
          }
        },
      );
    };

    start();

    return () => {
      if (watchId.current) {
        Geolocation.clearWatch({ id: watchId.current });
      }
    };
  }, [isCheckedIn, memberId]);
}
