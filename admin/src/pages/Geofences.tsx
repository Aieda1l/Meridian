import { useState, useEffect, useCallback, useRef } from 'react';
import {
  GoogleMap,
  useJsApiLoader,
  Polygon as GPolygon,
  Marker,
} from '@react-google-maps/api';
import {
  getGeofenceZones,
  createGeofenceZone,
  updateGeofenceZone,
  deleteGeofenceZone,
  getDashboard,
  type GeofenceZone,
  type ScannerStatus,
} from '../api/client';
import { useToast } from '../context/ToastContext';
import Modal from '../components/Modal';

const GOOGLE_API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '';
const LIBRARIES: ('places')[] = ['places'];
const DEFAULT_CENTER = { lat: 38.9, lng: -77.0 };
const DEFAULT_ZOOM = 17;
const ZONE_COLORS = ['#3388ff', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#e67e22', '#34495e'];

const MAP_CONTAINER: React.CSSProperties = {
  width: '100%',
  height: '100%',
  minHeight: '500px',
  borderRadius: 'var(--neo-radius-lg)',
};

export default function Geofences() {
  const { isLoaded } = useJsApiLoader({ googleMapsApiKey: GOOGLE_API_KEY, libraries: LIBRARIES });

  const [zones, setZones] = useState<GeofenceZone[]>([]);
  const [scanners, setScanners] = useState<ScannerStatus[]>([]);
  const [drawing, setDrawing] = useState(false);
  const [drawPoints, setDrawPoints] = useState<Array<{ lat: number; lng: number }>>([]);
  const [editingZone, setEditingZone] = useState<GeofenceZone | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [formName, setFormName] = useState('');
  const [formColor, setFormColor] = useState(ZONE_COLORS[0]);
  const [formScannerIds, setFormScannerIds] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [mapType, setMapType] = useState<'roadmap' | 'satellite'>('roadmap');
  const [showPOI, setShowPOI] = useState(false);
  const { toast } = useToast();
  const mapRef = useRef<google.maps.Map | null>(null);
  const searchInputRef = useRef<HTMLInputElement | null>(null);
  const autocompleteRef = useRef<google.maps.places.Autocomplete | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [z, d] = await Promise.all([
        getGeofenceZones(),
        getDashboard().catch(() => null),
      ]);
      setZones(z);
      if (d) setScanners(d.scanner_statuses);
    } catch {
      toast.error('Failed to load geofence zones');
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  // Fit map to show all zones
  const fitToZones = useCallback(() => {
    if (!mapRef.current || zones.length === 0) return;
    const bounds = new google.maps.LatLngBounds();
    zones.forEach((z) => z.polygon.forEach((p) => bounds.extend(p)));
    mapRef.current.fitBounds(bounds, 40);
  }, [zones]);

  useEffect(() => { fitToZones(); }, [fitToZones]);

  // Set up Places Autocomplete when map loads
  const onMapLoad = useCallback((map: google.maps.Map) => {
    mapRef.current = map;
    if (searchInputRef.current && !autocompleteRef.current) {
      const ac = new google.maps.places.Autocomplete(searchInputRef.current, {
        fields: ['geometry', 'name'],
      });
      ac.bindTo('bounds', map);
      ac.addListener('place_changed', () => {
        const place = ac.getPlace();
        if (place.geometry?.location) {
          map.panTo(place.geometry.location);
          map.setZoom(19);
        } else if (place.geometry?.viewport) {
          map.fitBounds(place.geometry.viewport);
        }
      });
      autocompleteRef.current = ac;
    }
  }, []);

  const startDrawing = () => {
    setDrawing(true);
    setDrawPoints([]);
    setEditingZone(null);
  };

  const finishDrawing = () => {
    if (drawPoints.length < 3) {
      toast.error('A boundary needs at least 3 points');
      return;
    }
    setDrawing(false);
    setFormName('');
    setFormColor(ZONE_COLORS[zones.length % ZONE_COLORS.length]);
    setFormScannerIds([]);
    setShowForm(true);
  };

  const cancelDrawing = () => {
    setDrawing(false);
    setDrawPoints([]);
  };

  const undoLastPoint = () => {
    setDrawPoints((pts) => pts.slice(0, -1));
  };

  const openEdit = (zone: GeofenceZone) => {
    setEditingZone(zone);
    setDrawPoints(zone.polygon);
    setFormName(zone.name);
    setFormColor(zone.color);
    setFormScannerIds(zone.scanner_ids);
    setShowForm(true);
    setDrawing(false);
  };

  const handleSave = async () => {
    if (!formName.trim()) { toast.error('Name is required'); return; }
    if (drawPoints.length < 3) { toast.error('At least 3 points required'); return; }

    setSaving(true);
    try {
      if (editingZone) {
        await updateGeofenceZone(editingZone.id, {
          name: formName,
          polygon: drawPoints,
          color: formColor,
          scanner_ids: formScannerIds,
        });
        toast.success('Zone updated');
      } else {
        await createGeofenceZone({
          name: formName,
          polygon: drawPoints,
          color: formColor,
          scanner_ids: formScannerIds,
        });
        toast.success('Zone created');
      }
      setShowForm(false);
      setEditingZone(null);
      setDrawPoints([]);
      refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save zone');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (zone: GeofenceZone) => {
    if (!confirm(`Delete zone "${zone.name}"? This cannot be undone.`)) return;
    try {
      await deleteGeofenceZone(zone.id);
      toast.success('Zone deleted');
      refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete zone');
    }
  };

  const toggleScanner = (id: string) => {
    setFormScannerIds((prev) =>
      prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id],
    );
  };

  const handleMapClick = useCallback((e: google.maps.MapMouseEvent) => {
    if (!drawing || !e.latLng) return;
    setDrawPoints((pts) => [...pts, { lat: e.latLng!.lat(), lng: e.latLng!.lng() }]);
  }, [drawing]);

  if (!isLoaded) {
    return <div className="p-6 text-neo-muted">Loading Google Maps...</div>;
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-neo-dark">Geofence Zones</h2>
        <div className="flex gap-3">
          {drawing ? (
            <>
              <button onClick={undoLastPoint} disabled={drawPoints.length === 0} className="neo-btn text-sm">
                Undo Point
              </button>
              <button onClick={cancelDrawing} className="neo-btn text-sm text-neo-muted">
                Cancel
              </button>
              <button onClick={finishDrawing} disabled={drawPoints.length < 3} className="neo-btn neo-btn-fill-secondary text-sm">
                Finish ({drawPoints.length} pts)
              </button>
            </>
          ) : (
            <button onClick={startDrawing} className="neo-btn neo-btn-fill-secondary">
              + Draw Boundary
            </button>
          )}
        </div>
      </div>

      {/* Search bar + map type toggle */}
      <div className="flex gap-3 items-center">
        <div className="flex-1 relative">
          <input
            ref={searchInputRef}
            type="text"
            placeholder="Search for a place..."
            className="neo-input"
            style={{ paddingLeft: '2.25rem' }}
          />
          <span
            style={{
              position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)',
              color: 'var(--neo-gray-muted)', fontSize: '0.875rem', pointerEvents: 'none',
            }}
          >
            &#x1F50D;
          </span>
        </div>
        <button
          onClick={() => setShowPOI((v) => !v)}
          className={`neo-btn text-sm ${showPOI ? 'neo-btn-fill-secondary' : ''}`}
        >
          Pins {showPOI ? 'On' : 'Off'}
        </button>
        <button
          onClick={() => setMapType((t) => t === 'roadmap' ? 'satellite' : 'roadmap')}
          className="neo-btn text-sm"
        >
          {mapType === 'roadmap' ? 'Satellite' : 'Road Map'}
        </button>
      </div>

      {drawing && (
        <div className="neo-card" style={{ padding: '0.75rem 1rem', fontSize: '0.875rem', color: 'var(--neo-text-muted)' }}>
          Click on the map to place boundary points. Place at least 3, then click "Finish" to save.
        </div>
      )}

      <div className="flex gap-4" style={{ minHeight: '550px' }}>
        {/* Map */}
        <div className="neo-card flex-1" style={{ padding: 0, overflow: 'hidden', minHeight: '550px' }}>
          <GoogleMap
            mapContainerStyle={MAP_CONTAINER}
            center={DEFAULT_CENTER}
            zoom={DEFAULT_ZOOM}
            onLoad={onMapLoad}
            onClick={handleMapClick}
            mapTypeId={mapType}
            options={{
              mapTypeControl: false,
              streetViewControl: false,
              fullscreenControl: false,
              tilt: 0,
              styles: !showPOI ? [
                { featureType: 'poi', stylers: [{ visibility: 'off' }] },
                { featureType: 'transit', stylers: [{ visibility: 'off' }] },
              ] : undefined,
            }}
          >
            {/* Existing zones */}
            {zones.map((zone) => (
              <GPolygon
                key={zone.id}
                paths={zone.polygon}
                options={{
                  strokeColor: zone.color,
                  fillColor: zone.color,
                  fillOpacity: 0.2,
                  strokeWeight: 3,
                  clickable: !drawing,
                }}
                onClick={() => { if (!drawing) openEdit(zone); }}
              />
            ))}

            {/* Currently drawing polygon */}
            {drawPoints.length >= 2 && (
              <GPolygon
                paths={drawPoints}
                options={{
                  strokeColor: '#e74c3c',
                  fillColor: '#e74c3c',
                  fillOpacity: 0.15,
                  strokeWeight: 2,
                  strokeOpacity: 0.8,
                  clickable: false,
                }}
              />
            )}

            {/* Draw point markers */}
            {drawing && drawPoints.map((pt, i) => (
              <Marker
                key={i}
                position={pt}
                icon={{
                  path: google.maps.SymbolPath.CIRCLE,
                  scale: 6,
                  fillColor: '#e74c3c',
                  fillOpacity: 1,
                  strokeColor: '#fff',
                  strokeWeight: 2,
                }}
              />
            ))}
          </GoogleMap>
        </div>

        {/* Zone list sidebar */}
        <div className="space-y-3" style={{ width: '280px', flexShrink: 0 }}>
          <h3 className="font-semibold text-neo-dark text-sm">Zones ({zones.length})</h3>
          {zones.length === 0 && (
            <p className="text-neo-muted text-sm">No zones yet. Draw a boundary on the map to create one.</p>
          )}
          {zones.map((zone) => (
            <div key={zone.id} className="neo-card" style={{ padding: '0.75rem 1rem' }}>
              <div className="flex items-center gap-2 mb-1">
                <span
                  style={{
                    width: '12px', height: '12px', borderRadius: '3px',
                    backgroundColor: zone.color, display: 'inline-block', flexShrink: 0,
                  }}
                />
                <span className="font-medium text-neo-dark text-sm truncate flex-1">{zone.name}</span>
              </div>
              <div className="text-xs text-neo-muted mb-2">
                {zone.polygon.length} vertices &middot;{' '}
                {zone.scanner_ids.length === 0
                  ? 'No scanners'
                  : `${zone.scanner_ids.length} scanner${zone.scanner_ids.length > 1 ? 's' : ''}`}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => openEdit(zone)}
                  className="neo-btn text-xs py-1 px-2"
                  style={{ color: 'var(--neo-secondary)' }}
                >
                  Edit
                </button>
                <button
                  onClick={() => { if (mapRef.current) { const b = new google.maps.LatLngBounds(); zone.polygon.forEach((p) => b.extend(p)); mapRef.current.fitBounds(b, 40); } }}
                  className="neo-btn text-xs py-1 px-2"
                >
                  Focus
                </button>
                <button
                  onClick={() => handleDelete(zone)}
                  className="neo-btn text-xs py-1 px-2"
                  style={{ color: 'var(--neo-danger)' }}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Create/Edit Modal */}
      <Modal open={showForm} onClose={() => { setShowForm(false); setEditingZone(null); setDrawPoints([]); }} title={editingZone ? 'Edit Zone' : 'New Zone'}>
        <div className="space-y-4">
          <div>
            <label className="neo-label">Name</label>
            <input
              type="text"
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              placeholder="e.g. Main Workshop"
              className="neo-input"
            />
          </div>

          <div>
            <label className="neo-label">Color</label>
            <div className="flex gap-2 flex-wrap">
              {ZONE_COLORS.map((c) => (
                <button
                  key={c}
                  onClick={() => setFormColor(c)}
                  style={{
                    width: '32px',
                    height: '32px',
                    borderRadius: '6px',
                    backgroundColor: c,
                    border: formColor === c ? '3px solid var(--neo-text)' : '2px solid transparent',
                    cursor: 'pointer',
                    transition: 'border-color 0.15s',
                  }}
                />
              ))}
            </div>
          </div>

          <div>
            <label className="neo-label">Assign Scanners</label>
            {scanners.length === 0 ? (
              <p className="text-neo-muted text-sm">No scanners registered</p>
            ) : (
              <div className="space-y-2">
                {scanners.map((s) => (
                  <label key={s.id} className="neo-check">
                    <input
                      type="checkbox"
                      checked={formScannerIds.includes(s.id)}
                      onChange={() => toggleScanner(s.id)}
                    />
                    <span className="text-sm">{s.name}</span>
                  </label>
                ))}
              </div>
            )}
          </div>

          <div className="text-xs text-neo-muted">
            {drawPoints.length} boundary points
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              onClick={() => { setShowForm(false); setEditingZone(null); setDrawPoints([]); }}
              className="neo-btn text-neo-muted"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="neo-btn neo-btn-fill-secondary disabled:opacity-50"
            >
              {saving ? 'Saving...' : editingZone ? 'Update Zone' : 'Create Zone'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
