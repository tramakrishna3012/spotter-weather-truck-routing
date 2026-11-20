import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  fullWidth?: boolean;
  iconLeft?: ReactNode;
  iconRight?: ReactNode;
}

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary:
    'bg-[var(--color-brand-deep)] text-white hover:bg-[var(--color-brand-deep-hover)] border border-transparent shadow-[var(--shadow-subtle)] hover:-translate-y-px active:translate-y-0',
  secondary:
    'bg-[var(--color-surface)] text-[var(--color-ink)] border border-[var(--color-border-strong)] hover:bg-[var(--color-surface-hover)] shadow-[var(--shadow-subtle)]',
  ghost:
    'bg-transparent text-[var(--color-ink-secondary)] border border-transparent hover:bg-[var(--color-surface-muted)] hover:text-[var(--color-ink)]',
  danger:
    'bg-[var(--severity-no-travel-bg)] text-[var(--severity-no-travel)] border border-[var(--severity-no-travel-border)] hover:bg-[#f4d8df]',
};

const SIZE_CLASSES: Record<ButtonSize, string> = {
  sm: 'h-9 px-3 text-[13px] gap-1.5 rounded-[10px]',
  md: 'h-11 px-4 text-[14px] gap-2 rounded-[var(--radius-control)]',
  lg: 'h-12 px-5 text-[15px] gap-2 rounded-[var(--radius-control)]',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = 'primary',
    size = 'md',
    fullWidth = false,
    iconLeft,
    iconRight,
    className = '',
    type = 'button',
    disabled,
    children,
    ...rest
  },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled}
      className={[
        'inline-flex items-center justify-center font-medium select-none cursor-pointer',
        'transition-[background-color,border-color,color,box-shadow,transform] duration-[var(--duration-feedback)] ease-[var(--ease-standard)]',
        'disabled:opacity-50 disabled:pointer-events-none disabled:cursor-not-allowed',
        VARIANT_CLASSES[variant],
        SIZE_CLASSES[size],
        fullWidth ? 'w-full' : '',
        className,
      ]
        .filter(Boolean)
        .join(' ')}
      {...rest}
    >
      {iconLeft ? <span className="shrink-0 inline-flex">{iconLeft}</span> : null}
      <span>{children}</span>
      {iconRight ? <span className="shrink-0 inline-flex">{iconRight}</span> : null}
    </button>
  );
});
