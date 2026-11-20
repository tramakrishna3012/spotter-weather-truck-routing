import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { RouteComparisonCard } from '../features/route-comparison/components/RouteComparisonCard';
import type { RouteCandidate } from '../shared/types/plan';

function makeRoute(overrides: Partial<RouteCandidate> = {}): RouteCandidate {
  return {
    id: 'route-a',
    label: 'Route A',
    summary: 'I-95 S',
    geometry: {
      type: 'LineString',
      coordinates: [
        [-74.006, 40.7128],
        [-75.1636, 39.9526],
      ],
    },
    distance_m: 160934.4,
    duration_seconds: 8400,
    risk: {
      severe_miles: 0,
      high_miles: 4.2,
      no_travel_miles: 0,
      unknown_miles: 0,
      weighted_average_risk: 0.46,
      eligible: true,
      coverage_fraction: 1.0,
    },
    checkpoints: [],
    risk_segments: [],
    eta_method: 'provider_timing',
    provider_warnings: [],
    rationale: 'Lowest Severe miles among covered eligible routes.',
    ...overrides,
  };
}

describe('RouteComparisonCard', () => {
  it('keeps Recommended badge distinct from Selected state', async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();

    render(
      <div>
        <RouteComparisonCard
          route={makeRoute({ id: 'route-a', label: 'Route A' })}
          index={0}
          isSelected={false}
          isRecommended={true}
          units="imperial"
          onSelect={onSelect}
        />
        <RouteComparisonCard
          route={makeRoute({
            id: 'route-b',
            label: 'Route B',
            rationale: 'Alternative corridor with higher wind exposure.',
          })}
          index={1}
          isSelected={true}
          isRecommended={false}
          units="imperial"
          onSelect={onSelect}
        />
      </div>,
    );

    const buttons = screen.getAllByRole('button');
    expect(buttons[0]).toHaveAttribute('aria-pressed', 'false');
    expect(buttons[1]).toHaveAttribute('aria-pressed', 'true');

    // Route A is Recommended but NOT Viewing; Route B is Viewing + Eligible (NOT Recommended)
    expect(screen.getByText('Recommended')).toBeInTheDocument();
    expect(screen.getByText('Viewing')).toBeInTheDocument();
    expect(screen.getByText('Eligible')).toBeInTheDocument();

    await user.click(buttons[0]!);
    expect(onSelect).toHaveBeenCalledWith('route-a');
  });

  it('displays No Travel warning and mileage without recommending the route', () => {
    const blockedRoute = makeRoute({
      id: 'route-blocked',
      label: 'Route A',
      risk: {
        severe_miles: 12.5,
        high_miles: 18.0,
        no_travel_miles: 14.3,
        unknown_miles: 0,
        weighted_average_risk: 3.4,
        eligible: false,
        coverage_fraction: 1.0,
      },
      rationale: 'Wind gusts 48 mph exceed 30,000 lb load override threshold.',
    });

    render(
      <RouteComparisonCard
        route={blockedRoute}
        index={0}
        isSelected={true}
        isRecommended={false}
        units="imperial"
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByText('No Travel')).toBeInTheDocument();
    expect(screen.getByText(/No Travel: 14\.3 mi/)).toBeInTheDocument();
    expect(screen.queryByText('Recommended')).not.toBeInTheDocument();
  });

  it('surfaces incomplete weather coverage honestly and never recomputes eligibility on the client', () => {
    const partialRoute = makeRoute({
      id: 'route-partial',
      label: 'Route C',
      risk: {
        severe_miles: 0,
        high_miles: 0,
        no_travel_miles: 0,
        unknown_miles: 24.5,
        weighted_average_risk: 0.12,
        eligible: false,
        coverage_fraction: 0.72,
      },
      rationale: null,
    });

    render(
      <RouteComparisonCard
        route={partialRoute}
        index={2}
        isSelected={false}
        isRecommended={false}
        units="imperial"
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByText('Incomplete coverage')).toBeInTheDocument();
    expect(screen.getByText(/Forecast unavailable: 24\.5 mi/)).toBeInTheDocument();
    expect(screen.getByText('72%')).toBeInTheDocument();
    expect(screen.queryByText('Recommended')).not.toBeInTheDocument();
    expect(screen.queryByText('Eligible')).not.toBeInTheDocument();
  });
});
