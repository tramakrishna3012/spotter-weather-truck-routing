export interface SkeletonPanelProps {
  stageLabel: string;
  subLabel?: string;
}

/**
 * Quiet geometry-matched skeleton while planning routes and sampling weather.
 * Uses static restrained placeholders rather than distracting shimmer loops.
 */
export function SkeletonPanel({ stageLabel, subLabel }: SkeletonPanelProps) {
  return (
    <div
      className="space-y-3"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <div className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
        <div className="flex items-center gap-2.5">
          <span
            aria-hidden="true"
            className="h-2.5 w-2.5 rounded-full bg-[var(--color-brand-action)] shrink-0"
          />
          <p className="text-[14px] font-medium text-[var(--color-ink)] m-0">
            {stageLabel}
          </p>
        </div>
        {subLabel ? (
          <p className="mt-1.5 pl-5 text-[12.5px] text-[var(--color-ink-secondary)] m-0">
            {subLabel}
          </p>
        ) : null}
      </div>

      {[0, 1, 2].map((index) => (
        <div
          key={index}
          aria-hidden="true"
          className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-4 space-y-3"
        >
          <div className="flex items-center justify-between gap-3">
            <div className="spotter-skeleton h-4 w-32" />
            <div className="spotter-skeleton h-5 w-24 rounded-full" />
          </div>
          <div className="flex items-center gap-4">
            <div className="spotter-skeleton h-6 w-20" />
            <div className="spotter-skeleton h-4 w-16" />
          </div>
          <div className="grid grid-cols-3 gap-2 pt-1">
            <div className="spotter-skeleton h-10" />
            <div className="spotter-skeleton h-10" />
            <div className="spotter-skeleton h-10" />
          </div>
          <div className="spotter-skeleton h-3.5 w-5/6" />
        </div>
      ))}
    </div>
  );
}
