import { useState } from 'react';
import { RefreshCw } from 'lucide-react';
import type {
  AppViewState,
  PlanLifecycleState,
  PlanResponse,
  RouteCandidate,
  UnitSystem,
} from '../../../shared/types/plan';
import { Button, SafetyNotice, SegmentedControl, SkeletonPanel } from '../../../shared/ui';
import { formatTimestampWithZone } from '../../../shared/utils/format';
import { CheckpointListPanel } from './CheckpointListPanel';
import { RouteComparisonCard } from './RouteComparisonCard';

export interface RouteComparisonRailProps {
  viewState: AppViewState;
  selectedRouteId: string | null;
  selectedCheckpointId: string | null;
  units: UnitSystem;
  onSelectRoute: (routeId: string) => void;
  onSelectCheckpoint: (checkpointId: string) => void;
  onRetry: () => void;
}

const STAGE_COPY: Record<PlanLifecycleState, { title: string; subtitle: string }> = {
  queued: {
    title: 'Preparing trip analysis…',
    subtitle: 'Validating origin, destination, departure time, and load policy.',
  },
  routing: {
    title: 'Fetching truck route alternatives…',
    subtitle: 'Requesting distinct truck-legal highway corridors.',
  },
  sampling_weather: {
    title: 'Checking weather along your route…',
    subtitle: 'Matching forecast data to estimated arrival times at each checkpoint.',
  },
  scoring: {
    title: 'Evaluating corridor risk policy…',
    subtitle: 'Applying wind, rain, snow, and load-weight overrides.',
  },
  completed: {
    title: 'Route comparison ready',
    subtitle: '',
  },
  failed: {
    title: 'Analysis could not be completed',
    subtitle: '',
  },
  canceled: {
    title: 'Analysis canceled',
    subtitle: '',
  },
};

function getRouteLabel(route: RouteCandidate, index: number): string {
  if (route.label && route.label.trim().length > 0) return route.label;
  return `Route ${String.fromCharCode(65 + index)}`;
}

function getWarningStrings(plan: PlanResponse): string[] {
  if (!plan.warnings || plan.warnings.length === 0) return [];
  return plan.warnings.map((w) => (typeof w === 'string' ? w : w.message)).filter(Boolean);
}

