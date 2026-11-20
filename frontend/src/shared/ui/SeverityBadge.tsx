import { AlertOctagon, HelpCircle } from 'lucide-react';
import { getRiskTheme } from '../design-tokens/riskTheme';
import type { Severity } from '../types/plan';

export interface SeverityBadgeProps {
  severity: Severity;
  compact?: boolean;
  className?: string;
}

/**
 * Displays a backend-classified weather severity.
 * ALWAYS pairs text label + non-color indicator (swatch, dashed circle, or AlertOctagon).
 */
export function SeverityBadge({ severity, compact = false, className = '' }: SeverityBadgeProps) {
  const theme = getRiskTheme(severity);
  const label = compact ? theme.shortLabel : theme.label;

  return (
    <span
      className={[
        'inline-flex items-center gap-1.5 rounded-full border font-medium whitespace-nowrap leading-none',
        compact ? 'px-2 py-1 text-[11.5px]' : 'px-2.5 py-1 text-[12px]',
        className,
      ]
        .filter(Boolean)
        .join(' ')}
      style={{
        backgroundColor: theme.bgColor,
        borderColor: theme.borderColor,
        color: theme.textColor,
      }}
    >
      {severity === 'no_travel' ? (
        <AlertOctagon className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      ) : severity === 'unknown' ? (
        <HelpCircle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      ) : (
        <span
          aria-hidden="true"
          className="h-2 w-2 rounded-full shrink-0"
          style={{ backgroundColor: theme.color }}
        />
      )}
      <span>{label}</span>
    </span>
  );
}
