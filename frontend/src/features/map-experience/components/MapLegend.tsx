import { useState } from 'react';
import { AlertOctagon, ChevronDown, ChevronUp, Layers } from 'lucide-react';
import { RISK_THEME, SEVERITY_ORDER } from '../../../shared/design-tokens/riskTheme';

export interface MapLegendProps {
  showCorridorOverlay: boolean;
  hasPlan: boolean;
}

/**
 * Compact floating legend clearly separating:
 * 1) Route Risk (evaluated at Truck ETA)
 * 2) Exploratory Corridor Forecast (at Slider Wall-Clock Time)
 */
export function MapLegend({ showCorridorOverlay, hasPlan }: MapLegendProps) {
  const [expanded, setExpanded] = useState(false);

  if (!hasPlan) return null;

  return (
    <aside
      aria-label="Map risk legend"
      className="rounded-[14px] border border-[var(--color-border-strong)] bg-[var(--color-surface)]/95 shadow-[var(--shadow-lifted)] text-[12px] max-w-[238px]"
    >
      <button
        type="button"
        aria-expanded={expanded}
        onClick={() => setExpanded((prev) => !prev)}
        className="w-full flex items-center justify-between gap-2 px-3 py-2 text-left font-medium text-[var(--color-ink)] cursor-pointer rounded-[14px] hover:bg-[var(--color-surface-hover)]"
      >
        <span className="inline-flex items-center gap-1.5">
          <Layers className="h-3.5 w-3.5 text-[var(--color-brand-action)]" aria-hidden="true" />
          <span>Risk legend</span>
        </span>
        {expanded ? (
          <ChevronDown className="h-3.5 w-3.5 text-[var(--color-ink-secondary)]" aria-hidden="true" />
        ) : (
          <ChevronUp className="h-3.5 w-3.5 text-[var(--color-ink-secondary)]" aria-hidden="true" />
        )}
      </button>

      {expanded ? (
        <div className="px-3 pb-3 pt-1.5 border-t border-[var(--color-border)] space-y-2.5">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.04em] text-[var(--color-ink-secondary)] mb-1.5">
              Route segments (at truck ETA)
            </div>
            <ul className="m-0 p-0 list-none space-y-1">
              {SEVERITY_ORDER.map((sev) => {
                const entry = RISK_THEME[sev];
                return (
                  <li key={sev} className="flex items-center gap-2 text-[var(--color-ink)]">
                    {sev === 'no_travel' ? (
                      <AlertOctagon
                        className="h-3.5 w-3.5 shrink-0"
                        style={{ color: entry.color }}
                        aria-hidden="true"
                      />
                    ) : sev === 'unknown' ? (
                      <span
                        aria-hidden="true"
                        className="inline-block w-4 h-0 border-t-2 border-dashed shrink-0"
                        style={{ borderColor: entry.strokeColor }}
                      />
                    ) : (
                      <span
                        aria-hidden="true"
                        className="inline-block w-4 h-1.5 rounded-full shrink-0"
                        style={{ backgroundColor: entry.strokeColor }}
                      />
                    )}
                    <span>{entry.label}</span>
                  </li>
                );
              })}
            </ul>
          </div>

          <div className="pt-2 border-t border-[var(--color-border)]">
            <div className="text-[11px] font-semibold uppercase tracking-[0.04em] text-[var(--color-ink-secondary)] mb-1">
              Corridor overlay (slider time)
            </div>
            <p className="m-0 text-[11.5px] text-[var(--color-ink-secondary)] leading-snug">
              {showCorridorOverlay
                ? 'Translucent weather intensity along corridor at selected wall-clock forecast hour.'
                : 'Corridor weather overlay is currently hidden.'}
            </p>
          </div>
        </div>
      ) : null}
    </aside>
  );
}
