import { HelpCircle, SlidersHorizontal } from 'lucide-react';
import type { DataMode, UnitSystem } from '../../shared/types/plan';

export interface TopBarProps {
  dataMode: DataMode | null;
  units: UnitSystem;
  onUnitsChange: (units: UnitSystem) => void;
  onOpenHelp: () => void;
  onOpenMobileTripDrawer: () => void;
}

/**
 * Slim, quiet operational header with original Spotter geometric mark,
 * honest fixture/live data indicator, display units toggle, and Policy help trigger.
 */
export function TopBar({
  dataMode,
  units,
  onUnitsChange,
  onOpenHelp,
  onOpenMobileTripDrawer,
}: TopBarProps) {
  return (
    <header className="h-[var(--topbar-height)] shrink-0 bg-[var(--color-surface)] border-b border-[var(--color-border)] px-4 flex items-center justify-between gap-3 z-[var(--z-topbar)]">
      {/* Left: Spotter Geometric Mark + Descriptor */}
      <div className="flex items-center gap-3 min-w-0">
        <div className="flex items-center gap-2.5 shrink-0">
          {/* Original Spotter geometric SVG mark: deep teal anchor + corridor accent dots */}
          <svg
            width="28"
            height="28"
            viewBox="0 0 28 28"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            aria-hidden="true"
            className="shrink-0"
          >
            <rect width="28" height="28" rx="8" fill="#073D45" />
            <path
              d="M7.5 18.5C9.5 13 13.5 10.5 20.5 9.5"
              stroke="#FFFFFF"
              strokeWidth="2.1"
              strokeLinecap="round"
            />
            <circle cx="7.5" cy="18.5" r="2.2" fill="#6FD1C6" />
            <circle cx="14.2" cy="12.6" r="1.7" fill="#FFFFFF" />
            <circle cx="20.5" cy="9.5" r="2.2" fill="#F2B84B" />
          </svg>
          <span className="text-[16px] font-semibold tracking-[-0.02em] text-[var(--color-brand-deep)]">
            Spotter
          </span>
        </div>

        <span
          aria-hidden="true"
          className="hidden sm:inline-block h-4 w-px bg-[var(--color-border-strong)]"
        />
        <span className="hidden sm:inline text-[13px] text-[var(--color-ink-secondary)] truncate">
          Weather-aware routing
        </span>

        {/* Unmistakable Fixture Mode Indicator — never disguises sample data as live */}
        {dataMode === 'fixture' ? (
          <span
            role="status"
            className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11.5px] font-semibold border whitespace-nowrap"
            style={{
              backgroundColor: 'var(--severity-moderate-bg)',
              borderColor: 'var(--severity-moderate-border)',
              color: '#784605',
            }}
          >
            <span
              aria-hidden="true"
              className="h-1.5 w-1.5 rounded-full bg-[var(--severity-moderate)]"
            />
            Sample data (Fixture mode)
          </span>
        ) : dataMode === 'live' ? (
          <span className="hidden md:inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11.5px] font-medium border border-[var(--color-border)] bg-[var(--color-surface-muted)] text-[var(--color-ink-secondary)] whitespace-nowrap">
            <span
              aria-hidden="true"
              className="h-1.5 w-1.5 rounded-full bg-[var(--severity-low)]"
            />
            Live forecast
          </span>
        ) : null}
      </div>

      {/* Right: Utilitarian Controls */}
      <div className="flex items-center gap-2 shrink-0">
        {/* Mobile Trip Drawer Trigger */}
        <button
          type="button"
          onClick={onOpenMobileTripDrawer}
          className="md:hidden inline-flex items-center gap-1.5 h-9 px-3 rounded-[10px] bg-[var(--color-brand-deep)] text-white text-[13px] font-medium cursor-pointer"
        >
          <SlidersHorizontal className="h-3.5 w-3.5" aria-hidden="true" />
          <span>Trip</span>
        </button>

        {/* Units Toggle (Imperial / Metric display) */}
        <div
          role="group"
          aria-label="Display units"
          className="hidden sm:inline-flex items-center rounded-[10px] bg-[var(--color-surface-muted)] p-0.5 border border-[var(--color-border)]"
        >
          <button
            type="button"
            aria-pressed={units === 'imperial'}
            onClick={() => onUnitsChange('imperial')}
            className={[
              'h-7 px-2.5 rounded-[8px] text-[12px] font-medium cursor-pointer transition-colors duration-[var(--duration-feedback)]',
              units === 'imperial'
                ? 'bg-[var(--color-surface)] text-[var(--color-brand-deep)] shadow-[var(--shadow-subtle)]'
                : 'text-[var(--color-ink-secondary)] hover:text-[var(--color-ink)]',
            ].join(' ')}
          >
            Imperial
          </button>
          <button
            type="button"
            aria-pressed={units === 'metric'}
            onClick={() => onUnitsChange('metric')}
            className={[
              'h-7 px-2.5 rounded-[8px] text-[12px] font-medium cursor-pointer transition-colors duration-[var(--duration-feedback)]',
              units === 'metric'
                ? 'bg-[var(--color-surface)] text-[var(--color-brand-deep)] shadow-[var(--shadow-subtle)]'
                : 'text-[var(--color-ink-secondary)] hover:text-[var(--color-ink)]',
            ].join(' ')}
          >
            Metric
          </button>
        </div>

        {/* Help / Policy Modal Trigger */}
        <button
          type="button"
          onClick={onOpenHelp}
          aria-label="Risk policy and help"
          className="inline-flex items-center gap-1.5 h-9 px-2.5 rounded-[10px] border border-[var(--color-border)] bg-[var(--color-surface)] text-[13px] font-medium text-[var(--color-ink-secondary)] hover:text-[var(--color-ink)] hover:bg-[var(--color-surface-hover)] cursor-pointer transition-colors duration-[var(--duration-feedback)]"
        >
          <HelpCircle className="h-4 w-4" aria-hidden="true" />
          <span className="hidden sm:inline">Policy</span>
        </button>
      </div>
    </header>
  );
}