export function RouteComparisonRail({
  viewState,
  selectedRouteId,
  selectedCheckpointId,
  units,
  onSelectRoute,
  onSelectCheckpoint,
  onRetry,
}: RouteComparisonRailProps) {
  const [activeTab, setActiveTab] = useState<'routes' | 'checkpoints'>('routes');

  if (viewState.kind === 'idle' || viewState.kind === 'validating' || viewState.kind === 'geocoding') {
    return (
      <div className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
        <p className="text-[13.5px] font-medium text-[var(--color-ink)] m-0">
          Compare routes against forecast conditions
        </p>
        <p className="mt-1.5 text-[13px] text-[var(--color-ink-secondary)] leading-relaxed m-0">
          Enter an origin, destination, departure time, and load weight to evaluate up to
          three distinct truck corridors against arrival-time wind, rain, and snow forecasts.
        </p>
      </div>
    );
  }

  if (viewState.kind === 'planning') {
    const copy = STAGE_COPY[viewState.stage];
    return <SkeletonPanel stageLabel={copy.title} subLabel={copy.subtitle} />;
  }

  if (viewState.kind === 'canceled') {
    return (
      <SafetyNotice
        tone="info"
        title="Route comparison canceled"
        body={viewState.message}
        action={
          <Button variant="secondary" size="sm" onClick={onRetry}>
            Run comparison again
          </Button>
        }
      />
    );
  }

  if (viewState.kind === 'provider_unavailable' || viewState.kind === 'failed') {
    return (
      <SafetyNotice
        tone="error"
        title={
          viewState.kind === 'provider_unavailable'
            ? 'Routing or weather service unavailable'
            : 'We could not retrieve the route forecast'
        }
        body={viewState.error.message}
        detail={
          viewState.error.request_id
            ? `Reference ID: ${viewState.error.request_id}`
            : null
        }
        action={
          viewState.error.retryable ? (
            <Button
              variant="secondary"
              size="sm"
              iconLeft={<RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />}
              onClick={onRetry}
            >
              Try again
            </Button>
          ) : undefined
        }
      />
    );
  }

  if (viewState.kind === 'forecast_out_of_range' && !viewState.plan) {
    return (
      <SafetyNotice
        tone="warning"
        title="Departure outside forecast horizon"
        body={viewState.error.message}
        detail="Adjust the departure date or time within the available forecast window and compare again."
      />
    );
  }

  // Remaining states carry a PlanResponse
  const plan = viewState.plan;
  if (!plan) return null;

  const routes = plan.routes ?? [];
  const selectedIndex = Math.max(
    0,
    routes.findIndex((r) => r.id === selectedRouteId),
  );
  const selectedRoute = routes[selectedIndex] ?? null;
  const planWarnings = getWarningStrings(plan);
  const forecastTimeZone = plan.forecast?.timezone ?? null;

  const routeCountHeading =
    routes.length === 0
      ? 'No truck routes available'
      : routes.length === 1
        ? '1 truck route available'
        : `${routes.length} distinct truck routes available`;

  return (
    <div className="space-y-3.5 spotter-panel-enter">
      {/* Operational State Notices */}
      {viewState.kind === 'no_eligible_route' ? (
        <SafetyNotice
          tone="no_travel"
          title="No eligible route for this forecast"
          body={
            plan.recommendation_reason ??
            'All candidate routes contain No Travel conditions under the current load weight policy. No route is decorated as recommended.'
          }
          detail="Inspect each route below to review affected mileage, or adjust your departure time and recalculate."
        />
      ) : null}

      {viewState.kind === 'partial_coverage' ? (
        <SafetyNotice
          tone="warning"
          title="Weather coverage incomplete"
          body={
            plan.recommendation_reason ??
            'Forecast data is unavailable for portions of one or more corridors. Uncovered segments are marked unknown and cannot be assumed clear.'
          }
          detail="Inspect affected segments below or try recalculating."
        />
      ) : null}

      {viewState.kind === 'no_routes' ? (
        <SafetyNotice
          tone="warning"
          title="No truck routes returned"
          body="The routing provider did not return a viable truck corridor between these locations. Verify origin and destination and try again."
          action={
            <Button variant="secondary" size="sm" onClick={onRetry}>
              Retry search
            </Button>
          }
        />
      ) : null}

      {viewState.kind === 'stale' ? (
        <SafetyNotice
          tone="warning"
          title="Forecast updated since this plan"
          body="Newer forecast data may be available. Recalculate to refresh arrival-time weather classifications."
          action={
            <Button
              variant="secondary"
              size="sm"
              iconLeft={<RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />}
              onClick={onRetry}
            >
              Recalculate
            </Button>
          }
        />
      ) : null}

      {viewState.kind === 'forecast_out_of_range' ? (
        <SafetyNotice
          tone="warning"
          title="Some trip segments are beyond available forecast"
          body={viewState.error.message}
        />
      ) : null}

      {/* Backend-provided general warnings */}
      {planWarnings.length > 0 && viewState.kind === 'results_eligible' ? (
        <SafetyNotice
          tone="info"
          title="Corridor advisory"
          body={planWarnings.join(' ')}
        />
      ) : null}

      {/* Route Count & Tab Switcher */}
      {routes.length > 0 ? (
        <>
          <div className="flex items-center justify-between gap-2 pt-0.5">
            <h2 className="text-[14px] font-semibold text-[var(--color-ink)] m-0 tracking-[-0.01em]">
              {routeCountHeading}
            </h2>
            {routes.length < 3 ? (
              <span className="text-[11.5px] text-[var(--color-ink-secondary)]">
                Provider returned {routes.length}
              </span>
            ) : null}
          </div>

          <SegmentedControl<'routes' | 'checkpoints'>
            label="Result view"
            hideLabel
            size="sm"
            value={activeTab}
            onChange={setActiveTab}
            options={[
              { value: 'routes', label: `Routes (${routes.length})` },
              {
                value: 'checkpoints',
                label: `Checkpoints (${selectedRoute?.checkpoints.length ?? 0})`,
              },
            ]}
          />

          {activeTab === 'routes' ? (
            <div className="space-y-2.5" role="region" aria-label="Route candidates">
              {routes.map((route, idx) => {
                const isRecommended =
                  plan.recommendation_status === 'recommended' &&
                  plan.recommended_route_id === route.id &&
                  route.risk.eligible;

                return (
                  <RouteComparisonCard
                    key={route.id}
                    route={route}
                    index={idx}
                    isSelected={route.id === selectedRoute?.id}
                    isRecommended={isRecommended}
                    recommendationReason={plan.recommendation_reason}
                    units={units}
                    onSelect={onSelectRoute}
                  />
                );
              })}
            </div>
          ) : selectedRoute ? (
            <CheckpointListPanel
              checkpoints={selectedRoute.checkpoints}
              selectedCheckpointId={selectedCheckpointId}
              onSelectCheckpoint={onSelectCheckpoint}
              units={units}
              timeZone={forecastTimeZone}
              routeLabel={getRouteLabel(selectedRoute, selectedIndex)}
            />
          ) : null}
        </>
      ) : null}

      {/* Forecast & Policy Metadata Footer */}
      {plan.forecast || plan.policy_version ? (
        <div className="rounded-[12px] bg-[var(--color-surface-muted)]/75 border border-[var(--color-border)] px-3 py-2.5 text-[11.5px] text-[var(--color-ink-secondary)] space-y-1">
          {plan.forecast?.issued_at ? (
            <div className="flex items-center justify-between gap-2">
              <span>Forecast issued</span>
              <span className="tabular-nums font-medium text-[var(--color-ink)]">
                {formatTimestampWithZone(plan.forecast.issued_at, forecastTimeZone)}
              </span>
            </div>
          ) : null}
          {plan.policy_version ? (
            <div className="flex items-center justify-between gap-2">
              <span>Risk policy</span>
              <span className="font-mono text-[11px] text-[var(--color-ink)]">
                {plan.policy_version}
              </span>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
