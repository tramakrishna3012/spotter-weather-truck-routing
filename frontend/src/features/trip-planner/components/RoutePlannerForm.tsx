import { useId, useState, type FormEvent } from 'react';
import { ArrowUpDown, Calendar, Clock, Info, Scale } from 'lucide-react';
import {
  SUPPORTED_DISPLAY_SPACINGS,
  type DisplaySpacingMiles,
} from '../../../shared/config/env';
import type { GeocodeResponse, PlanRequestPayload } from '../../../shared/types/plan';
import { Button, SegmentedControl } from '../../../shared/ui';
import { getLocalTimeZone } from '../../../shared/utils/format';
import {
  validateTripForm,
  type TripFormValues,
  type TripValidationErrors,
} from '../schema/tripSchema';
import { LocationAutocomplete } from './LocationAutocomplete';

export interface RoutePlannerFormProps {
  values: TripFormValues;
  onChange: (next: TripFormValues) => void;
  onSubmit: (payload: PlanRequestPayload) => void;
  onCancel?: () => void;
  isPlanning: boolean;
  /** Optional custom geocode search function for testing */
  geocodeSearchFn?: (query: string, signal?: AbortSignal) => Promise<GeocodeResponse>;
  onDataModeDetected?: (mode: 'live' | 'fixture') => void;
}

const SPACING_OPTIONS = SUPPORTED_DISPLAY_SPACINGS.map((miles) => ({
  value: miles,
  label: `${miles} mi`,
  ariaLabel: `${miles} mile checkpoint spacing`,
}));

