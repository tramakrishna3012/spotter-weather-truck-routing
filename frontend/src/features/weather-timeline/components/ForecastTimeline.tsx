import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { AlertTriangle, Clock, Pause, Play } from 'lucide-react';
import type { ForecastSliceResponse } from '../../../shared/types/plan';
import {
  formatCoveragePercent,
  formatTimestampWithZone,
} from '../../../shared/utils/format';

export interface ForecastTimelineProps {
  hourOffset: number;
  onHourOffsetChange: (nextHour: number) => void;
  slice: ForecastSliceResponse | null;
  referenceAt?: string | null;
  timeZone?: string | null;
  isFetching?: boolean;
  errorMessage?: string | null;
  disabled?: boolean;
}

const SPARSE_TICKS = [0, 12, 24, 36, 48] as const;

function computeProjectedWallClockIso(
  referenceAt: string | null | undefined,
  hourOffset: number,
): string | null {
  if (!referenceAt) return null;
  const base = new Date(referenceAt);
  if (Number.isNaN(base.getTime())) return null;
  return new Date(base.getTime() + hourOffset * 3600 * 1000).toISOString();
}

function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return false;
  }
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/**
 * 0–48h exploratory corridor forecast scrubber.
 * Explicitly separates wall-clock slider time from trip ETA route ranking.
 * Coalesces slider input via requestAnimationFrame so dragging stays smooth.
 */
