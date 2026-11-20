import { describe, expect, it } from 'vitest';
import {
  buildOffsetIsoTimestamp,
  formatAverageRisk,
  formatCoveragePercent,
  formatDistanceFromMeters,
  formatDuration,
  formatMiles,
  formatRain,
  formatSnow,
  formatTimestampWithZone,
  formatWeightLb,
  formatWind,
  NULL_DISPLAY,
} from '../shared/utils/format';

describe('format utilities — null safety and unit fidelity', () => {
  it('never coerces null, undefined, or NaN to zero', () => {
    expect(formatDistanceFromMeters(null)).toBe(NULL_DISPLAY);
    expect(formatDistanceFromMeters(undefined)).toBe(NULL_DISPLAY);
    expect(formatDistanceFromMeters(Number.NaN)).toBe(NULL_DISPLAY);

    expect(formatMiles(null)).toBe(NULL_DISPLAY);
    expect(formatDuration(null)).toBe(NULL_DISPLAY);
    expect(formatDuration(-10)).toBe(NULL_DISPLAY);
    expect(formatWeightLb(null)).toBe(NULL_DISPLAY);
    expect(formatWind(null)).toBe(NULL_DISPLAY);
    expect(formatRain(null)).toBe(NULL_DISPLAY);
    expect(formatSnow(null)).toBe(NULL_DISPLAY);
    expect(formatAverageRisk(null)).toBe(NULL_DISPLAY);
    expect(formatCoveragePercent(null)).toBe(NULL_DISPLAY);
    expect(formatTimestampWithZone(null)).toBe(NULL_DISPLAY);
  });

  it('distinguishes genuine zero values from missing values', () => {
    expect(formatMiles(0, 'imperial')).toBe('0 mi');
    expect(formatWind(0, 'imperial')).toBe('0 mph');
    expect(formatRain(0, 'imperial')).toBe('0 in/hr');
    expect(formatSnow(0, 'imperial')).toBe('0 in/hr');
    expect(formatAverageRisk(0)).toBe('0.00');
    expect(formatCoveragePercent(0)).toBe('0%');
  });

  it('formats Imperial and Metric distances, weights, and weather measurements with units', () => {
    expect(formatDistanceFromMeters(160934.4, 'imperial')).toBe('100 mi');
    expect(formatDistanceFromMeters(160934.4, 'metric')).toBe('161 km');

    expect(formatDuration(15480)).toBe('4 hr 18 min');
    expect(formatDuration(2520)).toBe('42 min');
    expect(formatDuration(7200)).toBe('2 hr');

    expect(formatWeightLb(32000, 'imperial')).toBe('32,000 lb');
    expect(formatWeightLb(32000, 'metric')).toBe('14,515 kg');

    expect(formatWind(45, 'imperial')).toBe('45 mph');
    expect(formatWind(45, 'metric')).toBe('72 km/h');

    expect(formatRain(0.25, 'imperial')).toBe('0.25 in/hr');
    expect(formatRain(0.25, 'metric')).toBe('6.4 mm/hr');

    expect(formatSnow(1.2, 'imperial')).toBe('1.2 in/hr');
    expect(formatSnow(1.2, 'metric')).toBe('3.0 cm/hr');
  });

  it('formats timestamps with explicit timezone abbreviation', () => {
    const formatted = formatTimestampWithZone('2026-11-20T14:30:00Z', 'America/New_York');
    expect(formatted).toContain('Nov 20');
    expect(formatted).toContain('9:30 AM');
    expect(formatted).toMatch(/EST|GMT-5/);
  });

  it('builds timezone-offset ISO timestamps for departure_at payload', () => {
    const iso = buildOffsetIsoTimestamp('2026-11-20', '09:30');
    expect(iso).not.toBeNull();
    expect(iso).toMatch(/^2026-11-20T09:30:00[+-]\d{2}:\d{2}$/);
    expect(buildOffsetIsoTimestamp('bad-date', '09:30')).toBeNull();
  });
});
