import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown, ChevronUp, Edit3, X } from 'lucide-react';
import { RouteMapCanvas } from '../features/map-experience/components/RouteMapCanvas';
import { RouteComparisonRail } from '../features/route-comparison/components/RouteComparisonRail';
import { RoutePlannerForm } from '../features/trip-planner/components/RoutePlannerForm';
import type { TripFormValues } from '../features/trip-planner/schema/tripSchema';
import { ForecastTimeline } from '../features/weather-timeline/components/ForecastTimeline';
import { useForecastSlice } from '../features/weather-timeline/hooks/useForecastSlice';
import {
  cancelPlan,
  createPlan,
  getHealthReady,
  getPlan,
  SpotterApiError,
} from '../shared/api/client';
import { DEFAULT_DISPLAY_SPACING } from '../shared/config/env';
import type {
  AppViewState,
  DataMode,
  PlanRequestPayload,
  PlanResponse,
  RouteCandidate,
  UnitSystem,
} from '../shared/types/plan';
import {
  formatDuration,
  formatLocalDateTimeInput,
  formatWeightLb,
} from '../shared/utils/format';
import { HelpPolicyModal } from './components/HelpPolicyModal';
import { MobileBottomSheet, type SheetSnap } from './components/MobileBottomSheet';
import { TopBar } from './components/TopBar';

function createInitialFormValues(): TripFormValues {
  // Default departure to the next rounded hour in user's local timezone (inputs only — never a preloaded result)
  const nextHour = new Date();
  nextHour.setMinutes(0, 0, 0);
  nextHour.setHours(nextHour.getHours() + 1);
  const { date, time } = formatLocalDateTimeInput(nextHour);

  return {
    origin: null,
    destination: null,
    departureDate: date,
    departureTime: time,
    loadWeightInput: '32000',
    displayCheckpointMiles: DEFAULT_DISPLAY_SPACING,
  };
}

function classifyCompletedPlan(plan: PlanResponse): AppViewState {
  const routes = plan.routes ?? [];

  if (plan.state === 'failed') {
    return {
      kind: 'failed',
      error: plan.error ?? {
        code: plan.error_code || 'PLAN_FAILED',
        message:
          plan.error_message || 'We could not complete this route forecast. Try again.',
        retryable: true,
      },
    };
  }

  if (plan.state === 'canceled') {
    return {
      kind: 'canceled',
      message: 'This route comparison was canceled before completion.',
    };
  }

  if (routes.length === 0 || plan.recommendation_status === 'no_routes') {
    return { kind: 'no_routes', plan };
  }

  if (plan.forecast?.stale) {
    return { kind: 'stale', plan };
  }

  if (plan.recommendation_status === 'no_eligible_route') {
    return { kind: 'no_eligible_route', plan };
  }

  const hasIncompleteRoute = routes.some(
    (r) =>
      (r.risk.coverage_fraction !== null && r.risk.coverage_fraction < 1) ||
      (r.risk.unknown_miles !== null && r.risk.unknown_miles > 0),
  );

  if (
    plan.recommendation_status === 'incomplete_coverage' ||
    plan.forecast?.coverage_complete === false ||
    (plan.recommendation_status !== 'recommended' && hasIncompleteRoute)
  ) {
    return { kind: 'partial_coverage', plan };
  }

  // Fallback safety check: if backend did not mark any route recommended and all are ineligible
  const anyEligible = routes.some((r) => r.risk.eligible);
  if (!anyEligible) {
    return { kind: 'no_eligible_route', plan };
  }

  return { kind: 'results_eligible', plan };
}

function getPlanFromState(state: AppViewState): PlanResponse | null {
  switch (state.kind) {
    case 'results_eligible':
    case 'partial_coverage':
    case 'no_eligible_route':
    case 'no_routes':
    case 'stale':
      return state.plan;
    case 'forecast_out_of_range':
      return state.plan ?? null;
    default:
      return null;
  }
}