export function ForecastTimeline({
  hourOffset,
  onHourOffsetChange,
  slice,
  referenceAt,
  timeZone,
  isFetching = false,
  errorMessage = null,
  disabled = false,
}: ForecastTimelineProps) {
  const sliderId = useId();
  const [isPlaying, setIsPlaying] = useState(false);
  const rafRef = useRef<number | null>(null);
  const pendingHourRef = useRef<number | null>(null);

  const resolvedTz = slice?.timezone ?? timeZone ?? null;
  const validAtIso =
    slice && slice.hour_offset === hourOffset && slice.valid_at
      ? slice.valid_at
      : computeProjectedWallClockIso(slice?.reference_at ?? referenceAt, hourOffset);

  const formattedTime = validAtIso
    ? formatTimestampWithZone(validAtIso, resolvedTz)
    : `+${hourOffset} hr from forecast reference`;

  const ariaValueText = `+${hourOffset} hours (${formattedTime})`;

  const scheduleHourChange = useCallback(
    (nextHour: number) => {
      const clamped = Math.max(0, Math.min(48, Math.round(nextHour)));
      pendingHourRef.current = clamped;
      if (rafRef.current !== null) return;
      rafRef.current = window.requestAnimationFrame(() => {
        rafRef.current = null;
        if (pendingHourRef.current !== null) {
          onHourOffsetChange(pendingHourRef.current);
          pendingHourRef.current = null;
        }
      });
    },
    [onHourOffsetChange],
  );

  useEffect(() => {
    return () => {
      if (rafRef.current !== null) {
        window.cancelAnimationFrame(rafRef.current);
      }
    };
  }, []);

  // Optional user-initiated playback (never auto-plays; respects reduced motion)
  useEffect(() => {
    if (!isPlaying || disabled) return;

    const intervalMs = prefersReducedMotion() ? 1500 : 850;
    const timer = window.setInterval(() => {
      if (hourOffset >= 48) {
        setIsPlaying(false);
        return;
      }
      onHourOffsetChange(hourOffset + 1);
    }, intervalMs);

    return () => window.clearInterval(timer);
  }, [isPlaying, disabled, hourOffset, onHourOffsetChange]);

  const hasCoverageGap =
    Boolean(errorMessage) ||
    (slice !== null &&
      ((slice.coverage_fraction !== null && slice.coverage_fraction < 1) ||
        slice.coverage_complete === false));

  const coverageLabel = errorMessage
    ? 'Forecast unavailable'
    : slice?.coverage_fraction !== null && slice?.coverage_fraction !== undefined
      ? slice.coverage_fraction < 1
        ? `Partial coverage · ${formatCoveragePercent(slice.coverage_fraction)}`
        : `Coverage ${formatCoveragePercent(slice.coverage_fraction)}`
      : null;

  return (
    <section
      aria-label="Corridor forecast timeline"
      className="rounded-[var(--radius-overlay)] border border-[var(--color-border-strong)] bg-[var(--color-surface)]/96 shadow-[var(--shadow-overlay)] px-4 py-3"
    >
      {/* Top Row: Play/Pause, Active Wall-Clock Timestamp, Coverage Pill */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2.5 min-w-0">
          <button
            type="button"
            disabled={disabled}
            onClick={() => {
              if (!isPlaying && hourOffset >= 48) {
                onHourOffsetChange(0);
              }
              setIsPlaying((prev) => !prev);
            }}
            aria-label={isPlaying ? 'Pause forecast playback' : 'Play 48-hour forecast'}
            className="h-9 w-9 inline-flex items-center justify-center rounded-full bg-[var(--color-brand-deep)] text-white hover:bg-[var(--color-brand-deep-hover)] disabled:opacity-45 cursor-pointer shrink-0 transition-colors duration-[var(--duration-feedback)]"
          >
            {isPlaying ? (
              <Pause className="h-4 w-4" aria-hidden="true" />
            ) : (
              <Play className="h-4 w-4 ml-0.5" aria-hidden="true" />
            )}
          </button>

          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <label
                htmlFor={sliderId}
                className="text-[13.5px] font-semibold text-[var(--color-ink)] tabular-nums truncate"
              >
                Forecast for {formattedTime}
              </label>
              <span className="inline-flex items-center px-1.5 py-0.5 rounded-[6px] bg-[var(--color-surface-muted)] text-[11px] font-semibold text-[var(--color-brand-deep)] tabular-nums shrink-0">
                +{hourOffset}h
              </span>
            </div>
            <p className="mt-0.5 text-[11.5px] text-[var(--color-ink-secondary)] m-0 leading-snug">
              Exploratory corridor forecast (wall-clock) — route ranking remains based on
              truck ETA
            </p>
          </div>
        </div>

        {/* Coverage & Fetch Status */}
        <div className="flex items-center gap-2 shrink-0">
          {isFetching ? (
            <span className="inline-flex items-center gap-1 text-[11.5px] text-[var(--color-ink-secondary)]">
              <Clock className="h-3.5 w-3.5" aria-hidden="true" />
              Updating…
            </span>
          ) : null}

          {coverageLabel ? (
            <span
              role={hasCoverageGap ? 'status' : undefined}
              className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11.5px] font-medium border tabular-nums"
              style={
                hasCoverageGap
                  ? {
                      backgroundColor: 'var(--severity-moderate-bg)',
                      borderColor: 'var(--severity-moderate-border)',
                      color: '#784605',
                    }
                  : {
                      backgroundColor: 'var(--color-surface-muted)',
                      borderColor: 'var(--color-border)',
                      color: 'var(--color-ink-secondary)',
                    }
              }
            >
              {hasCoverageGap ? (
                <AlertTriangle className="h-3 w-3 shrink-0" aria-hidden="true" />
              ) : null}
              {coverageLabel}
            </span>
          ) : null}
        </div>
      </div>

      {/* Range Slider + Sparse Ticks */}
      <div className="mt-2">
        <input
          id={sliderId}
          type="range"
          min={0}
          max={48}
          step={1}
          disabled={disabled}
          value={hourOffset}
          aria-label="Forecast hour offset (0 to 48 hours)"
          aria-valuemin={0}
          aria-valuemax={48}
          aria-valuenow={hourOffset}
          aria-valuetext={ariaValueText}
          onChange={(e) => {
            if (isPlaying) setIsPlaying(false);
            scheduleHourChange(Number(e.target.value));
          }}
          className="spotter-slider"
        />

        <div
          aria-hidden="true"
          className="flex items-center justify-between text-[11px] font-medium text-[var(--color-ink-secondary)] tabular-nums px-0.5 -mt-1"
        >
          {SPARSE_TICKS.map((tick) => (
            <span key={tick}>{tick}h</span>
          ))}
        </div>
      </div>

      {errorMessage ? (
        <p
          role="alert"
          className="mt-2 text-[12px] text-[var(--severity-severe)] m-0 leading-snug"
        >
          {errorMessage}
        </p>
      ) : null}
    </section>
  );
}
