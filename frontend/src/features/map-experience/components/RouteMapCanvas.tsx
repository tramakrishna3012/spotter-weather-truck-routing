import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { Feature, FeatureCollection, LineString, Point } from 'geojson';
import maplibregl, { type GeoJSONSource, type Map as MapLibreMap } from 'maplibre-gl';
import { Cloud, Compass, Crosshair, MapPin, Minus, Plus } from 'lucide-react';
import { ENV } from '../../../shared/config/env';
import { getRiskTheme } from '../../../shared/design-tokens/riskTheme';
import type {
  Checkpoint,
  ForecastSliceResponse,
  RouteCandidate,
  UnitSystem,
} from '../../../shared/types/plan';
import {
  computeRoutesBounds,
  resolveRiskSegmentCoordinates,
} from '../../../shared/utils/geometry';
import { CheckpointDetailPopover } from './CheckpointDetailPopover';
import { MapLegend } from './MapLegend';

export interface RouteMapCanvasProps {
  planId: string | null;
  routes: readonly RouteCandidate[];
  selectedRouteId: string | null;
  selectedCheckpointId: string | null;
  forecastSlice: ForecastSliceResponse | null;
  units: UnitSystem;
  timeZone?: string | null;
  isPlanning: boolean;
  onSelectRoute: (routeId: string) => void;
  onSelectCheckpoint: (checkpointId: string | null) => void;
}

const DEFAULT_CENTER: [number, number] = [-96.5, 39.5];
const DEFAULT_ZOOM = 3.8;

const SOURCE_CORRIDOR = 'corridor-heatmap';
const SOURCE_ALTERNATIVES = 'routes-alternatives';
const SOURCE_SELECTED_SEGMENTS = 'route-selected-segments';
const SOURCE_CHECKPOINTS = 'route-checkpoints';
const SOURCE_ENDPOINTS = 'route-endpoints';

const EMPTY_FC: FeatureCollection = {
  type: 'FeatureCollection',
  features: [],
};

function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return false;
  }
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function isWebGLSupported(): boolean {
  if (typeof document === 'undefined') return false;
  try {
    const canvas = document.createElement('canvas');
    const gl =
      canvas.getContext('webgl2') ||
      canvas.getContext('webgl') ||
      canvas.getContext('experimental-webgl');
    return Boolean(gl);
  } catch {
    return false;
  }
}

/**
 * Single persistent MapLibre GL JS canvas held in a ref.
 * Sources and layers are initialized ONCE on load and updated imperatively
 * via source.setData() with requestAnimationFrame coalescing.
 */
