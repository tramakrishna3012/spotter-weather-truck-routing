import { useEffect, useRef } from 'react';
import { X } from 'lucide-react';
import { ENV } from '../../shared/config/env';
import { SeverityBadge } from '../../shared/ui';

export interface HelpPolicyModalProps {
  open: boolean;
  onClose: () => void;
  policyVersion?: string | null;
}

export function HelpPolicyModal({ open, onClose, policyVersion }: HelpPolicyModalProps) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const prev = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeRef.current?.focus();

    function handleKey(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
      }
    }

    window.addEventListener('keydown', handleKey);
    return () => {
      window.removeEventListener('keydown', handleKey);
      prev?.focus();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[var(--z-modal)] flex items-center justify-center p-4 bg-[#07282C]/40"
      role="presentation"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="policy-modal-title"
        className="spotter-panel-enter w-full max-w-xl max-h-[88vh] flex flex-col rounded-[var(--radius-overlay)] border border-[var(--color-border-strong)] bg-[var(--color-surface)] shadow-[var(--shadow-overlay)] overflow-hidden"
      >
        <div className="flex items-center justify-between gap-3 px-5 py-4 border-b border-[var(--color-border)]">
          <div>
            <h2
              id="policy-modal-title"
              className="text-[17px] font-semibold text-[var(--color-ink)] m-0"
            >
              Weather Risk Policy &amp; Forecast Notes
            </h2>
            {policyVersion ? (
              <p className="mt-0.5 text-[12px] text-[var(--color-ink-secondary)] font-mono m-0">
                Active backend policy: {policyVersion}
              </p>
            ) : null}
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            aria-label="Close policy dialog"
            className="h-9 w-9 inline-flex items-center justify-center rounded-[10px] text-[var(--color-ink-secondary)] hover:text-[var(--color-ink)] hover:bg-[var(--color-surface-muted)] cursor-pointer"
          >
            <X className="h-4.5 w-4.5" aria-hidden="true" />
          </button>
        </div>

        <div className="p-5 overflow-y-auto spotter-scroll space-y-5 text-[13.5px] leading-relaxed text-[var(--color-ink)]">
          {/* Classification Reference Table */}
          <div>
            <h3 className="text-[13px] font-semibold uppercase tracking-[0.04em] text-[var(--color-ink-secondary)] m-0 mb-2.5">
              Backend weather severity reference
            </h3>
            <div className="overflow-x-auto rounded-[12px] border border-[var(--color-border)]">
              <table className="w-full border-collapse text-left text-[12.5px] tabular-nums">
                <thead>
                  <tr className="bg-[var(--color-surface-muted)] text-[var(--color-ink-secondary)]">
                    <th className="py-2 px-3 font-semibold">Condition</th>
                    <th className="py-2 px-2.5 font-semibold">Low</th>
                    <th className="py-2 px-2.5 font-semibold">Moderate</th>
                    <th className="py-2 px-2.5 font-semibold">High</th>
                    <th className="py-2 px-2.5 font-semibold">Severe</th>
                    <th className="py-2 px-2.5 font-semibold">No Travel</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--color-border)]">
                  <tr>
                    <td className="py-2 px-3 font-medium">Wind (mph)</td>
                    <td className="py-2 px-2.5">&lt;25</td>
                    <td className="py-2 px-2.5">25–34</td>
                    <td className="py-2 px-2.5">35–44</td>
                    <td className="py-2 px-2.5">45–54</td>
                    <td className="py-2 px-2.5 font-semibold">&ge;55</td>
                  </tr>
                  <tr>
                    <td className="py-2 px-3 font-medium">Rain (in/hr)</td>
                    <td className="py-2 px-2.5">&lt;0.10</td>
                    <td className="py-2 px-2.5">0.10–0.25</td>
                    <td className="py-2 px-2.5">0.25–0.50</td>
                    <td className="py-2 px-2.5">0.50–1.00</td>
                    <td className="py-2 px-2.5 font-semibold">&gt;1.00</td>
                  </tr>
                  <tr>
                    <td className="py-2 px-3 font-medium">Snow (in/hr)</td>
                    <td className="py-2 px-2.5">&lt;0.5</td>
                    <td className="py-2 px-2.5">0.5–1.0</td>
                    <td className="py-2 px-2.5">1.0–2.0</td>
                    <td className="py-2 px-2.5">2.0–3.0</td>
                    <td className="py-2 px-2.5 font-semibold">&gt;3.0</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Load-Weight Wind Overrides */}
          <div className="space-y-2">
            <h3 className="text-[13px] font-semibold uppercase tracking-[0.04em] text-[var(--color-ink-secondary)] m-0">
              Load-weight wind overrides (backend enforced)
            </h3>
            <ul className="m-0 pl-5 space-y-1 text-[13px] text-[var(--color-ink)]">
              <li>
                Wind <strong>&ge;55 mph</strong> is classified as{' '}
                <SeverityBadge severity="no_travel" compact /> at any load weight.
              </li>
              <li>
                Wind <strong>45–54 mph</strong> with load <strong>&gt;30,000 lb</strong> is
                elevated to <SeverityBadge severity="no_travel" compact />.
              </li>
              <li>
                Wind <strong>35–44 mph</strong> with load <strong>&gt;40,000 lb</strong> is
                elevated to <SeverityBadge severity="severe" compact />.
              </li>
            </ul>
          </div>

          {/* Recommendation Order */}
          <div className="space-y-1.5">
            <h3 className="text-[13px] font-semibold uppercase tracking-[0.04em] text-[var(--color-ink-secondary)] m-0">
              Route ranking order
            </h3>
            <p className="m-0 text-[13px] text-[var(--color-ink)]">
              Among fully covered eligible corridors without No Travel segments, the backend
              ranks routes by:{' '}
              <strong>
                1) fewest Severe miles &rarr; 2) fewest High risk miles &rarr; 3) lowest
                weighted average risk &rarr; 4) shortest travel time
              </strong>
              . Changing the 0–48h corridor forecast slider explores wall-clock conditions
              without changing the trip ETA recommendation.
            </p>
          </div>

          {/* Forecast Disclaimer & Basemap Transparency */}
          <div className="rounded-[12px] bg-[var(--color-surface-muted)] border border-[var(--color-border)] p-3.5 text-[12.5px] text-[var(--color-ink-secondary)] space-y-1.5">
            <p className="m-0 font-medium text-[var(--color-ink)]">
              Operational disclaimer
            </p>
            <p className="m-0">
              Forecast data reflects modeled weather estimates and may not capture sudden
              localized squalls, road closures, bridge restrictions, or black ice.
              Recommendations indicate lower forecast risk among available options and never
              guarantee road safety.
            </p>
            {ENV.mapBasemapNotice ? (
              <p className="m-0 pt-1 text-[11.5px]">{ENV.mapBasemapNotice}</p>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
