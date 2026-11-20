import type { Severity } from '../types/plan';

export interface SeverityThemeEntry {
  readonly severity: Severity;
  readonly label: string;
  readonly shortLabel: string;
  readonly color: string;
  readonly strokeColor: string;
  readonly bgColor: string;
  readonly borderColor: string;
  readonly textColor: string;
  readonly dashArray: readonly number[] | null;
  /** Purely visual heatmap intensity weight derived from backend severity enum (zero threshold logic). */
  readonly heatWeight: number;
  readonly isBlocking: boolean;
  readonly description: string;
}

/**
 * Centralized UI severity mapping.
 * IMPORTANT: Contains ZERO weather threshold calculations.
 * All severity classifications come exclusively from the backend risk policy.
 */
export const RISK_THEME: Readonly<Record<Severity, SeverityThemeEntry>> = {
  low: {
    severity: 'low',
    label: 'Low risk',
    shortLabel: 'Low',
    color: '#1F7A52',
    strokeColor: '#1F7A52',
    bgColor: '#EAF6F0',
    borderColor: '#B9DFC9',
    textColor: '#1F7A52',
    dashArray: null,
    heatWeight: 0.22,
    isBlocking: false,
    description: 'Forecast values within lower risk classification.',
  },
  moderate: {
    severity: 'moderate',
    label: 'Moderate',
    shortLabel: 'Moderate',
    color: '#A16207',
    strokeColor: '#B87208',
    bgColor: '#FEF7E6',
    borderColor: '#EDD59B',
    textColor: '#A16207',
    dashArray: null,
    heatWeight: 0.45,
    isBlocking: false,
    description: 'Elevated weather conditions along this segment.',
  },
  high: {
    severity: 'high',
    label: 'High risk',
    shortLabel: 'High',
    color: '#C2410C',
    strokeColor: '#C2410C',
    bgColor: '#FFF0E8',
    borderColor: '#F2C1A9',
    textColor: '#C2410C',
    dashArray: null,
    heatWeight: 0.72,
    isBlocking: false,
    description: 'Significant wind or precipitation risk classified by backend policy.',
  },
  severe: {
    severity: 'severe',
    label: 'Severe',
    shortLabel: 'Severe',
    color: '#B91C1C',
    strokeColor: '#B91C1C',
    bgColor: '#FDECEC',
    borderColor: '#F0B6B6',
    textColor: '#B91C1C',
    dashArray: null,
    heatWeight: 0.9,
    isBlocking: false,
    description: 'Severe forecast hazard or heavy-load wind override active.',
  },
  no_travel: {
    severity: 'no_travel',
    label: 'No Travel',
    shortLabel: 'No Travel',
    color: '#6B1124',
    strokeColor: '#6B1124',
    bgColor: '#F9E6EA',
    borderColor: '#DEB0BA',
    textColor: '#6B1124',
    dashArray: null,
    heatWeight: 1.0,
    isBlocking: true,
    description: 'Conditions exceed travel threshold under current load policy.',
  },
  unknown: {
    severity: 'unknown',
    label: 'Forecast unavailable',
    shortLabel: 'Unavailable',
    color: '#5C6B73',
    strokeColor: '#5C6B73',
    bgColor: '#EEF2F4',
    borderColor: '#CBD5DA',
    textColor: '#5C6B73',
    dashArray: [2.5, 2],
    heatWeight: 0.14,
    isBlocking: false,
    description: 'Forecast coverage is missing or outside provider horizon.',
  },
} as const;

export const SEVERITY_ORDER: readonly Severity[] = [
  'low',
  'moderate',
  'high',
  'severe',
  'no_travel',
  'unknown',
] as const;

export function getRiskTheme(severity: Severity | null | undefined): SeverityThemeEntry {
  if (!severity || !(severity in RISK_THEME)) {
    return RISK_THEME.unknown;
  }
  return RISK_THEME[severity];
}