export function RouteMapCanvas({
  planId,
  routes,
  selectedRouteId,
  selectedCheckpointId,
  forecastSlice,
  units,
  timeZone,
  isPlanning,
  onSelectRoute,
  onSelectCheckpoint,
}: RouteMapCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const mapLoadedRef = useRef<boolean>(false);
  const lastFittedPlanIdRef = useRef<string | null>(null);

  const onSelectRouteRef = useRef(onSelectRoute);
  const onSelectCheckpointRef = useRef(onSelectCheckpoint);
  onSelectRouteRef.current = onSelectRoute;
  onSelectCheckpointRef.current = onSelectCheckpoint;

  const [webglUnavailable, setWebglUnavailable] = useState<boolean>(false);
  const [mapReady, setMapReady] = useState<boolean>(false);
  const [showCorridorOverlay, setShowCorridorOverlay] = useState<boolean>(true);
  const [showCheckpoints, setShowCheckpoints] = useState<boolean>(true);

  const selectedRoute = useMemo(
    () => routes.find((r) => r.id === selectedRouteId) ?? routes[0] ?? null,
    [routes, selectedRouteId],
  );

  const selectedCheckpointIndex = useMemo(() => {
    if (!selectedRoute || !selectedCheckpointId) return -1;
    return selectedRoute.checkpoints.findIndex((cp) => cp.id === selectedCheckpointId);
  }, [selectedRoute, selectedCheckpointId]);

  const selectedCheckpoint: Checkpoint | null =
    selectedRoute && selectedCheckpointIndex >= 0
      ? selectedRoute.checkpoints[selectedCheckpointIndex] ?? null
      : null;

  // Build GeoJSON payloads cleanly from backend DTOs
  const alternativesGeoJson = useMemo<FeatureCollection>(() => {
    if (!selectedRoute) return EMPTY_FC;
    const features: Feature<LineString>[] = routes
      .filter((r) => r.id !== selectedRoute.id)
      .map((r) => ({
        type: 'Feature',
        properties: { routeId: r.id },
        geometry: {
          type: 'LineString',
          coordinates: r.geometry.coordinates,
        },
      }));
    return { type: 'FeatureCollection', features };
  }, [routes, selectedRoute]);

  const selectedSegmentsGeoJson = useMemo<FeatureCollection>(() => {
    if (!selectedRoute) return EMPTY_FC;
    const features: Feature<LineString>[] = [];

    if (selectedRoute.risk_segments.length > 0) {
      for (let i = 0; i < selectedRoute.risk_segments.length; i += 1) {
        const segment = selectedRoute.risk_segments[i];
        if (!segment) continue;
        const coords = resolveRiskSegmentCoordinates(selectedRoute, segment);
        if (coords.length < 2) continue;
        const theme = getRiskTheme(segment.severity);
        features.push({
          type: 'Feature',
          properties: {
            index: i,
            severity: segment.severity,
            status: segment.status,
            color: theme.strokeColor,
            isDashed: segment.severity === 'unknown' || segment.status === 'unknown',
          },
          geometry: {
            type: 'LineString',
            coordinates: coords,
          },
        });
      }
    }

    // If backend returned a route with empty risk_segments array, draw the full geometry as unknown (dashed)
    if (features.length === 0 && selectedRoute.geometry.coordinates.length >= 2) {
      const unknownTheme = getRiskTheme('unknown');
      features.push({
        type: 'Feature',
        properties: {
          index: 0,
          severity: 'unknown',
          status: 'unknown',
          color: unknownTheme.strokeColor,
          isDashed: true,
        },
        geometry: {
          type: 'LineString',
          coordinates: selectedRoute.geometry.coordinates,
        },
      });
    }

    return { type: 'FeatureCollection', features };
  }, [selectedRoute]);

  const checkpointsGeoJson = useMemo<FeatureCollection>(() => {
    if (!selectedRoute) return EMPTY_FC;
    const features: Feature<Point>[] = selectedRoute.checkpoints.map(
      (cp, idx) => {
        const theme = getRiskTheme(cp.risk_severity);
        return {
          type: 'Feature',
          properties: {
            id: cp.id,
            index: idx,
            severity: cp.risk_severity,
            color: theme.color,
            isSelected: cp.id === selectedCheckpointId,
          },
          geometry: {
            type: 'Point',
            coordinates: [cp.lon, cp.lat],
          },
        };
      },
    );
    return { type: 'FeatureCollection', features };
  }, [selectedRoute, selectedCheckpointId]);

  const endpointsGeoJson = useMemo<FeatureCollection>(() => {
    if (!selectedRoute || selectedRoute.geometry.coordinates.length < 2) {
      return EMPTY_FC;
    }
    const coords = selectedRoute.geometry.coordinates;
    const origin = coords[0];
    const dest = coords[coords.length - 1];
    if (!origin || !dest) return EMPTY_FC;

    return {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          properties: { kind: 'origin', label: 'A', color: '#073D45' },
          geometry: { type: 'Point', coordinates: origin },
        },
        {
          type: 'Feature',
          properties: { kind: 'destination', label: 'B', color: '#126B75' },
          geometry: { type: 'Point', coordinates: dest },
        },
      ],
    };
  }, [selectedRoute]);

  const corridorHeatmapGeoJson = useMemo<FeatureCollection>(() => {
    if (!forecastSlice || forecastSlice.points.length === 0) {
      return EMPTY_FC;
    }
    const features: Feature<Point>[] = forecastSlice.points.map((pt) => {
      const theme = getRiskTheme(pt.severity);
      return {
        type: 'Feature',
        properties: {
          severity: pt.severity,
          color: theme.color,
          heatWeight: theme.heatWeight,
        },
        geometry: {
          type: 'Point',
          coordinates: [pt.lon, pt.lat],
        },
      };
    });
    return { type: 'FeatureCollection', features };
  }, [forecastSlice]);

  // Initialize single persistent MapLibre instance ONCE on mount
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    if (!isWebGLSupported()) {
      setWebglUnavailable(true);
      return;
    }

    let map: MapLibreMap;
    try {
      const styleUrl =
        ENV.mapPublicToken && ENV.mapStyleUrl.includes('{token}')
          ? ENV.mapStyleUrl.replace('{token}', encodeURIComponent(ENV.mapPublicToken))
          : ENV.mapStyleUrl;

      map = new maplibregl.Map({
        container: containerRef.current,
        style: styleUrl,
        center: DEFAULT_CENTER,
        zoom: DEFAULT_ZOOM,
        attributionControl: { compact: true },
        pitchWithRotate: false,
        dragRotate: false,
      });
    } catch {
      setWebglUnavailable(true);
      return;
    }

    mapRef.current = map;

    map.on('load', () => {
      mapLoadedRef.current = true;

      // 1. Sources (created once)
      map.addSource(SOURCE_CORRIDOR, { type: 'geojson', data: EMPTY_FC });
      map.addSource(SOURCE_ALTERNATIVES, { type: 'geojson', data: EMPTY_FC });
      map.addSource(SOURCE_SELECTED_SEGMENTS, { type: 'geojson', data: EMPTY_FC });
      map.addSource(SOURCE_CHECKPOINTS, { type: 'geojson', data: EMPTY_FC });
      map.addSource(SOURCE_ENDPOINTS, { type: 'geojson', data: EMPTY_FC });

      // 2. Translucent Corridor Heatmap Layer (below route geometry)
      map.addLayer({
        id: 'corridor-heatmap-layer',
        type: 'heatmap',
        source: SOURCE_CORRIDOR,
        paint: {
          'heatmap-weight': ['get', 'heatWeight'],
          'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 3, 0.75, 10, 1.35],
          'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 3, 18, 7, 28, 11, 42],
          'heatmap-opacity': 0.42,
          'heatmap-color': [
            'interpolate',
            ['linear'],
            ['heatmap-density'],
            0,
            'rgba(31, 122, 82, 0)',
            0.18,
            'rgba(31, 122, 82, 0.35)',
            0.42,
            'rgba(184, 114, 8, 0.50)',
            0.66,
            'rgba(194, 65, 12, 0.62)',
            0.84,
            'rgba(185, 28, 28, 0.72)',
            1.0,
            'rgba(107, 17, 36, 0.82)',
          ],
        },
      });

      map.addLayer({
        id: 'corridor-points-detail',
        type: 'circle',
        source: SOURCE_CORRIDOR,
        minzoom: 6.5,
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 6.5, 4, 11, 7],
          'circle-color': ['get', 'color'],
          'circle-opacity': 0.32,
          'circle-stroke-width': 0,
        },
      });

      // 3. Subdued Alternative Routes (clickable to switch routes)
      map.addLayer({
        id: 'routes-alternatives-casing',
        type: 'line',
        source: SOURCE_ALTERNATIVES,
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
          'line-color': '#FFFFFF',
          'line-width': 7.5,
          'line-opacity': 0.8,
        },
      });

      map.addLayer({
        id: 'routes-alternatives-line',
        type: 'line',
        source: SOURCE_ALTERNATIVES,
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
          'line-color': '#8A9CA0',
          'line-width': 4.2,
          'line-opacity': 0.78,
        },
      });

      // 4. Selected Route Risk-Colored Segments (solid + dashed for unknown)
      map.addLayer({
        id: 'route-selected-casing',
        type: 'line',
        source: SOURCE_SELECTED_SEGMENTS,
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
          'line-color': '#FFFFFF',
          'line-width': 10.5,
          'line-opacity': 0.94,
        },
      });

      map.addLayer({
        id: 'route-selected-solid',
        type: 'line',
        source: SOURCE_SELECTED_SEGMENTS,
        filter: ['!', ['get', 'isDashed']],
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
          'line-color': ['get', 'color'],
          'line-width': 6,
          'line-opacity': 0.96,
        },
      });

      map.addLayer({
        id: 'route-selected-unknown',
        type: 'line',
        source: SOURCE_SELECTED_SEGMENTS,
        filter: ['get', 'isDashed'],
        layout: { 'line-cap': 'butt', 'line-join': 'round' },
        paint: {
          'line-color': ['get', 'color'],
          'line-width': 5.5,
          'line-dasharray': [2.2, 1.8],
          'line-opacity': 0.95,
        },
      });

      // 5. Route Checkpoints (static enlarged halo on selection, no pulsing)
      map.addLayer({
        id: 'route-checkpoints-selected-halo',
        type: 'circle',
        source: SOURCE_CHECKPOINTS,
        filter: ['get', 'isSelected'],
        paint: {
          'circle-radius': 13,
          'circle-color': ['get', 'color'],
          'circle-opacity': 0.22,
          'circle-stroke-width': 2,
          'circle-stroke-color': '#166BCA',
        },
      });

      map.addLayer({
        id: 'route-checkpoints-circle',
        type: 'circle',
        source: SOURCE_CHECKPOINTS,
        paint: {
          'circle-radius': ['case', ['get', 'isSelected'], 7, 5],
          'circle-color': ['get', 'color'],
          'circle-stroke-color': '#FFFFFF',
          'circle-stroke-width': 2,
        },
      });

      // 6. Origin & Destination Pins
      map.addLayer({
        id: 'route-endpoints-circle',
        type: 'circle',
        source: SOURCE_ENDPOINTS,
        paint: {
          'circle-radius': 9,
          'circle-color': ['get', 'color'],
          'circle-stroke-color': '#FFFFFF',
          'circle-stroke-width': 2.5,
        },
      });

      // Interactive cursor & click handlers
      map.on('mouseenter', 'routes-alternatives-line', () => {
        map.getCanvas().style.cursor = 'pointer';
      });
      map.on('mouseleave', 'routes-alternatives-line', () => {
        map.getCanvas().style.cursor = '';
      });
      map.on('click', 'routes-alternatives-line', (event) => {
        const feature = event.features?.[0];
        const routeId = feature?.properties?.routeId;
        if (typeof routeId === 'string') {
          onSelectRouteRef.current(routeId);
        }
      });

      map.on('mouseenter', 'route-checkpoints-circle', () => {
        map.getCanvas().style.cursor = 'pointer';
      });
      map.on('mouseleave', 'route-checkpoints-circle', () => {
        map.getCanvas().style.cursor = '';
      });
      map.on('click', 'route-checkpoints-circle', (event) => {
        const feature = event.features?.[0];
        const cpId = feature?.properties?.id;
        if (typeof cpId === 'string') {
          onSelectCheckpointRef.current(cpId);
        }
      });

      setMapReady(true);
    });

    return () => {
      mapLoadedRef.current = false;
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Update route, checkpoint, and endpoint sources via rAF coalescing
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoadedRef.current) return;

    const rafId = window.requestAnimationFrame(() => {
      (map.getSource(SOURCE_ALTERNATIVES) as GeoJSONSource | undefined)?.setData(
        alternativesGeoJson,
      );
      (map.getSource(SOURCE_SELECTED_SEGMENTS) as GeoJSONSource | undefined)?.setData(
        selectedSegmentsGeoJson,
      );
      (map.getSource(SOURCE_CHECKPOINTS) as GeoJSONSource | undefined)?.setData(
        checkpointsGeoJson,
      );
      (map.getSource(SOURCE_ENDPOINTS) as GeoJSONSource | undefined)?.setData(
        endpointsGeoJson,
      );
    });

    return () => window.cancelAnimationFrame(rafId);
  }, [
    mapReady,
    alternativesGeoJson,
    selectedSegmentsGeoJson,
    checkpointsGeoJson,
    endpointsGeoJson,
  ]);

  // Update corridor forecast heatmap source independently (never touches route bounds!)
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoadedRef.current) return;

    const rafId = window.requestAnimationFrame(() => {
      (map.getSource(SOURCE_CORRIDOR) as GeoJSONSource | undefined)?.setData(
        corridorHeatmapGeoJson,
      );
    });

    return () => window.cancelAnimationFrame(rafId);
  }, [mapReady, corridorHeatmapGeoJson]);

  // Toggle overlay layer visibilities without recreating map or sources
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoadedRef.current) return;

    const corridorVis = showCorridorOverlay ? 'visible' : 'none';
    if (map.getLayer('corridor-heatmap-layer')) {
      map.setLayoutProperty('corridor-heatmap-layer', 'visibility', corridorVis);
    }
    if (map.getLayer('corridor-points-detail')) {
      map.setLayoutProperty('corridor-points-detail', 'visibility', corridorVis);
    }

    const cpVis = showCheckpoints ? 'visible' : 'none';
    if (map.getLayer('route-checkpoints-circle')) {
      map.setLayoutProperty('route-checkpoints-circle', 'visibility', cpVis);
    }
    if (map.getLayer('route-checkpoints-selected-halo')) {
      map.setLayoutProperty('route-checkpoints-selected-halo', 'visibility', cpVis);
    }
  }, [mapReady, showCorridorOverlay, showCheckpoints]);

  // Smooth fitBounds ONLY when a new plan completes (never jerks on slider scrub)
  const recenterToRoutes = useCallback(() => {
    const map = mapRef.current;
    if (!map || !mapLoadedRef.current || routes.length === 0) return;

    const bounds = computeRoutesBounds(routes);
    if (!bounds) return;

    map.fitBounds(bounds, {
      padding: { top: 68, right: 64, bottom: 136, left: 64 },
      duration: prefersReducedMotion() ? 0 : 420,
      maxZoom: 11,
    });
  }, [routes]);

  useEffect(() => {
    if (!mapReady || !planId || routes.length === 0) return;
    if (lastFittedPlanIdRef.current === planId) return;
    lastFittedPlanIdRef.current = planId;
    recenterToRoutes();
  }, [mapReady, planId, routes, recenterToRoutes]);

  function handleZoomIn() {
    mapRef.current?.zoomIn({ duration: prefersReducedMotion() ? 0 : 180 });
  }

  function handleZoomOut() {
    mapRef.current?.zoomOut({ duration: prefersReducedMotion() ? 0 : 180 });
  }

  function handleSelectPreviousCheckpoint() {
    if (!selectedRoute || selectedCheckpointIndex <= 0) return;
    const prev = selectedRoute.checkpoints[selectedCheckpointIndex - 1];
    if (prev) onSelectCheckpoint(prev.id);
  }

  function handleSelectNextCheckpoint() {
    if (
      !selectedRoute ||
      selectedCheckpointIndex < 0 ||
      selectedCheckpointIndex >= selectedRoute.checkpoints.length - 1
    ) {
      return;
    }
    const next = selectedRoute.checkpoints[selectedCheckpointIndex + 1];
    if (next) onSelectCheckpoint(next.id);
  }

  return (
    <div
      className="relative w-full h-full bg-[#E8EEEC] overflow-hidden"
      aria-label="Interactive truck route and weather corridor map"
    >
      {/* Map Canvas Container or Graceful WebGL Fallback */}
      {webglUnavailable ? (
        <div
          role="region"
          aria-label="Route corridor overview (map unavailable)"
          className="w-full h-full flex flex-col items-center justify-center p-6 text-center bg-[var(--color-canvas)]"
        >
          <div className="max-w-md rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-[var(--shadow-lifted)]">
            <Compass
              className="h-8 w-8 text-[var(--color-brand-action)] mx-auto mb-3"
              aria-hidden="true"
            />
            <h2 className="text-[16px] font-semibold text-[var(--color-ink)] m-0">
              Interactive map unavailable in this browser context
            </h2>
            <p className="mt-2 text-[13.5px] text-[var(--color-ink-secondary)] leading-relaxed m-0">
              WebGL hardware rendering is disabled or unsupported. All route rankings,
              severity summaries, and checkpoint arrival weather remain fully accessible
              in the Route Comparison and Checkpoints panels.
            </p>
          </div>
        </div>
      ) : (
        <div
          ref={containerRef}
          className={[
            'w-full h-full transition-opacity duration-[var(--duration-panel)]',
            isPlanning ? 'opacity-75' : 'opacity-100',
          ].join(' ')}
        />
      )}

      {/* Subtle Empty-State Geographic Framing Hint (no giant hero/KPI clichés) */}
      {!webglUnavailable && routes.length === 0 && !isPlanning ? (
        <div className="pointer-events-none absolute top-5 left-5 right-16 z-[var(--z-map-controls)] flex justify-start">
          <div className="rounded-[13px] border border-[var(--color-border)] bg-[var(--color-surface)]/92 px-3.5 py-2.5 shadow-[var(--shadow-lifted)] max-w-sm">
            <p className="text-[13px] font-medium text-[var(--color-ink)] m-0">
              Corridor map ready
            </p>
            <p className="mt-0.5 text-[12px] text-[var(--color-ink-secondary)] m-0 leading-snug">
              Compare up to three distinct truck routes with arrival-time weather
              classifications and a 0–48h corridor forecast overlay.
            </p>
          </div>
        </div>
      ) : null}

      {/* Top-Right Floating Map Controls */}
      {!webglUnavailable ? (
        <div className="absolute top-4 right-4 z-[var(--z-map-controls)] flex flex-col items-end gap-2">
          <div
            role="group"
            aria-label="Map zoom and recenter controls"
            className="flex flex-col rounded-[12px] border border-[var(--color-border-strong)] bg-[var(--color-surface)]/95 shadow-[var(--shadow-lifted)] overflow-hidden"
          >
            <button
              type="button"
              onClick={handleZoomIn}
              aria-label="Zoom in"
              className="h-9 w-9 inline-flex items-center justify-center text-[var(--color-ink)] hover:bg-[var(--color-surface-hover)] border-b border-[var(--color-border)] cursor-pointer"
            >
              <Plus className="h-4 w-4" aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={handleZoomOut}
              aria-label="Zoom out"
              className="h-9 w-9 inline-flex items-center justify-center text-[var(--color-ink)] hover:bg-[var(--color-surface-hover)] border-b border-[var(--color-border)] cursor-pointer"
            >
              <Minus className="h-4 w-4" aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={recenterToRoutes}
              disabled={routes.length === 0}
              aria-label="Recenter map to routes"
              title="Recenter map to routes"
              className="h-9 w-9 inline-flex items-center justify-center text-[var(--color-ink)] hover:bg-[var(--color-surface-hover)] disabled:opacity-40 disabled:pointer-events-none cursor-pointer"
            >
              <Crosshair className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>

          {/* Layer Visibility Toggles */}
          {routes.length > 0 ? (
            <div
              role="group"
              aria-label="Map layer visibility"
              className="flex flex-col gap-1.5"
            >
              <button
                type="button"
                aria-pressed={showCorridorOverlay}
                onClick={() => setShowCorridorOverlay((v) => !v)}
                className={[
                  'inline-flex items-center gap-1.5 h-8 px-2.5 rounded-[10px] text-[12px] font-medium border shadow-[var(--shadow-subtle)] cursor-pointer',
                  'transition-colors duration-[var(--duration-feedback)]',
                  showCorridorOverlay
                    ? 'bg-[var(--color-brand-deep)] text-white border-transparent'
                    : 'bg-[var(--color-surface)]/95 text-[var(--color-ink)] border-[var(--color-border-strong)] hover:bg-[var(--color-surface-hover)]',
                ].join(' ')}
              >
                <Cloud className="h-3.5 w-3.5" aria-hidden="true" />
                <span>Corridor weather</span>
              </button>

              <button
                type="button"
                aria-pressed={showCheckpoints}
                onClick={() => setShowCheckpoints((v) => !v)}
                className={[
                  'inline-flex items-center gap-1.5 h-8 px-2.5 rounded-[10px] text-[12px] font-medium border shadow-[var(--shadow-subtle)] cursor-pointer',
                  'transition-colors duration-[var(--duration-feedback)]',
                  showCheckpoints
                    ? 'bg-[var(--color-brand-deep)] text-white border-transparent'
                    : 'bg-[var(--color-surface)]/95 text-[var(--color-ink)] border-[var(--color-border-strong)] hover:bg-[var(--color-surface-hover)]',
                ].join(' ')}
              >
                <MapPin className="h-3.5 w-3.5" aria-hidden="true" />
                <span>Checkpoints</span>
              </button>
            </div>
          ) : null}

          <MapLegend showCorridorOverlay={showCorridorOverlay} hasPlan={routes.length > 0} />
        </div>
      ) : null}

      {/* Floating Checkpoint Detail Popover (Level-2 Overlay) */}
      {selectedCheckpoint && selectedRoute ? (
        <div className="absolute top-4 left-4 z-[var(--z-popover)]">
          <CheckpointDetailPopover
            checkpoint={selectedCheckpoint}
            checkpointIndex={selectedCheckpointIndex}
            totalCheckpoints={selectedRoute.checkpoints.length}
            units={units}
            timeZone={timeZone}
            onClose={() => onSelectCheckpoint(null)}
            onSelectPrevious={handleSelectPreviousCheckpoint}
            onSelectNext={handleSelectNextCheckpoint}
          />
        </div>
      ) : null}
    </div>
  );
}
