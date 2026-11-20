import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ForecastTimeline } from '../features/weather-timeline/components/ForecastTimeline';
import type { ForecastSliceResponse } from '../shared/types/plan';

describe('ForecastTimeline', () => {
  it('exposes accessible 0-48h slider aria-valuetext and explicit wall-clock vs truck ETA copy', () => {
    const slice: ForecastSliceResponse = {
      hour_offset: 6,
      valid_at: '2026-11-20T18:00:00Z',
      reference_at: '2026-11-20T12:00:00Z',
      timezone: 'America/New_York',
      points: [],
      coverage_fraction: 1.0,
      coverage_complete: true,
      data_origin: 'fixture',
    };

    render(
      <ForecastTimeline
        hourOffset={6}
        onHourOffsetChange={vi.fn()}
        slice={slice}
        referenceAt="2026-11-20T12:00:00Z"
        timeZone="America/New_York"
      />,
    );

    const slider = screen.getByRole('slider', { name: /forecast hour offset/i });
    expect(slider).toHaveAttribute('min', '0');
    expect(slider).toHaveAttribute('max', '48');
    expect(slider).toHaveAttribute('aria-valuenow', '6');
    expect(slider.getAttribute('aria-valuetext')).toContain('+6 hours');
    expect(slider.getAttribute('aria-valuetext')).toContain('Nov 20');

    expect(
      screen.getByText(
        /exploratory corridor forecast \(wall-clock\) — route ranking remains based on truck eta/i,
      ),
    ).toBeInTheDocument();
    expect(screen.getByText('Coverage 100%')).toBeInTheDocument();
  });

  it('warns honestly when corridor forecast coverage is incomplete or unavailable', () => {
    const partialSlice: ForecastSliceResponse = {
      hour_offset: 36,
      valid_at: '2026-11-22T00:00:00Z',
      timezone: 'UTC',
      points: [],
      coverage_fraction: 0.65,
      coverage_complete: false,
      data_origin: 'open_meteo',
    };

    const { rerender } = render(
      <ForecastTimeline
        hourOffset={36}
        onHourOffsetChange={vi.fn()}
        slice={partialSlice}
      />,
    );

    expect(screen.getByText(/partial coverage · 65%/i)).toBeInTheDocument();

    rerender(
      <ForecastTimeline
        hourOffset={48}
        onHourOffsetChange={vi.fn()}
        slice={null}
        errorMessage="Forecast slice is beyond the current provider horizon."
      />,
    );

    expect(screen.getByText('Forecast unavailable')).toBeInTheDocument();
    expect(
      screen.getByText(/beyond the current provider horizon/i),
    ).toBeInTheDocument();
  });

  it('coalesces slider changes via requestAnimationFrame and reports selected hour', () => {
    const onHourOffsetChange = vi.fn();
    const rafSpy = vi
      .spyOn(window, 'requestAnimationFrame')
      .mockImplementation((cb: FrameRequestCallback) => {
        cb(0);
        return 1;
      });

    render(
      <ForecastTimeline
        hourOffset={0}
        onHourOffsetChange={onHourOffsetChange}
        slice={null}
      />,
    );

    const slider = screen.getByRole('slider', { name: /forecast hour offset/i });
    fireEvent.change(slider, { target: { value: '18' } });

    expect(onHourOffsetChange).toHaveBeenCalledWith(18);
    rafSpy.mockRestore();
  });
});
