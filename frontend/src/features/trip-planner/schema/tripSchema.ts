import { z } from 'zod';
import { SUPPORTED_DISPLAY_SPACINGS, type DisplaySpacingMiles } from '../../../shared/config/env';
import type { GeoLocation, PlanRequestPayload } from '../../../shared/types/plan';
import { buildOffsetIsoTimestamp } from '../../../shared/utils/format';

export const geoLocationSchema = z.object({
  latitude: z.number().finite().min(-90).max(90),
  longitude: z.number().finite().min(-180).max(180),
  label: z.string().trim().min(1, 'Select a recognized place from the list.'),
  subtitle: z.string().nullable().optional(),
  place_id: z.string().nullable().optional(),
  country_code: z.string().nullable().optional(),
});

export const displaySpacingSchema = z
  .number()
  .refine(
    (v): v is DisplaySpacingMiles =>
      (SUPPORTED_DISPLAY_SPACINGS as readonly number[]).includes(v),
    { message: 'Display checkpoint spacing must be 10, 25, or 50 miles.' },
  );

export const tripFormSchema = z
  .object({
    origin: geoLocationSchema.nullable(),
    destination: geoLocationSchema.nullable(),
    departureDate: z
      .string()
      .regex(/^\d{4}-\d{2}-\d{2}$/, 'Enter a valid departure date.'),
    departureTime: z
      .string()
      .regex(/^\d{2}:\d{2}$/, 'Enter a valid departure time.'),
    loadWeightInput: z.string().trim().min(1, 'Enter a load weight in pounds (lb).'),
    displayCheckpointMiles: displaySpacingSchema,
  })
  .superRefine((data, ctx) => {
    if (!data.origin) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['origin'],
        message: 'Select a recognized origin from the suggestions.',
      });
    }

    if (!data.destination) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['destination'],
        message: 'Select a recognized destination from the suggestions.',
      });
    }

    if (
      data.origin &&
      data.destination &&
      Math.abs(data.origin.latitude - data.destination.latitude) < 1e-4 &&
      Math.abs(data.origin.longitude - data.destination.longitude) < 1e-4
    ) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['destination'],
        message: 'Destination must be a different location from origin.',
      });
    }

    const departureIso = buildOffsetIsoTimestamp(data.departureDate, data.departureTime);
    if (!departureIso) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['departureDate'],
        message: 'Enter a valid departure date and time.',
      });
    }

    const normalizedWeight = data.loadWeightInput.replace(/,/g, '');
    const parsedWeight = Number(normalizedWeight);
    if (!Number.isFinite(parsedWeight) || parsedWeight < 0) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['loadWeightInput'],
        message: 'Load weight must be a non-negative number in lb.',
      });
    } else if (parsedWeight > 200_000) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['loadWeightInput'],
        message: 'Load weight exceeds maximum supported input (200,000 lb).',
      });
    }
  });

export interface TripFormValues {
  origin: GeoLocation | null;
  destination: GeoLocation | null;
  departureDate: string;
  departureTime: string;
  loadWeightInput: string;
  displayCheckpointMiles: DisplaySpacingMiles;
}

export interface TripValidationErrors {
  origin?: string;
  destination?: string;
  departureDate?: string;
  departureTime?: string;
  loadWeightInput?: string;
  displayCheckpointMiles?: string;
}

export function validateTripForm(
  values: TripFormValues,
): { ok: true; payload: PlanRequestPayload } | { ok: false; errors: TripValidationErrors } {
  const result = tripFormSchema.safeParse(values);
  if (!result.success) {
    const errors: TripValidationErrors = {};
    for (const issue of result.error.issues) {
      const key = issue.path[0];
      if (typeof key === 'string' && !(key in errors)) {
        errors[key as keyof TripValidationErrors] = issue.message;
      }
    }
    return { ok: false, errors };
  }

  const valid = result.data;
  const departureAt = buildOffsetIsoTimestamp(valid.departureDate, valid.departureTime);
  if (!valid.origin || !valid.destination || !departureAt) {
    return {
      ok: false,
      errors: { departureDate: 'Enter a valid departure date and time.' },
    };
  }

  const parsedWeight = Number(valid.loadWeightInput.replace(/,/g, ''));

  return {
    ok: true,
    payload: {
      origin: {
        latitude: valid.origin.latitude,
        longitude: valid.origin.longitude,
        label: valid.origin.label,
      },
      destination: {
        latitude: valid.destination.latitude,
        longitude: valid.destination.longitude,
        label: valid.destination.label,
      },
      departure_at: departureAt,
      load_weight_lb: parsedWeight,
      display_checkpoint_miles: valid.displayCheckpointMiles,
    },
  };
}
