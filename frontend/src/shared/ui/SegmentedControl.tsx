import { useId } from 'react';

export interface SegmentedOption<T extends string | number> {
  readonly value: T;
  readonly label: string;
  readonly ariaLabel?: string;
}

export interface SegmentedControlProps<T extends string | number> {
  label: string;
  options: readonly SegmentedOption<T>[];
  value: T;
  onChange: (value: T) => void;
  disabled?: boolean;
  size?: 'sm' | 'md';
  hideLabel?: boolean;
  className?: string;
}

export function SegmentedControl<T extends string | number>({
  label,
  options,
  value,
  onChange,
  disabled = false,
  size = 'md',
  hideLabel = false,
  className = '',
}: SegmentedControlProps<T>) {
  const groupLabelId = useId();

  return (
    <div className={className}>
      <span
        id={groupLabelId}
        className={
          hideLabel
            ? 'sr-only'
            : 'block text-[13px] font-medium text-[var(--color-ink)] mb-1.5'
        }
      >
        {label}
      </span>
      <div
        role="radiogroup"
        aria-labelledby={groupLabelId}
        className={[
          'inline-flex w-full items-center rounded-[var(--radius-control)] bg-[var(--color-surface-muted)] p-1 border border-[var(--color-border)]',
          disabled ? 'opacity-60 pointer-events-none' : '',
        ].join(' ')}
      >
        {options.map((opt) => {
          const isSelected = opt.value === value;
          return (
            <button
              key={String(opt.value)}
              type="button"
              role="radio"
              aria-checked={isSelected}
              aria-label={opt.ariaLabel ?? opt.label}
              disabled={disabled}
              onClick={() => onChange(opt.value)}
              className={[
                'flex-1 inline-flex items-center justify-center font-medium tabular-nums cursor-pointer',
                'transition-[background-color,color,box-shadow] duration-[var(--duration-feedback)] ease-[var(--ease-standard)]',
                size === 'sm' ? 'h-8 px-2.5 text-[12.5px] rounded-[8px]' : 'h-9 px-3 text-[13px] rounded-[9px]',
                isSelected
                  ? 'bg-[var(--color-surface)] text-[var(--color-brand-deep)] shadow-[var(--shadow-subtle)] border border-[var(--color-border)]'
                  : 'bg-transparent text-[var(--color-ink-secondary)] border border-transparent hover:text-[var(--color-ink)]',
              ].join(' ')}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
