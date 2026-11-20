import { useRef, type PointerEvent, type ReactNode } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';

export type SheetSnap = 'peek' | 'half' | 'expanded';

export interface MobileBottomSheetProps {
  snap: SheetSnap;
  onSnapChange: (snap: SheetSnap) => void;
  summaryTitle: string;
  summarySubtitle?: string | null;
  children: ReactNode;
}

const SNAP_HEIGHTS: Record<SheetSnap, string> = {
  peek: '132px',
  half: '48vh',
  expanded: '82vh',
};

/**
 * Three-position mobile bottom sheet (peek / half / expanded).
 * Supports touch/pointer drag gestures AND accessible keyboard/button steppers.
 */
export function MobileBottomSheet({
  snap,
  onSnapChange,
  summaryTitle,
  summarySubtitle,
  children,
}: MobileBottomSheetProps) {
  const dragStartYRef = useRef<number | null>(null);

  function handlePointerDown(event: PointerEvent<HTMLDivElement>) {
    dragStartYRef.current = event.clientY;
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function handlePointerUp(event: PointerEvent<HTMLDivElement>) {
    if (dragStartYRef.current === null) return;
    const deltaY = event.clientY - dragStartYRef.current;
    dragStartYRef.current = null;

    if (deltaY < -36) {
      // Swiped up
      if (snap === 'peek') onSnapChange('half');
      else if (snap === 'half') onSnapChange('expanded');
    } else if (deltaY > 36) {
      // Swiped down
      if (snap === 'expanded') onSnapChange('half');
      else if (snap === 'half') onSnapChange('peek');
    }
  }

  function stepUp() {
    if (snap === 'peek') onSnapChange('half');
    else if (snap === 'half') onSnapChange('expanded');
  }

  function stepDown() {
    if (snap === 'expanded') onSnapChange('half');
    else if (snap === 'half') onSnapChange('peek');
  }

  return (
    <section
      aria-label="Route comparison sheet"
      className="md:hidden fixed left-0 right-0 bottom-0 z-[var(--z-sheet)] flex flex-col rounded-t-[20px] border-t border-[var(--color-border-strong)] bg-[var(--color-surface)] shadow-[var(--shadow-overlay)] transition-[height] duration-[var(--duration-panel)] ease-[var(--ease-standard)]"
      style={{ height: SNAP_HEIGHTS[snap] }}
    >
      {/* Drag Handle & Accessible Step Controls */}
      <div
        onPointerDown={handlePointerDown}
        onPointerUp={handlePointerUp}
        className="shrink-0 pt-2.5 pb-2 px-4 border-b border-[var(--color-border)] touch-none select-none"
      >
        <div
          aria-hidden="true"
          className="mx-auto mb-2 h-1 w-10 rounded-full bg-[var(--color-border-strong)]"
        />
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0">
            <div className="text-[14px] font-semibold text-[var(--color-ink)] truncate">
              {summaryTitle}
            </div>
            {summarySubtitle ? (
              <div className="text-[12px] text-[var(--color-ink-secondary)] truncate">
                {summarySubtitle}
              </div>
            ) : null}
          </div>

          <div className="flex items-center gap-1 shrink-0">
            <button
              type="button"
              disabled={snap === 'peek'}
              onClick={stepDown}
              aria-label="Collapse route panel"
              className="h-9 w-9 inline-flex items-center justify-center rounded-[10px] border border-[var(--color-border)] text-[var(--color-ink)] hover:bg-[var(--color-surface-muted)] disabled:opacity-35 cursor-pointer"
            >
              <ChevronDown className="h-4 w-4" aria-hidden="true" />
            </button>
            <button
              type="button"
              disabled={snap === 'expanded'}
              onClick={stepUp}
              aria-label="Expand route panel"
              className="h-9 w-9 inline-flex items-center justify-center rounded-[10px] border border-[var(--color-border)] text-[var(--color-ink)] hover:bg-[var(--color-surface-muted)] disabled:opacity-35 cursor-pointer"
            >
              <ChevronUp className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </div>
      </div>

      {/* Scrollable Sheet Content */}
      <div className="flex-1 overflow-y-auto spotter-scroll px-4 py-3.5 pb-6">
        {children}
      </div>
    </section>
  );
}
