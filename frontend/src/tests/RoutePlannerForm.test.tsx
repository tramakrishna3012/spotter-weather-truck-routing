import { useState } from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { RoutePlannerForm } from '../features/trip-planner/components/RoutePlannerForm';
import type { TripFormValues } from '../features/trip-planner/schema/tripSchema';
import type { GeocodeResponse, PlanRequestPayload } from '../shared/types/plan';

function Harness({
  initial,
  onSubmit,
  geocodeSearchFn,
}: {
  initial?: Partial<TripFormValues>;
  onSubmit: (payload: PlanRequestPayload) => void;
  geocodeSearchFn: (query: string) => Promise<GeocodeResponse>;
}) {
  const [values, setValues] = useState<TripFormValues>({
    origin: null,
    destination: null,
    departureDate: '2026-11-20',
    departureTime: '09:00',
    loadWeightInput: '32000',
    displayCheckpointMiles: 25,
    ...initial,
  });

  return (
    <RoutePlannerForm
      values={values}
      onChange={setValues}
      onSubmit={onSubmit}
      isPlanning={false}
      geocodeSearchFn={geocodeSearchFn}
    />
  );
}

describe('RoutePlannerForm', () => {
  it('blocks submission with actionable inline errors when required places or load are invalid', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    const geocodeSearchFn = vi.fn().mockResolvedValue({ results: [] });

    render(
      <Harness
        initial={{ loadWeightInput: '-500' }}
        onSubmit={onSubmit}
        geocodeSearchFn={geocodeSearchFn}
      />,
    );

    await user.click(screen.getByRole('button', { name: /compare routes/i }));

    expect(onSubmit).not.toHaveBeenCalled();
    expect(
      screen.getByText(/select a recognized origin from the suggestions/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/select a recognized destination from the suggestions/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/load weight must be a non-negative number/i),
    ).toBeInTheDocument();
  });

  it('requires explicit disambiguation when multiple geocode matches exist and submits selected spacing', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    const geocodeSearchFn = vi.fn(async (query: string): Promise<GeocodeResponse> => {
      if (query.toLowerCase().includes('spring')) {
        return {
          results: [
            {
              latitude: 39.7817,
              longitude: -89.6501,
              label: 'Springfield, IL',
              subtitle: 'Illinois, United States',
              place_id: 'sp-il',
            },
            {
              latitude: 37.209,
              longitude: -93.2923,
              label: 'Springfield, MO',
              subtitle: 'Missouri, United States',
              place_id: 'sp-mo',
            },
          ],
        };
      }
      return {
        results: [
          {
            latitude: 41.8781,
            longitude: -87.6298,
            label: 'Chicago, IL',
            subtitle: 'Illinois, United States',
            place_id: 'chi-il',
          },
        ],
      };
    });

    render(<Harness onSubmit={onSubmit} geocodeSearchFn={geocodeSearchFn} />);

    // Type ambiguous origin query
    const originInput = screen.getByRole('combobox', { name: /origin/i });
    await user.type(originInput, 'Springfield');

    // Explicit disambiguation banner appears; does NOT auto-select first match
    await waitFor(() => {
      expect(
        screen.getByText(/choose the correct location — multiple places match/i),
      ).toBeInTheDocument();
    });

    // Keyboard select second option (Springfield, MO)
    await user.keyboard('{ArrowDown}{Enter}');
    expect(originInput).toHaveValue('Springfield, MO');

    // Select destination
    const destInput = screen.getByRole('combobox', { name: /destination/i });
    await user.type(destInput, 'Chicago');

    await waitFor(() => {
      expect(screen.getByRole('option', { name: /chicago, il/i })).toBeInTheDocument();
    });
    await user.click(screen.getByRole('option', { name: /chicago, il/i }));

    // Switch display checkpoint spacing to 50 mi
    await user.click(screen.getByRole('radio', { name: /50 mile checkpoint spacing/i }));

    // Submit
    await user.click(screen.getByRole('button', { name: /compare routes/i }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    const payload = onSubmit.mock.calls[0]?.[0] as PlanRequestPayload;
    expect(payload.origin.label).toBe('Springfield, MO');
    expect(payload.destination.label).toBe('Chicago, IL');
    expect(payload.load_weight_lb).toBe(32000);
    expect(payload.display_checkpoint_miles).toBe(50);
    expect(payload.departure_at).toMatch(/^2026-11-20T09:00:00[+-]\d{2}:\d{2}$/);
  });
});
