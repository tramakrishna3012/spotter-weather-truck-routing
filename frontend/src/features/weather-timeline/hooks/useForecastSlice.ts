import { useEffect } from 'react';
import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query';
import { getForecastSlice } from '../../../shared/api/client';
import type { ForecastSliceResponse } from '../../../shared/types/plan';

export function forecastSliceQueryKey(planId: string | null, hourOffset: number) {
  return ['forecast-slice', planId, hourOffset] as const;
}

export interface UseForecastSliceOptions {
  planId: string | null;
  hourOffset: number;
  enabled: boolean;
}

export function useForecastSlice({ planId, hourOffset, enabled }: UseForecastSliceOptions) {
  const queryClient = useQueryClient();
  const clampedHour = Math.max(0, Math.min(48, Math.round(hourOffset)));

  const query = useQuery<ForecastSliceResponse, Error>({
    queryKey: forecastSliceQueryKey(planId, clampedHour),
    queryFn: ({ signal }) => {
      if (!planId) {
        throw new Error('Plan ID is required to fetch forecast slice.');
      }
      return getForecastSlice(planId, clampedHour, signal);
    },
    enabled: Boolean(planId) && enabled,
    placeholderData: keepPreviousData,
    staleTime: 5 * 60 * 1000,
    gcTime: 15 * 60 * 1000,
    retry: 1,
  });

  // Smartly prefetch adjacent hours in background so scrubbing feels instantaneous
  useEffect(() => {
    if (!planId || !enabled) return;

    const candidates = [clampedHour + 1, clampedHour + 3, clampedHour - 1].filter(
      (h) => h >= 0 && h <= 48 && h !== clampedHour,
    );

    const timer = window.setTimeout(() => {
      for (const nextHour of candidates) {
        void queryClient.prefetchQuery({
          queryKey: forecastSliceQueryKey(planId, nextHour),
          queryFn: ({ signal }) => getForecastSlice(planId, nextHour, signal),
          staleTime: 5 * 60 * 1000,
        });
      }
    }, 180);

    return () => window.clearTimeout(timer);
  }, [planId, clampedHour, enabled, queryClient]);

  return query;
}