export function AppShell() {
  const [formValues, setFormValues] = useState<TripFormValues>(createInitialFormValues);
  const [viewState, setViewState] = useState<AppViewState>({ kind: 'idle' });
  const [dataMode, setDataMode] = useState<DataMode | null>(null);
  const [units, setUnits] = useState<UnitSystem>('imperial');

  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null);
  const [selectedCheckpointId, setSelectedCheckpointId] = useState<string | null>(null);
  const [hourOffset, setHourOffset] = useState<number>(0);

  const [plannerCollapsed, setPlannerCollapsed] = useState<boolean>(false);
  const [formEditedSincePlan, setFormEditedSincePlan] = useState<boolean>(false);
  const [helpOpen, setHelpOpen] = useState<boolean>(false);
  const [mobileTripDrawerOpen, setMobileTripDrawerOpen] = useState<boolean>(false);
  const [mobileSheetSnap, setMobileSheetSnap] = useState<SheetSnap>('half');
  const [politeAnnouncement, setPoliteAnnouncement] = useState<string>('');
  const [assertiveAnnouncement, setAssertiveAnnouncement] = useState<string>('');

  const lastSubmittedPayloadRef = useRef<PlanRequestPayload | null>(null);
  const activeAbortRef = useRef<AbortController | null>(null);
  const activePlanIdRef = useRef<string | null>(null);

  // Detect backend data_mode on startup without blocking interaction
  useEffect(() => {
    const controller = new AbortController();
    getHealthReady(controller.signal)
      .then((health) => {
        if (health.data_mode) {
          setDataMode(health.data_mode);
        }
      })
      .catch(() => {
        // Non-fatal; data_mode will also be populated from geocode/plan responses
      });
    return () => controller.abort();
  }, []);

  // Cleanup active requests on unmount
  useEffect(() => {
    return () => {
      activeAbortRef.current?.abort();
    };
  }, []);

  const currentPlan = getPlanFromState(viewState);
  const routes: readonly RouteCandidate[] = useMemo(
    () => currentPlan?.routes ?? [],
    [currentPlan],
  );
  const isPlanning = viewState.kind === 'planning';

  // Fetch 0-48h exploratory corridor forecast slice via TanStack Query
  const forecastQuery = useForecastSlice({
    planId: currentPlan?.plan_id ?? null,
    hourOffset,
    enabled: Boolean(currentPlan && routes.length > 0),
  });

  const forecastSlice = forecastQuery.data ?? null;
  const forecastErrorMessage = forecastQuery.isError
    ? forecastQuery.error instanceof SpotterApiError
      ? forecastQuery.error.detail.message
      : 'Forecast slice is temporarily unavailable for this hour.'
    : null;

  const applyCompletedPlan = useCallback((plan: PlanResponse) => {
    if (plan.data_mode) {
      setDataMode(plan.data_mode);
    }

    const nextView = classifyCompletedPlan(plan);
    setViewState(nextView);

    const planRoutes = plan.routes ?? [];
    const defaultRouteId =
      plan.recommended_route_id && planRoutes.some((r) => r.id === plan.recommended_route_id)
        ? plan.recommended_route_id
        : (planRoutes[0]?.id ?? null);

    setSelectedRouteId(defaultRouteId);
    setSelectedCheckpointId(null);
    setHourOffset(0);
    setPlannerCollapsed(planRoutes.length > 0);
    setFormEditedSincePlan(false);
    setMobileTripDrawerOpen(false);
    setMobileSheetSnap(planRoutes.length > 0 ? 'half' : 'peek');

    if (nextView.kind === 'no_eligible_route') {
      setAssertiveAnnouncement(
        'Warning: No eligible route for this forecast. All candidate routes contain No Travel conditions.',
      );
    } else if (nextView.kind === 'partial_coverage') {
      setPoliteAnnouncement(
        `Route comparison complete with incomplete weather coverage across ${planRoutes.length} route candidates.`,
      );
    } else if (nextView.kind === 'results_eligible') {
      setPoliteAnnouncement(
        `Route comparison ready. ${planRoutes.length} distinct truck routes available.`,
      );
    }
  }, []);

  const executePlan = useCallback(
    async (payload: PlanRequestPayload) => {
      activeAbortRef.current?.abort();
      const controller = new AbortController();
      activeAbortRef.current = controller;
      activePlanIdRef.current = null;
      lastSubmittedPayloadRef.current = payload;

      setViewState({ kind: 'planning', stage: 'queued', planId: null });
      setPoliteAnnouncement('Checking truck routes and arrival weather forecasts.');
      setAssertiveAnnouncement('');

      try {
        let result = await createPlan(payload, controller.signal);
        if (controller.signal.aborted) return;

        activePlanIdRef.current = result.plan_id;
        if (result.data_mode) {
          setDataMode(result.data_mode);
        }

        // Poll if backend returned 202 async lifecycle state
        let pollAttempts = 0;
        const maxPollAttempts = 45;
        while (
          (result.state === 'queued' ||
            result.state === 'routing' ||
            result.state === 'sampling_weather' ||
            result.state === 'scoring') &&
          pollAttempts < maxPollAttempts
        ) {
          setViewState({
            kind: 'planning',
            stage: result.state,
            planId: result.plan_id,
          });
          const delayMs = Math.max(800, Math.min(5000, (result.poll_after_seconds ?? 1.5) * 1000));
          await new Promise<void>((resolve, reject) => {
            const timeout = window.setTimeout(resolve, delayMs);
            controller.signal.addEventListener(
              'abort',
              () => {
                window.clearTimeout(timeout);
                reject(new DOMException('Aborted', 'AbortError'));
              },
              { once: true },
            );
          });

          if (controller.signal.aborted) return;
          result = await getPlan(result.plan_id, controller.signal);
          pollAttempts += 1;
        }

        if (controller.signal.aborted) return;

        if (
          result.state === 'queued' ||
          result.state === 'routing' ||
          result.state === 'sampling_weather' ||
          result.state === 'scoring'
        ) {
          setViewState({
            kind: 'failed',
            error: {
              code: 'PLAN_POLL_TIMEOUT',
              message:
                'Route analysis is taking longer than expected. Your inputs are preserved—try again shortly.',
              retryable: true,
            },
          });
          setAssertiveAnnouncement('Route analysis timed out. You can retry.');
          return;
        }

        applyCompletedPlan(result);
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') {
          return;
        }

        if (err instanceof SpotterApiError) {
          const code = err.detail.code.toLowerCase();
          if (code.includes('forecast_out_of_range') || code.includes('horizon')) {
            setViewState({ kind: 'forecast_out_of_range', error: err.detail });
            setAssertiveAnnouncement(err.detail.message);
            return;
          }
          if (err.status === 502 || err.status === 503 || err.status === 504 || err.status === 0) {
            setViewState({ kind: 'provider_unavailable', error: err.detail });
            setAssertiveAnnouncement(err.detail.message);
            return;
          }
          setViewState({ kind: 'failed', error: err.detail });
          setAssertiveAnnouncement(err.detail.message);
          return;
        }

        setViewState({
          kind: 'failed',
          error: {
            code: 'UNKNOWN_ERROR',
            message: 'We could not retrieve the route forecast. Try again.',
            retryable: true,
          },
        });
        setAssertiveAnnouncement('We could not retrieve the route forecast. Try again.');
      }
    },
    [applyCompletedPlan],
  );

  const handleCancelPlanning = useCallback(() => {
    activeAbortRef.current?.abort();
    const pendingId = activePlanIdRef.current;
    if (pendingId) {
      void cancelPlan(pendingId).catch(() => {
        // Best-effort server cancellation
      });
    }
    setViewState({
      kind: 'canceled',
      message: 'Your trip inputs have been preserved. Compare routes whenever you are ready.',
    });
    setPoliteAnnouncement('Route comparison canceled.');
  }, []);

  const handleRetry = useCallback(() => {
    if (lastSubmittedPayloadRef.current) {
      void executePlan(lastSubmittedPayloadRef.current);
    } else {
      setPlannerCollapsed(false);
    }
  }, [executePlan]);

  const handleFormValuesChange = useCallback(
    (next: TripFormValues) => {
      setFormValues(next);
      if (currentPlan) {
        setFormEditedSincePlan(true);
      }
    },
    [currentPlan],
  );

  const handleSelectRoute = useCallback(
    (routeId: string) => {
      setSelectedRouteId(routeId);
      setSelectedCheckpointId(null);
      const idx = routes.findIndex((r) => r.id === routeId);
      const picked = routes[idx];
      if (picked) {
        const name = picked.label || `Route ${String.fromCharCode(65 + Math.max(0, idx))}`;
        setPoliteAnnouncement(
          `Viewing ${name}, ${formatDuration(picked.duration_seconds)}.`,
        );
      }
    },
    [routes],
  );

  const mobileSheetSummary = useMemo(() => {
    if (viewState.kind === 'planning') {
      return { title: 'Checking routes and forecast…', subtitle: null };
    }
    if (viewState.kind === 'no_eligible_route') {
      return {
        title: 'No eligible route for this forecast',
        subtitle: `${routes.length} routes inspected · No Travel detected`,
      };
    }
    if (routes.length > 0) {
      const selected = routes.find((r) => r.id === selectedRouteId) ?? routes[0];
      const name = selected?.label || 'Route A';
      return {
        title:
          viewState.kind === 'results_eligible'
            ? `${name} · ${formatDuration(selected?.duration_seconds)}`
            : `${routes.length} routes available`,
        subtitle:
          routes.length === 1
            ? 'Tap expand to inspect checkpoints'
            : `Compare ${routes.length} distinct truck routes`,
      };
    }
    return {
      title: 'Plan a weather-aware route',
      subtitle: 'Tap Trip above to enter origin, destination, and load',
    };
  }, [viewState.kind, routes, selectedRouteId]);

  return (
    <div className="h-full w-full flex flex-col bg-[var(--color-canvas)] overflow-hidden">
      {/* Screen-Reader Live Regions */}
      <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">
        {politeAnnouncement}
      </div>
      <div className="sr-only" role="alert" aria-live="assertive" aria-atomic="true">
        {assertiveAnnouncement}
      </div>

      {/* Slim, Quiet Header */}
      <TopBar
        dataMode={dataMode}
        units={units}
        onUnitsChange={setUnits}
        onOpenHelp={() => setHelpOpen(true)}
        onOpenMobileTripDrawer={() => setMobileTripDrawerOpen(true)}
      />

      {/* Main Split Operational Cockpit */}
      <main className="flex-1 min-h-0 flex relative overflow-hidden">
        {/* Desktop & Tablet Left Instrument Rail */}
        <aside
          aria-label="Trip planner and route comparison"
          className="hidden md:flex md:w-[348px] lg:w-[var(--rail-width)] shrink-0 flex-col bg-[var(--color-canvas)] border-r border-[var(--color-border)] z-[var(--z-rail)] min-h-0"
        >
          <div className="flex-1 overflow-y-auto spotter-scroll p-4 space-y-4">
            {/* Collapsible Planner Instrument Card */}
            <section
              aria-label="Trip setup"
              className="rounded-[18px] border border-[var(--color-border)] bg-[var(--color-surface)] shadow-[var(--shadow-lifted)] overflow-hidden"
            >
              {plannerCollapsed && currentPlan ? (
                <div className="p-3.5">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="text-[11px] font-semibold uppercase tracking-[0.05em] text-[var(--color-ink-secondary)]">
                        Active trip
                      </div>
                      <div className="mt-1 text-[13.5px] font-semibold text-[var(--color-ink)] truncate">
                        {formValues.origin?.label ?? 'Origin'} &rarr;{' '}
                        {formValues.destination?.label ?? 'Destination'}
                      </div>
                      <div className="mt-0.5 text-[12px] text-[var(--color-ink-secondary)] tabular-nums">
                        {formValues.departureDate} {formValues.departureTime} ·{' '}
                        {formatWeightLb(
                          Number(formValues.loadWeightInput.replace(/,/g, '')),
                          units,
                        )}{' '}
                        · {formValues.displayCheckpointMiles} mi
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={() => setPlannerCollapsed(false)}
                      aria-expanded={false}
                      className="inline-flex items-center gap-1 h-8 px-2.5 rounded-[9px] border border-[var(--color-border)] bg-[var(--color-surface-muted)] text-[12px] font-medium text-[var(--color-brand-deep)] hover:bg-[var(--color-brand-tint)] cursor-pointer shrink-0"
                    >
                      <Edit3 className="h-3.5 w-3.5" aria-hidden="true" />
                      Edit
                    </button>
                  </div>
                </div>
              ) : (
                <div className="p-4">
                  <div className="flex items-center justify-between gap-2 mb-3.5">
                    <div>
                      <h1 className="text-[16px] font-semibold tracking-[-0.015em] text-[var(--color-ink)] m-0">
                        Plan your trip
                      </h1>
                    </div>
                    {currentPlan ? (
                      <button
                        type="button"
                        onClick={() => setPlannerCollapsed(true)}
                        aria-label="Collapse trip form"
                        className="inline-flex items-center gap-1 h-7 px-2 rounded-[8px] text-[12px] font-medium text-[var(--color-ink-secondary)] hover:text-[var(--color-ink)] hover:bg-[var(--color-surface-muted)] cursor-pointer"
                      >
                        <span>Collapse</span>
                        <ChevronUp className="h-3.5 w-3.5" aria-hidden="true" />
                      </button>
                    ) : null}
                  </div>

                  {formEditedSincePlan ? (
                    <div className="mb-3 rounded-[10px] bg-[var(--color-brand-tint)] border border-[#C3DFE2] px-3 py-2 text-[12px] text-[var(--color-brand-deep)]">
                      Trip details updated. Select <strong>Compare routes</strong> to
                      recalculate weather risk.
                    </div>
                  ) : null}

                  <RoutePlannerForm
                    values={formValues}
                    onChange={handleFormValuesChange}
                    onSubmit={(payload) => void executePlan(payload)}
                    onCancel={handleCancelPlanning}
                    isPlanning={isPlanning}
                    onDataModeDetected={setDataMode}
                  />
                </div>
              )}
            </section>

            {/* Route Comparison & Checkpoints Rail */}
            <RouteComparisonRail
              viewState={viewState}
              selectedRouteId={selectedRouteId}
              selectedCheckpointId={selectedCheckpointId}
              units={units}
              onSelectRoute={handleSelectRoute}
              onSelectCheckpoint={(cpId) => setSelectedCheckpointId(cpId)}
              onRetry={handleRetry}
            />
          </div>
        </aside>

        {/* Right Dominant Full-Bleed Map Canvas + Bottom Floating Forecast Scrubber */}
        <section
          aria-label="Map workspace"
          className="flex-1 relative min-w-0 min-h-0"
        >
          <RouteMapCanvas
            planId={currentPlan?.plan_id ?? null}
            routes={routes}
            selectedRouteId={selectedRouteId}
            selectedCheckpointId={selectedCheckpointId}
            forecastSlice={forecastSlice}
            units={units}
            timeZone={currentPlan?.forecast?.timezone ?? null}
            isPlanning={isPlanning}
            onSelectRoute={handleSelectRoute}
            onSelectCheckpoint={setSelectedCheckpointId}
          />

          {/* Floating 0–48h Forecast Timeline (safe margins above attribution & mobile sheet) */}
          {currentPlan && routes.length > 0 ? (
            <div className="pointer-events-none absolute left-3 right-3 md:left-5 md:right-5 bottom-[144px] md:bottom-7 z-[var(--z-timeline)] flex justify-center">
              <div className="pointer-events-auto w-full max-w-[700px]">
                <ForecastTimeline
                  hourOffset={hourOffset}
                  onHourOffsetChange={setHourOffset}
                  slice={forecastSlice}
                  referenceAt={
                    currentPlan.forecast?.reference_at ??
                    currentPlan.forecast?.reference_time ??
                    currentPlan.forecast?.issued_at ??
                    currentPlan.generated_at ??
                    null
                  }
                  timeZone={currentPlan.forecast?.timezone ?? null}
                  isFetching={forecastQuery.isFetching}
                  errorMessage={forecastErrorMessage}
                  disabled={isPlanning}
                />
              </div>
            </div>
          ) : null}
        </section>

        {/* Mobile Three-Position Bottom Sheet (< 768px) */}
        <MobileBottomSheet
          snap={mobileSheetSnap}
          onSnapChange={setMobileSheetSnap}
          summaryTitle={mobileSheetSummary.title}
          summarySubtitle={mobileSheetSummary.subtitle}
        >
          <RouteComparisonRail
            viewState={viewState}
            selectedRouteId={selectedRouteId}
            selectedCheckpointId={selectedCheckpointId}
            units={units}
            onSelectRoute={handleSelectRoute}
            onSelectCheckpoint={(cpId) => {
              setSelectedCheckpointId(cpId);
              setMobileSheetSnap('peek');
            }}
            onRetry={handleRetry}
          />
        </MobileBottomSheet>
      </main>

      {/* Mobile Full-Screen Trip Drawer (< 768px) */}
      {mobileTripDrawerOpen ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Edit trip details"
          className="md:hidden fixed inset-0 z-[var(--z-modal)] bg-[var(--color-surface)] flex flex-col"
        >
          <div className="h-[var(--topbar-height)] px-4 border-b border-[var(--color-border)] flex items-center justify-between">
            <h1 className="text-[16px] font-semibold text-[var(--color-ink)] m-0">
              Plan your trip
            </h1>
            <button
              type="button"
              onClick={() => setMobileTripDrawerOpen(false)}
              aria-label="Close trip planner"
              className="h-9 w-9 inline-flex items-center justify-center rounded-[10px] text-[var(--color-ink-secondary)] hover:bg-[var(--color-surface-muted)] cursor-pointer"
            >
              <X className="h-5 w-5" aria-hidden="true" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto spotter-scroll p-4 pb-8">
            <RoutePlannerForm
              values={formValues}
              onChange={handleFormValuesChange}
              onSubmit={(payload) => void executePlan(payload)}
              onCancel={handleCancelPlanning}
              isPlanning={isPlanning}
              onDataModeDetected={setDataMode}
            />

            {/* Units toggle inside mobile drawer */}
            <div className="mt-6 pt-4 border-t border-[var(--color-border)] flex items-center justify-between">
              <span className="text-[13px] font-medium text-[var(--color-ink)]">
                Display units
              </span>
              <button
                type="button"
                onClick={() => setUnits((u) => (u === 'imperial' ? 'metric' : 'imperial'))}
                className="inline-flex items-center gap-1.5 h-9 px-3 rounded-[10px] border border-[var(--color-border-strong)] bg-[var(--color-surface-muted)] text-[13px] font-medium text-[var(--color-ink)] cursor-pointer"
              >
                <span>{units === 'imperial' ? 'Imperial (mi, mph)' : 'Metric (km, km/h)'}</span>
                <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {/* Policy & Help Modal */}
      <HelpPolicyModal
        open={helpOpen}
        onClose={() => setHelpOpen(false)}
        policyVersion={currentPlan?.policy_version ?? null}
      />
    </div>
  );
}
