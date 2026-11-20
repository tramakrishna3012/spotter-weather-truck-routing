import { AlertOctagon, Award, CheckCircle2, HelpCircle } from 'lucide-react';
import type { RouteCandidate, UnitSystem } from '../../../shared/types/plan';
import {
  formatAverageRisk,
  formatCoveragePercent,
  formatDistanceFromMeters,
  formatDuration,
  formatMiles,
} from '../../../shared/utils/format';

export interface RouteComparisonCardProps {
  route: RouteCandidate;
  index: number;
  isSelected: boolean;
  isRecommended: boolean;
  recommendationReason?: string | null;
  units: UnitSystem;
  onSelect: (routeId: string) => void;
}

function getRouteDisplayName(route: RouteCandidate, index: number): string {
  if (route.label && route.label.trim().length > 0) {
    return route.label;
  }
  const letter = String.fromCharCode(65 + index);
  return `Route ${letter}`;
}

/**
 * Purely presentational route comparison card.
 * Displays ONLY backend-supplied eligibility, recommendation, and risk metrics.
 * Selected state is visually and semantically distinct from Recommended state.
 */
export function RouteComparisonCard({
  route,
  index,
  isSelected,
  isRecommended,
  recommendationReason,
  units,
  onSelect,
}: RouteComparisonCardProps) {
  const { risk } = route;
  const routeName = getRouteDisplayName(route, index);

  const hasNoTravel =
    (risk.no_travel_miles !== null && risk.no_travel_miles > 0) ||
    route.risk_segments.some((seg) => seg.severity === 'no_travel' || seg.status === 'no_travel') ||
    route.checkpoints.some((cp) => cp.risk_severity === 'no_travel');

  const hasIncompleteCoverage =
    (risk.coverage_fraction !== null && risk.coverage_fraction < 1) ||
    (risk.unknown_miles !== null && risk.unknown_miles > 0);

  const coveragePct =
    risk.coverage_fraction !== null ? Math.max(0, Math.min(100, Math.round(risk.coverage_fraction * 100))) : null;

  const rationale =
    route.rationale ??
    (isRecommended ? recommendationReason : null) ??
    (hasNoTravel
      ? 'Contains No Travel conditions under current load policy.'
      : hasIncompleteCoverage
        ? 'Weather forecast coverage is incomplete along part of this corridor.'
        : risk.eligible
          ? 'Eligible candidate based on available corridor forecast.'
          : 'Not eligible for recommendation under current forecast policy.');

  const statusAnnouncement = isRecommended
    ? 'Recommended based on available forecast'
    : hasNoTravel
      ? 'No Travel conditions detected'
      : hasIncompleteCoverage
        ? 'Incomplete weather coverage'
        : risk.eligible
          ? 'Eligible route'
          : 'Not eligible';

  return (
    <button
      type="button"
      aria-pressed={isSelected}
      aria-label={`${routeName}, ${statusAnnouncement}, ${formatDuration(route.duration_seconds)}, ${formatDistanceFromMeters(route.distance_m, units)}${isSelected ? ', currently selected' : ''}`}
      onClick={() => onSelect(route.id)}
      className={[
        'w-full text-left rounded-[var(--radius-card)] p-4 cursor-pointer',
        'transition-[border-color,background-color,box-shadow] duration-[var(--duration-panel)] ease-[var(--ease-standard)]',
        isSelected
          ? 'bg-[var(--color-surface)] border-2 border-[var(--color-brand-action)] shadow-[var(--shadow-lifted)]'
          : 'bg-[var(--color-surface)] border border-[var(--color-border)] hover:border-[var(--color-border-strong)] hover:bg-[var(--color-surface-hover)]',
      ].join(' ')}
    >
      {/* Priority 1: Route Identifier + Eligibility / Recommendation Badge */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-[16px] font-semibold text-[var(--color-ink)] tracking-[-0.01em] truncate">
              {routeName}
            </span>
            {isSelected ? (
              <span className="inline-flex items-center px-1.5 py-0.5 rounded-[6px] bg-[var(--color-surface-muted)] text-[11px] font-medium text-[var(--color-brand-deep)]">
                Viewing
              </span>
            ) : null}
          </div>
          {route.summary ? (
            <p className="mt-0.5 text-[12.5px] text-[var(--color-ink-secondary)] truncate m-0">
              via {route.summary}
            </p>
          ) : null}
        </div>

        {/* Distinct status badge from backend eligibility */}
        <div className="shrink-0 flex flex-col items-end gap-1">
          {isRecommended ? (
            <span
              className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11.5px] font-semibold border whitespace-nowrap"
              style={{
                backgroundColor: 'var(--color-brand-tint)',
                borderColor: '#B5D7DB',
                color: 'var(--color-brand-deep)',
              }}
            >
              <Award className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              Recommended
            </span>
          ) : hasNoTravel ? (
            <span
              className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11.5px] font-semibold border whitespace-nowrap"
              style={{
                backgroundColor: 'var(--severity-no-travel-bg)',
                borderColor: 'var(--severity-no-travel-border)',
                color: 'var(--severity-no-travel)',
              }}
            >
              <AlertOctagon className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              No Travel
            </span>
          ) : hasIncompleteCoverage ? (
            <span
              className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11.5px] font-medium border whitespace-nowrap"
              style={{
                backgroundColor: 'var(--severity-unknown-bg)',
                borderColor: 'var(--severity-unknown-border)',
                color: 'var(--severity-unknown)',
              }}
            >
              <HelpCircle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              Incomplete coverage
            </span>
          ) : risk.eligible ? (
            <span className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11.5px] font-medium border border-[var(--color-border)] bg-[var(--color-surface-muted)] text-[var(--color-ink-secondary)] whitespace-nowrap">
              <CheckCircle2 className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              Eligible
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11.5px] font-medium border border-[var(--severity-unknown-border)] bg-[var(--severity-unknown-bg)] text-[var(--severity-unknown)] whitespace-nowrap">
              Not eligible
            </span>
          )}
        </div>
      </div>

      {/* Priority 2: Travel Time & Distance */}
      <div className="mt-2.5 flex items-baseline gap-2.5 tabular-nums">
        <span className="text-[21px] font-semibold tracking-[-0.02em] text-[var(--color-ink)]">
          {formatDuration(route.duration_seconds)}
        </span>
        <span className="text-[13.5px] text-[var(--color-ink-secondary)]">
          {formatDistanceFromMeters(route.distance_m, units)}
        </span>
      </div>

      {/* Priority 3: Risk Mileage & Average Risk (static tabular figures, zero count-up animation) */}
      <div className="mt-3 grid grid-cols-3 gap-2">
        <div className="rounded-[10px] bg-[var(--color-canvas)] border border-[var(--color-border)] px-2.5 py-1.5">
          <div className="text-[11px] text-[var(--color-ink-secondary)]">Severe</div>
          <div
            className="text-[13.5px] font-semibold tabular-nums mt-0.5"
            style={{
              color:
                risk.severe_miles !== null && risk.severe_miles > 0
                  ? 'var(--severity-severe)'
                  : 'var(--color-ink)',
            }}
          >
            {formatMiles(risk.severe_miles, units)}
          </div>
        </div>

        <div className="rounded-[10px] bg-[var(--color-canvas)] border border-[var(--color-border)] px-2.5 py-1.5">
          <div className="text-[11px] text-[var(--color-ink-secondary)]">High risk</div>
          <div
            className="text-[13.5px] font-semibold tabular-nums mt-0.5"
            style={{
              color:
                risk.high_miles !== null && risk.high_miles > 0
                  ? 'var(--severity-high)'
                  : 'var(--color-ink)',
            }}
          >
            {formatMiles(risk.high_miles, units)}
          </div>
        </div>

        <div className="rounded-[10px] bg-[var(--color-canvas)] border border-[var(--color-border)] px-2.5 py-1.5">
          <div className="text-[11px] text-[var(--color-ink-secondary)]">Avg risk</div>
          <div className="text-[13.5px] font-semibold tabular-nums text-[var(--color-ink)] mt-0.5">
            {formatAverageRisk(risk.weighted_average_risk)}
          </div>
        </div>
      </div>

      {/* Additional explicit callouts for No Travel or Unknown mileage */}
      {(risk.no_travel_miles !== null && risk.no_travel_miles > 0) ||
      (risk.unknown_miles !== null && risk.unknown_miles > 0) ? (
        <div className="mt-2 flex flex-wrap items-center gap-2 text-[12px] tabular-nums">
          {risk.no_travel_miles !== null && risk.no_travel_miles > 0 ? (
            <span
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-[7px] font-medium"
              style={{
                backgroundColor: 'var(--severity-no-travel-bg)',
                color: 'var(--severity-no-travel)',
              }}
            >
              <AlertOctagon className="h-3 w-3 shrink-0" aria-hidden="true" />
              No Travel: {formatMiles(risk.no_travel_miles, units)}
            </span>
          ) : null}
          {risk.unknown_miles !== null && risk.unknown_miles > 0 ? (
            <span
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-[7px] font-medium"
              style={{
                backgroundColor: 'var(--severity-unknown-bg)',
                color: 'var(--severity-unknown)',
              }}
            >
              Forecast unavailable: {formatMiles(risk.unknown_miles, units)}
            </span>
          ) : null}
        </div>
      ) : null}

      {/* Forecast Coverage Bar */}
      <div className="mt-2.5">
        <div className="flex items-center justify-between text-[11.5px] text-[var(--color-ink-secondary)] mb-1">
          <span>Forecast coverage</span>
          <span className="tabular-nums font-medium text-[var(--color-ink)]">
            {formatCoveragePercent(risk.coverage_fraction)}
          </span>
        </div>
        <div
          className="h-1.5 w-full rounded-full bg-[var(--color-surface-muted)] overflow-hidden"
          aria-hidden="true"
        >
          <div
            className="h-full rounded-full"
            style={{
              width: `${coveragePct ?? 0}%`,
              backgroundColor:
                coveragePct === 100
                  ? 'var(--color-brand-action)'
                  : 'var(--severity-unknown)',
            }}
          />
        </div>
      </div>

      {/* Priority 4: Concise Backend Rationale */}
      <p className="mt-2.5 pt-2.5 border-t border-[var(--color-border)] text-[12.5px] text-[var(--color-ink-secondary)] leading-relaxed m-0">
        {rationale}
      </p>
    </button>
  );
}
