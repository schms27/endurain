import type { ChartRenderOptions } from '@/composables/useChartProvider'
import type { Units } from '@/features/activities/utils/format'
import type { RoutePoint } from '@/features/routes/types'

import { elevationToDisplay } from '@/features/activities/utils/format'
import { themeColor } from '@/lib/themeColor'
import { kmToMiles } from '@/utils/units'

/** Mean Earth radius in metres. */
const EARTH_RADIUS_M = 6_371_008.8
/** Upper bound on plotted samples, so long routes stay responsive. */
export const MAX_PROFILE_SAMPLES = 400

/**
 * Great-circle distance between two points in metres.
 *
 * @param a - First point.
 * @param b - Second point.
 * @returns The distance in metres.
 */
export function haversineMeters(a: RoutePoint, b: RoutePoint): number {
  const toRad = (deg: number) => (deg * Math.PI) / 180
  const dLat = toRad(b.lat - a.lat)
  const dLng = toRad(b.lng - a.lng)
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLng / 2) ** 2
  return 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(h)))
}

/** An elevation sample at a distance along the route. */
export interface ProfileSample {
  /** Distance from the start in metres. */
  distance: number
  /** Elevation in metres. */
  elevation: number
}

/**
 * Elevation samples along a route, evenly spaced by distance and capped at
 * {@link MAX_PROFILE_SAMPLES}. Points without elevation are skipped.
 *
 * @param points - Route vertices in order.
 * @returns The samples, or an empty list when fewer than two points have
 *   elevation.
 */
export function buildProfileSamples(points: RoutePoint[]): ProfileSample[] {
  const known: ProfileSample[] = []
  let distance = 0
  points.forEach((point, index) => {
    const previous = points[index - 1]
    if (index > 0 && previous) {
      distance += haversineMeters(previous, point)
    }
    if (point.ele !== null) {
      known.push({ distance, elevation: point.ele })
    }
  })
  if (known.length < 2) {
    return []
  }
  if (known.length <= MAX_PROFILE_SAMPLES) {
    return known
  }

  // Linear interpolation onto an even distance grid.
  const distances = known.map((sample) => sample.distance)
  const elevations = known.map((sample) => sample.elevation)
  const total = distances[distances.length - 1] ?? 0
  const samples: ProfileSample[] = []
  let cursor = 0
  for (let i = 0; i < MAX_PROFILE_SAMPLES; i += 1) {
    const target = (total * i) / (MAX_PROFILE_SAMPLES - 1)
    while (cursor < distances.length - 2 && (distances[cursor + 1] ?? total) < target) {
      cursor += 1
    }
    const leftDistance = distances[cursor] ?? 0
    const rightDistance = distances[cursor + 1] ?? leftDistance
    const leftElevation = elevations[cursor] ?? 0
    const rightElevation = elevations[cursor + 1] ?? leftElevation
    const span = rightDistance - leftDistance
    const fraction = span > 0 ? Math.min(1, Math.max(0, (target - leftDistance) / span)) : 0
    samples.push({
      distance: target,
      elevation: leftElevation + fraction * (rightElevation - leftElevation),
    })
  }
  return samples
}

/**
 * Chart options for a route's elevation profile, in the viewer's units.
 *
 * @param points - Route vertices in order.
 * @param units - The viewer's unit system.
 * @param label - Series label (already localized or an i18n key).
 * @returns Render options, or `null` when the route has no elevation data.
 */
export function buildElevationProfile(
  points: RoutePoint[],
  units: Units,
  label: string,
): ChartRenderOptions | null {
  const samples = buildProfileSamples(points)
  if (samples.length === 0) {
    return null
  }
  const elevationUnit = units === 'imperial' ? 'ft' : 'm'
  return {
    kind: 'line',
    series: [
      {
        label,
        data: samples.map((sample) => Math.round(elevationToDisplay(sample.elevation, units))),
        color: themeColor('--color-goal'),
      },
    ],
    labels: samples.map((sample) => {
      const km = sample.distance / 1000
      return (units === 'imperial' ? kmToMiles(km) : km).toFixed(1)
    }),
    xUnit: units === 'imperial' ? 'mi' : 'km',
    valueFormat: (value) => `${Math.round(value)} ${elevationUnit}`,
    zoom: true,
  }
}
