import { CloudRain, CloudSnow, Wind } from 'lucide-react';
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

export interface CheckpointListPanelProps {
  checkpoints: readonly Checkpoint[];
  selectedCheckpointId: string | null;
  onSelectCheckpoint: (checkpointId: string) => void;
  units: UnitSystem;
  timeZone?: string | null;
  routeLabel: string;
}

/**
 * Accessible ordered list of route checkpoints along the selected route.
 * Ensures the interactive map is NEVER the sole medium for essential weather safety data.
 */
export function CheckpointListPanel({
  checkpoints,
  selectedCheckpointId,
  onSelectCheckpoint,
  units,
  timeZone,
  routeLabel,
}: CheckpointListPanelProps) {
  if (checkpoints.length === 0) {
    return (
      <div className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-4 text-[13px] text-[var(--color-ink-secondary)]">
        No checkpoints were returned for {routeLabel}.
      </div>
    );
  }

  return (
    <div aria-label={`Weather checkpoints along ${routeLabel}`}>
      <div className="flex items-center justify-between mb-2 px-0.5">
        <span className="text-[12px] font-medium text-[var(--color-ink-secondary)]">
          Arrival ETA conditions ({checkpoints.length} checkpoints)
        </span>
      </div>
      <ol className="m-0 p-0 list-none space-y-2">
        {checkpoints.map((cp, idx) => {
          const isSelected = cp.id === selectedCheckpointId;
          const distText = formatDistanceFromMeters(cp.cumulative_distance_m, units);
          const etaText = formatTimestampWithZone(cp.eta_at, timeZone);

          return (
            <li key={cp.id}>
              <button
                type="button"
                aria-pressed={isSelected}
                onClick={() => onSelectCheckpoint(cp.id)}
                className={[
                  'w-full text-left rounded-[13px] p-3 cursor-pointer',
                  'transition-[border-color,background-color,box-shadow] duration-[var(--duration-feedback)] ease-[var(--ease-standard)]',
                  isSelected
                    ? 'bg-[var(--color-brand-tint)]/55 border-2 border-[var(--color-brand-action)] shadow-[var(--shadow-subtle)]'
                    : 'bg-[var(--color-surface)] border border-[var(--color-border)] hover:border-[var(--color-border-strong)] hover:bg-[var(--color-surface-hover)]',
                ].join(' ')}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <span className="text-[13.5px] font-semibold text-[var(--color-ink)] tabular-nums">
                      #{idx + 1} · {distText}
                    </span>
                    <div className="text-[12px] text-[var(--color-ink-secondary)] tabular-nums mt-0.5">
                      ETA {etaText}
                    </div>
                  </div>
                  <SeverityBadge severity={cp.risk_severity} compact />
                </div>

                {/* Weather metrics with explicit units; null never coerced to 0 */}
                <div className="mt-2.5 grid grid-cols-3 gap-1.5 text-[12px] tabular-nums">
                  <div className="flex items-center gap-1 text-[var(--color-ink)]">
                    <Wind
                      className="h-3.5 w-3.5 text-[var(--color-ink-secondary)] shrink-0"
                      aria-hidden="true"
                    />
                    <span className="sr-only">Wind:</span>
                    <span>{formatWind(cp.wind_mph, units)}</span>
                  </div>
                  <div className="flex items-center gap-1 text-[var(--color-ink)]">
                    <CloudRain
                      className="h-3.5 w-3.5 text-[var(--color-ink-secondary)] shrink-0"
                      aria-hidden="true"
                    />
                    <span className="sr-only">Rain:</span>
                    <span>{formatRain(cp.rain_in_per_hr, units)}</span>
                  </div>
                  <div className="flex items-center gap-1 text-[var(--color-ink)]">
                    <CloudSnow
                      className="h-3.5 w-3.5 text-[var(--color-ink-secondary)] shrink-0"
                      aria-hidden="true"
                    />
                    <span className="sr-only">Snow:</span>
                    <span>{formatSnow(cp.snow_in_per_hr, units)}</span>
                  </div>
                </div>

                {/* Backend risk / load override reasons */}
                {cp.risk_reasons.length > 0 ? (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {cp.risk_reasons.map((reason) => (
                      <span
                        key={reason}
                        className="inline-block rounded-[6px] bg-[var(--color-surface-muted)] px-1.5 py-0.5 text-[11px] text-[var(--color-ink-secondary)]"
                      >
                        {formatReasonCode(reason)}
                      </span>
                    ))}
                  </div>
                ) : null}
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
