import type { LineStringGeometry, RiskSegment, RouteCandidate } from '../types/plan';

const EARTH_RADIUS_M = 6371008.8;

function toRad(deg: number): number {
  return (deg * Math.PI) / 180;
}

export function haversineDistanceMeters(
  a: [number, number],
  b: [number, number],
): number {
  const [lon1, lat1] = a;
  const [lon2, lat2] = b;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const sinLat = Math.sin(dLat / 2);
  const sinLon = Math.sin(dLon / 2);
  const h =
    sinLat * sinLat + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * sinLon * sinLon;
  return 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(h)));
}

function interpolateCoord(
  a: [number, number],
  b: [number, number],
  t: number,
): [number, number] {
  const clamped = Math.max(0, Math.min(1, t));
  return [a[0] + (b[0] - a[0]) * clamped, a[1] + (b[1] - a[1]) * clamped];
}

/**
 * Slices a route LineString between [fromDistanceM, toDistanceM] so backend risk_segments
 * without pre-sliced segment geometry render accurately along the true route polyline.
 */
export function sliceLineStringByDistance(
  geometry: LineStringGeometry,
  fromDistanceM: number,
  toDistanceM: number,
  declaredTotalDistanceM?: number,
): Array<[number, number]> {
  const coords = geometry.coordinates;
  if (coords.length < 2) return coords;

  const cumDist: number[] = [0];
  let totalGeomDist = 0;
  for (let i = 1; i < coords.length; i += 1) {
    const prev = coords[i - 1];
    const curr = coords[i];
    if (!prev || !curr) continue;
    totalGeomDist += haversineDistanceMeters(prev, curr);
    cumDist.push(totalGeomDist);
  }

  if (totalGeomDist <= 0) return coords;

  const scale =
    declaredTotalDistanceM && declaredTotalDistanceM > 0
      ? totalGeomDist / declaredTotalDistanceM
      : 1;

  const startTarget = Math.max(0, Math.min(totalGeomDist, fromDistanceM * scale));
  const endTarget = Math.max(startTarget, Math.min(totalGeomDist, toDistanceM * scale));

  if (endTarget - startTarget < 1e-3) {
    return [];
  }

  const sliced: Array<[number, number]> = [];

  for (let i = 0; i < coords.length - 1; i += 1) {
    const p0 = coords[i];
    const p1 = coords[i + 1];
    const d0 = cumDist[i] ?? 0;
    const d1 = cumDist[i + 1] ?? d0;
    if (!p0 || !p1) continue;

    if (d1 < startTarget) continue;
    if (d0 > endTarget) break;

    const segLen = d1 - d0;
    if (sliced.length === 0) {
      if (startTarget <= d0 || segLen === 0) {
        sliced.push(p0);
      } else {
        sliced.push(interpolateCoord(p0, p1, (startTarget - d0) / segLen));
      }
    }

    if (endTarget >= d1 || segLen === 0) {
      sliced.push(p1);
    } else {
      sliced.push(interpolateCoord(p0, p1, (endTarget - d0) / segLen));
      break;
    }
  }

  return sliced.length >= 2 ? sliced : [];
}

/**
 * Returns the GeoJSON coordinate array for a backend RiskSegment.
 * Uses segment.geometry directly if provided by backend, otherwise slices the route LineString.
 */
export function resolveRiskSegmentCoordinates(
  route: RouteCandidate,
  segment: RiskSegment,
): Array<[number, number]> {
  if (segment.coordinates && segment.coordinates.length >= 2) {
    return segment.coordinates;
  }
  if (segment.geometry && segment.geometry.coordinates.length >= 2) {
    return segment.geometry.coordinates;
  }
  return sliceLineStringByDistance(
    route.geometry,
    segment.from_distance_m,
    segment.to_distance_m,
    route.distance_m,
  );
}

/**
 * Computes [minLng, minLat, maxLng, maxLat] bounding box for a set of routes.
 */
export function computeRoutesBounds(
  routes: readonly RouteCandidate[],
): [[number, number], [number, number]] | null {
  let minLng = Infinity;
  let minLat = Infinity;
  let maxLng = -Infinity;
  let maxLat = -Infinity;

  for (const route of routes) {
    for (const [lng, lat] of route.geometry.coordinates) {
      if (lng < minLng) minLng = lng;
      if (lat < minLat) minLat = lat;
      if (lng > maxLng) maxLng = lng;
      if (lat > maxLat) maxLat = lat;
    }
  }

  if (!Number.isFinite(minLng) || !Number.isFinite(minLat)) {
    return null;
  }

  return [
    [minLng, minLat],
    [maxLng, maxLat],
  ];
}