export function RoutePlannerForm({
  values,
  onChange,
  onSubmit,
  onCancel,
  isPlanning,
  geocodeSearchFn,
  onDataModeDetected,
}: RoutePlannerFormProps) {
  const dateId = useId();
  const timeId = useId();
  const weightId = useId();
  const weightHintId = useId();
  const spacingHintId = useId();

  const [errors, setErrors] = useState<TripValidationErrors>({});
  const localTimeZone = getLocalTimeZone();

  function updateField<K extends keyof TripFormValues>(field: K, fieldValue: TripFormValues[K]) {
    onChange({
      ...values,
      [field]: fieldValue,
    });
    if (errors[field]) {
      setErrors((prev) => {
        const next = { ...prev };
        delete next[field];
        return next;
      });
    }
  }

  function handleSwapLocations() {
    onChange({
      ...values,
      origin: values.destination,
      destination: values.origin,
    });
    setErrors((prev) => {
      const next = { ...prev };
      delete next.origin;
      delete next.destination;
      return next;
    });
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validation = validateTripForm(values);
    if (!validation.ok) {
      setErrors(validation.errors);
      return;
    }
    setErrors({});
    onSubmit(validation.payload);
  }

  return (
    <form
      onSubmit={handleSubmit}
      noValidate
      aria-label="Trip route planner"
      className="space-y-4"
    >
      {/* Origin & Destination with Swap */}
      <div className="space-y-3 relative">
        <LocationAutocomplete
          label="Origin"
          placeholder="City, state, or facility"
          markerTone="origin"
          value={values.origin}
          onChange={(loc) => updateField('origin', loc)}
          error={errors.origin}
          disabled={isPlanning}
          searchFn={geocodeSearchFn}
          onDataModeDetected={onDataModeDetected}
        />

        <div className="flex items-center justify-end -my-1.5">
          <button
            type="button"
            onClick={handleSwapLocations}
            disabled={isPlanning || (!values.origin && !values.destination)}
            aria-label="Swap origin and destination"
            className="inline-flex items-center gap-1 px-2 py-1 rounded-[8px] text-[12px] font-medium text-[var(--color-ink-secondary)] hover:text-[var(--color-brand-deep)] hover:bg-[var(--color-surface-muted)] disabled:opacity-40 disabled:pointer-events-none cursor-pointer transition-colors duration-[var(--duration-feedback)]"
          >
            <ArrowUpDown className="h-3.5 w-3.5" aria-hidden="true" />
            Swap
          </button>
        </div>

        <LocationAutocomplete
          label="Destination"
          placeholder="City, state, or facility"
          markerTone="destination"
          value={values.destination}
          onChange={(loc) => updateField('destination', loc)}
          error={errors.destination}
          disabled={isPlanning}
          searchFn={geocodeSearchFn}
          onDataModeDetected={onDataModeDetected}
        />
      </div>

      {/* Departure Date & Time + Timezone Pill */}
      <div>
        <div className="flex items-center justify-between gap-2 mb-1.5">
          <span className="text-[13px] font-medium text-[var(--color-ink)]">
            Departure
          </span>
          <span
            className="inline-flex items-center px-2 py-0.5 rounded-full bg-[var(--color-surface-muted)] border border-[var(--color-border)] text-[11.5px] font-medium text-[var(--color-ink-secondary)]"
            title={`Departure time is interpreted in ${localTimeZone}`}
          >
            {localTimeZone}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2.5">
          <div>
            <label htmlFor={dateId} className="sr-only">
              Departure date
            </label>
            <div className="relative">
              <Calendar
                className="h-4 w-4 text-[var(--color-ink-secondary)] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
                aria-hidden="true"
              />
              <input
                id={dateId}
                type="date"
                disabled={isPlanning}
                value={values.departureDate}
                onChange={(e) => updateField('departureDate', e.target.value)}
                aria-invalid={Boolean(errors.departureDate)}
                className={[
                  'w-full h-11 pl-9 pr-2.5 rounded-[var(--radius-control)] text-[13.5px] tabular-nums',
                  'bg-[var(--color-surface)] border transition-colors duration-[var(--duration-feedback)]',
                  errors.departureDate
                    ? 'border-[var(--severity-severe)]'
                    : 'border-[var(--color-border-strong)] hover:border-[var(--color-brand-action)]/60',
                ].join(' ')}
              />
            </div>
          </div>

          <div>
            <label htmlFor={timeId} className="sr-only">
              Departure time
            </label>
            <div className="relative">
              <Clock
                className="h-4 w-4 text-[var(--color-ink-secondary)] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
                aria-hidden="true"
              />
              <input
                id={timeId}
                type="time"
                disabled={isPlanning}
                value={values.departureTime}
                onChange={(e) => updateField('departureTime', e.target.value)}
                aria-invalid={Boolean(errors.departureTime)}
                className={[
                  'w-full h-11 pl-9 pr-2.5 rounded-[var(--radius-control)] text-[13.5px] tabular-nums',
                  'bg-[var(--color-surface)] border transition-colors duration-[var(--duration-feedback)]',
                  errors.departureTime
                    ? 'border-[var(--severity-severe)]'
                    : 'border-[var(--color-border-strong)] hover:border-[var(--color-brand-action)]/60',
                ].join(' ')}
              />
            </div>
          </div>
        </div>

        {errors.departureDate || errors.departureTime ? (
          <p role="alert" className="mt-1.5 text-[12.5px] text-[var(--severity-severe)] m-0">
            {errors.departureDate ?? errors.departureTime}
          </p>
        ) : null}
      </div>

      {/* Load Weight (lb) */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <label
            htmlFor={weightId}
            className="text-[13px] font-medium text-[var(--color-ink)]"
          >
            Load weight
          </label>
          <span className="text-[11.5px] text-[var(--color-ink-secondary)]">
            Pounds (lb)
          </span>
        </div>

        <div className="relative">
          <Scale
            className="h-4 w-4 text-[var(--color-ink-secondary)] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
            aria-hidden="true"
          />
          <input
            id={weightId}
            type="text"
            inputMode="numeric"
            disabled={isPlanning}
            value={values.loadWeightInput}
            onChange={(e) => updateField('loadWeightInput', e.target.value)}
            placeholder="e.g. 32000"
            aria-invalid={Boolean(errors.loadWeightInput)}
            aria-describedby={weightHintId}
            className={[
              'w-full h-11 pl-9 pr-12 rounded-[var(--radius-control)] text-[14px] tabular-nums',
              'bg-[var(--color-surface)] border transition-colors duration-[var(--duration-feedback)]',
              errors.loadWeightInput
                ? 'border-[var(--severity-severe)]'
                : 'border-[var(--color-border-strong)] hover:border-[var(--color-brand-action)]/60',
            ].join(' ')}
          />
          <span
            aria-hidden="true"
            className="absolute right-3.5 top-1/2 -translate-y-1/2 text-[13px] font-medium text-[var(--color-ink-secondary)]"
          >
            lb
          </span>
        </div>

        <p
          id={weightHintId}
          className="mt-1.5 text-[12px] text-[var(--color-ink-secondary)] m-0 leading-snug"
        >
          Backend policy applies wind risk overrides above 30,000 lb and 40,000 lb.
        </p>

        {errors.loadWeightInput ? (
          <p role="alert" className="mt-1 text-[12.5px] text-[var(--severity-severe)] m-0">
            {errors.loadWeightInput}
          </p>
        ) : null}
      </div>

      {/* Display Checkpoint Spacing (10 / 25 / 50 mi) */}
      <div>
        <SegmentedControl<DisplaySpacingMiles>
          label="Display checkpoint spacing"
          options={SPACING_OPTIONS}
          value={values.displayCheckpointMiles}
          onChange={(miles) => updateField('displayCheckpointMiles', miles)}
          disabled={isPlanning}
        />
        <p
          id={spacingHintId}
          className="mt-1.5 flex items-start gap-1.5 text-[12px] text-[var(--color-ink-secondary)] m-0 leading-snug"
        >
          <Info className="h-3.5 w-3.5 shrink-0 mt-0.5" aria-hidden="true" />
          <span>
            Controls displayed checkpoint density. Safety scoring always evaluates at
            backend 10-mi resolution.
          </span>
        </p>
      </div>

      {/* Primary Action */}
      <div className="pt-1 flex items-center gap-2">
        <Button type="submit" variant="primary" size="lg" fullWidth disabled={isPlanning}>
          {isPlanning ? 'Comparing routes…' : 'Compare routes'}
        </Button>
        {isPlanning && onCancel ? (
          <Button type="button" variant="secondary" size="lg" onClick={onCancel}>
            Cancel
          </Button>
        ) : null}
      </div>
    </form>
  );
}
