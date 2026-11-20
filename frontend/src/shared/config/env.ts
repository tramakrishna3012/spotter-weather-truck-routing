export type DisplaySpacingMiles = 10 | 25 | 50;

export const SUPPORTED_DISPLAY_SPACINGS: readonly DisplaySpacingMiles[] = [10, 25, 50] as const;

export const DEFAULT_DISPLAY_SPACING: DisplaySpacingMiles = 25;

/**
 * Fallback public vector basemap style used ONLY in local dev when
 * VITE_MAP_STYLE_URL is not configured. Never claims a licensed provider key exists.
 */
const PUBLIC_FALLBACK_MAP_STYLE_URL = 'https://tiles.openfreemap.org/styles/positron';

export interface AppEnvConfig {
  readonly apiBaseUrl: string;
  readonly mapStyleUrl: string;
  readonly mapPublicToken: string;
  readonly mapBasemapSource: 'configured' | 'public_fallback';
  readonly mapBasemapNotice: string | null;
}

function readEnvString(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

export function getEnvConfig(): AppEnvConfig {
  const apiBaseUrl = readEnvString(import.meta.env.VITE_API_BASE_URL).replace(/\/+$/, '');
  const configuredStyleUrl = readEnvString(import.meta.env.VITE_MAP_STYLE_URL);
  const mapPublicToken = readEnvString(import.meta.env.VITE_MAP_PUBLIC_TOKEN);

  if (configuredStyleUrl.length > 0) {
    return {
      apiBaseUrl,
      mapStyleUrl: configuredStyleUrl,
      mapPublicToken,
      mapBasemapSource: 'configured',
      mapBasemapNotice: null,
    };
  }

  return {
    apiBaseUrl,
    mapStyleUrl: PUBLIC_FALLBACK_MAP_STYLE_URL,
    mapPublicToken: '',
    mapBasemapSource: 'public_fallback',
    mapBasemapNotice: 'Using public OpenFreeMap Positron basemap (no VITE_MAP_STYLE_URL configured).',
  };
}

export const ENV = getEnvConfig();
