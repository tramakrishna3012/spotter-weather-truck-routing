import type { ReactNode } from 'react';
import { AlertOctagon, AlertTriangle, CloudOff, Info } from 'lucide-react';

export type SafetyNoticeTone = 'no_travel' | 'warning' | 'error' | 'info';

export interface SafetyNoticeProps {
  tone: SafetyNoticeTone;
  title: string;
  body: string;
  detail?: string | null;
  action?: ReactNode;
  className?: string;
}

const TONE_STYLES: Record<
  SafetyNoticeTone,
  {
    bg: string;
    border: string;
    titleColor: string;
    iconColor: string;
    role: 'alert' | 'status';
  }
> = {
  no_travel: {
    bg: 'var(--severity-no-travel-bg)',
    border: 'var(--severity-no-travel-border)',
    titleColor: 'var(--severity-no-travel)',
    iconColor: 'var(--severity-no-travel)',
    role: 'alert',
  },
  warning: {
    bg: 'var(--severity-moderate-bg)',
    border: 'var(--severity-moderate-border)',
    titleColor: '#784605',
    iconColor: 'var(--severity-moderate)',
    role: 'status',
  },
  error: {
    bg: 'var(--severity-severe-bg)',
    border: 'var(--severity-severe-border)',
    titleColor: 'var(--severity-severe)',
    iconColor: 'var(--severity-severe)',
    role: 'alert',
  },
  info: {
    bg: 'var(--color-brand-tint)',
    border: '#C3DFE2',
    titleColor: 'var(--color-brand-deep)',
    iconColor: 'var(--color-brand-action)',
    role: 'status',
  },
};

function renderIcon(tone: SafetyNoticeTone, color: string) {
  const iconProps = {
    className: 'h-4.5 w-4.5 shrink-0 mt-0.5',
    style: { color },
    'aria-hidden': true as const,
  };
  switch (tone) {
    case 'no_travel':
      return <AlertOctagon {...iconProps} />;
    case 'warning':
      return <AlertTriangle {...iconProps} />;
    case 'error':
      return <CloudOff {...iconProps} />;
    case 'info':
      return <Info {...iconProps} />;
  }
}

/**
 * Sober, prominent, non-dismissible safety notice for blocking conditions,
 * partial coverage, stale forecasts, and service errors.
 */
export function SafetyNotice({
  tone,
  title,
  body,
  detail,
  action,
  className = '',
}: SafetyNoticeProps) {
  const style = TONE_STYLES[tone];

  return (
    <div
      role={style.role}
      aria-live={style.role === 'alert' ? 'assertive' : 'polite'}
      className={[
        'rounded-[var(--radius-card)] border p-3.5 text-[13.5px] leading-snug',
        className,
      ]
        .filter(Boolean)
        .join(' ')}
      style={{
        backgroundColor: style.bg,
        borderColor: style.border,
      }}
    >
      <div className="flex items-start gap-2.5">
        {renderIcon(tone, style.iconColor)}
        <div className="min-w-0 flex-1 space-y-1">
          <p
            className="font-semibold text-[13.5px] m-0"
            style={{ color: style.titleColor }}
          >
            {title}
          </p>
          <p className="text-[13px] text-[var(--color-ink)] m-0 leading-relaxed">
            {body}
          </p>
          {detail ? (
            <p className="text-[12px] text-[var(--color-ink-secondary)] m-0 pt-0.5">
              {detail}
            </p>
          ) : null}
          {action ? <div className="pt-2">{action}</div> : null}
        </div>
      </div>
    </div>
  );
}
