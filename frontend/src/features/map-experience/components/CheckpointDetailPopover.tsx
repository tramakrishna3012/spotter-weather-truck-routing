import { useEffect, useRef } from 'react';
import {
  ChevronLeft,
  ChevronRight,
  CloudRain,
  CloudSnow,
  Wind,
  X,
} from 'lucide-react';
import type { Checkpoint, UnitSystem } from '../../../shared/types/plan';
import { SeverityBadge } from '../../../shared/ui';
import {
  formatDistanceFromMeters,
  formatRain,
  formatReasonCode,
  formatSnow,
  formatTimestampWithZone,
  formatWind,
} from '../../../shared/utils/format';

export interface CheckpointDetailPopoverProps {
  checkpoint: Checkpoint;
  checkpointIndex: number;
  totalCheckpoints: number;
  units: UnitSystem;
  timeZone?: string | null;
  onClose: () => void;
  onSelectPrevious: () => void;
  onSelectNext: () => void;
}

/**
 * Crisp level-2 floating detail overlay for an inspected route checkpoint.
 * Supports keyboard navigation (Escape to close, Previous/Next checkpoint)
 * and restores focus predictably on close.
 */
export function CheckpointDetailPopover({
  checkpoint,
  checkpointIndex,
  totalCheckpoints,
  units,
  timeZone,
  onClose,
  onSelectPrevious,
  onSelectNext,
}: CheckpointDetailPopoverProps) {
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    previousFocusRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeButtonRef.current?.focus();

    return () => {
      previousFocusRef.current?.focus();
    };
  }, []);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const hasPrev = checkpointIndex > 0;
  const hasNext = checkpointIndex < totalCheckpoints - 1;

  return (
    <section
      role="dialog"
      aria-label={`Checkpoint ${checkpointIndex + 1} weather detail`}
      className="spotter-panel-enter w-[312px] max-w-[calc(100vw-24px)] rounded-[var(--radius-overlay)] border border-[var(--color-border-strong)] bg-[var(--color-surface)] shadow-[var(--shadow-overlay)] overflow-hidden"
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2 px-4 pt-3.5 pb-2.5 border-b border-[var(--color-border)]">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-[14.5px] font-semibold text-[var(--color-ink)] m-0 tabular-nums">
              Checkpoint {checkpointIndex + 1} of {totalCheckpoints}
            </h3>
          </div>
          <p className="mt-0.5 text-[12.5px] text-[var(--color-ink-secondary)] tabular-nums m-0">
            {formatDistanceFromMeters(checkpoint.cumulative_distance_m, units)} from origin
          </p>
        </div>

        <button
          ref={closeButtonRef}
          type="button"
          onClick={onClose}
          aria-label="Close checkpoint details"
          className="h-8 w-8 inline-flex items-center justify-center rounded-[9px] text-[var(--color-ink-secondary)] hover:text-[var(--color-ink)] hover:bg-[var(--color-surface-muted)] cursor-pointer shrink-0"
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>

      {/* Body */}
      <div className="p-4 space-y-3">
        <div className="flex items-center justify-between gap-2">
          <div>
            <div className="text-[11px] font-medium uppercase tracking-[0.04em] text-[var(--color-ink-secondary)]">
              Estimated arrival (ETA)
            </div>
            <div className="text-[13.5px] font-semibold text-[var(--color-ink)] tabular-nums mt-0.5">
              {formatTimestampWithZone(checkpoint.eta_at, timeZone)}
            </div>
          </div>
          <SeverityBadge severity={checkpoint.risk_severity} />
        </div>

        {/* Weather Measurements */}
        <div className="grid grid-cols-3 gap-2">
          <div className="rounded-[11px] bg-[var(--color-canvas)] border border-[var(--color-border)] px-2.5 py-2">
            <div className="flex items-center gap-1 text-[11px] text-[var(--color-ink-secondary)]">
              <Wind className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              <span>Wind</span>
            </div>
            <div className="mt-1 text-[13.5px] font-semibold text-[var(--color-ink)] tabular-nums">
              {formatWind(checkpoint.wind_mph, units)}
            </div>
          </div>

          <div className="rounded-[11px] bg-[var(--color-canvas)] border border-[var(--color-border)] px-2.5 py-2">
            <div className="flex items-center gap-1 text-[11px] text-[var(--color-ink-secondary)]">
              <CloudRain className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              <span>Rain</span>
            </div>
            <div className="mt-1 text-[13.5px] font-semibold text-[var(--color-ink)] tabular-nums">
              {formatRain(checkpoint.rain_in_per_hr, units)}
            </div>
          </div>

          <div className="rounded-[11px] bg-[var(--color-canvas)] border border-[var(--color-border)] px-2.5 py-2">
            <div className="flex items-center gap-1 text-[11px] text-[var(--color-ink-secondary)]">
              <CloudSnow className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              <span>Snow</span>
            </div>
            <div className="mt-1 text-[13.5px] font-semibold text-[var(--color-ink)] tabular-nums">
              {formatSnow(checkpoint.snow_in_per_hr, units)}
            </div>
          </div>
        </div>

        {/* Coverage Caveat */}
        {checkpoint.weather_status === 'unknown' ? (
          <div
            className="rounded-[10px] border px-2.5 py-2 text-[12px] leading-snug"
            style={{
              backgroundColor: 'var(--severity-unknown-bg)',
              borderColor: 'var(--severity-unknown-border)',
              color: 'var(--severity-unknown)',
            }}
          >
            Forecast data is unavailable for this checkpoint at the projected arrival time.
          </div>
        ) : null}

        {/* Backend Risk & Load Override Reasons */}
        {checkpoint.risk_reasons.length > 0 ? (
          <div>
            <div className="text-[11px] font-medium uppercase tracking-[0.04em] text-[var(--color-ink-secondary)] mb-1.5">
              Classification factors
            </div>
            <ul className="m-0 p-0 list-none flex flex-wrap gap-1.5">
              {checkpoint.risk_reasons.map((reason) => (
                <li
                  key={reason}
                  className="rounded-[7px] bg-[var(--color-surface-muted)] border border-[var(--color-border)] px-2 py-0.5 text-[11.5px] text-[var(--color-ink)]"
                >
                  {formatReasonCode(reason)}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {/* Timestamps */}
        <div className="pt-2 border-t border-[var(--color-border)] text-[11.5px] text-[var(--color-ink-secondary)] space-y-1 tabular-nums">
          {checkpoint.weather_valid_at ? (
            <div className="flex items-center justify-between gap-2">
              <span>Forecast valid</span>
              <span>{formatTimestampWithZone(checkpoint.weather_valid_at, timeZone)}</span>
            </div>
          ) : null}
          {checkpoint.forecast_issued_at ? (
            <div className="flex items-center justify-between gap-2">
              <span>Forecast issued</span>
              <span>{formatTimestampWithZone(checkpoint.forecast_issued_at, timeZone)}</span>
            </div>
          ) : null}
        </div>
      </div>

      {/* Prev / Next Navigation Footer */}
      <div className="flex items-center justify-between gap-2 px-3 py-2.5 bg-[var(--color-canvas)] border-t border-[var(--color-border)]">
        <button
          type="button"
          disabled={!hasPrev}
          onClick={onSelectPrevious}
          className="inline-flex items-center gap-1 h-8 px-2.5 rounded-[8px] text-[12.5px] font-medium text-[var(--color-ink)] hover:bg-[var(--color-surface-muted)] disabled:opacity-40 disabled:pointer-events-none cursor-pointer"
        >
          <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          Previous
        </button>
        <button
          type="button"
          disabled={!hasNext}
          onClick={onSelectNext}
          className="inline-flex items-center gap-1 h-8 px-2.5 rounded-[8px] text-[12.5px] font-medium text-[var(--color-ink)] hover:bg-[var(--color-surface-muted)] disabled:opacity-40 disabled:pointer-events-none cursor-pointer"
        >
          Next
          <ChevronRight className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    </section>
  );
}
