import type { ChartRenderOptions } from '@/composables/useChartProvider'
import type { GeoPoint } from '@/composables/useMapProvider'
import type { ActivityStream } from '@/features/activities/types'
import type { Units } from '@/features/activities/utils/format'
import type { SegmentEffort, SportGroup } from '@/features/segments/types'

import { formatHmsDuration, formatPace, formatSpeed } from '@/features/activities/utils/format'
import { haversineMeters } from '@/features/routes/utils/elevationProfile'
import { themeColor } from '@/lib/themeColor'
import {
  MAX_SEGMENT_DISTANCE_M,
  MIN_SEGMENT_DISTANCE_M,
  MIN_SEGMENT_POINTS,
  SPORT_GROUP_ACTIVITY_TYPES,
} from '@/features/segments/types'

/** Backend stream type of the lat/lon (GPS) stream. */
const MAP_STREAM_TYPE = 7

/**
 * Activity type used to format pace or speed for a sport group (runs and
 * walks show pace, rides show speed).
 */
const REPRESENTATIVE_ACTIVITY_TYPE: Record<SportGroup, number> = {
  run: 1,
  foot: 12,
  ride: 4,
  e_ride: 35,
}

/** A GPS point tagged with its position in the activity's lat/lon stream. */
export interface IndexedPoint extends GeoPoint {
  /** Index into the backend's lat/lon stream (what slices and efforts use). */
  index: number
}

/**
 * The sport group an activity type is matched in, if any.
 *
 * @param activityType - Numeric activity type.
 * @returns The sport group, or `null` for sports without segments (virtual,
 *   indoor, non-GPS).
 */
export function sportGroupOf(activityType: number): SportGroup | null {
  for (const [group, types] of Object.entries(SPORT_GROUP_ACTIVITY_TYPES)) {
    if (types.includes(activityType)) {
      return group as SportGroup
    }
  }
  return null
}

/**
 * Whether a sport group shows pace (runs, walks) rather than speed (rides).
 *
 * @param group - The sport group.
 * @returns `true` for pace.
 */
export function usesPace(group: SportGroup): boolean {
  return group === 'run' || group === 'foot'
}

/**
 * Formats an average speed as pace or speed for the sport group.
 *
 * @param metersPerSecond - Average speed in m/s, or null.
 * @param group - The sport group.
 * @param units - The viewer's unit system.
 * @returns The formatted `value unit` string, or `--`.
 */
export function formatEffortSpeed(
  metersPerSecond: number | null,
  group: SportGroup,
  units: Units,
): string {
  const activityType = REPRESENTATIVE_ACTIVITY_TYPE[group]
  if (metersPerSecond === null || metersPerSecond <= 0) {
    return '--'
  }
  const metric = usesPace(group)
    ? formatPace(1 / metersPerSecond, activityType, units)
    : formatSpeed(metersPerSecond, activityType, units)
  return `${metric.value} ${metric.unit}`
}

/**
 * The activity's GPS track with each point's original stream index. Points
 * without coordinates are skipped but never shift the indices, so a slice
 * picked here maps exactly onto the backend's `start_index`/`end_index`.
 *
 * @param streams - The activity's streams.
 * @returns Indexed points in recording order.
 */
export function extractIndexedTrack(streams: readonly ActivityStream[]): IndexedPoint[] {
  const mapStream =
    streams.find((stream) => stream.streamType === MAP_STREAM_TYPE) ??
    streams.find((stream) => stream.waypoints.some((waypoint) => typeof waypoint.lat === 'number'))
  if (!mapStream) {
    return []
  }
  const points: IndexedPoint[] = []
  mapStream.waypoints.forEach((waypoint, index) => {
    const { lat, lon } = waypoint
    if (typeof lat === 'number' && typeof lon === 'number' && Number.isFinite(lat + lon)) {
      points.push({ index, lat, lng: lon })
    }
  })
  return points
}

/**
 * Cumulative distance along a track, in metres.
 *
 * @param points - Track points in order.
 * @returns One distance per point; the first is 0.
 */
export function cumulativeDistances(points: readonly GeoPoint[]): number[] {
  const distances: number[] = []
  let total = 0
  points.forEach((point, position) => {
    const previous = points[position - 1]
    if (previous) {
      total += haversineMeters({ ...previous, ele: null }, { ...point, ele: null })
    }
    distances.push(total)
  })
  return distances
}

/**
 * The part of a track between two stream indices (inclusive), for drawing an
 * effort or a proposed segment over the activity map.
 *
 * @param track - Indexed track points.
 * @param startIndex - First stream index.
 * @param endIndex - Last stream index.
 * @returns The points in range, without their indices.
 */
export function sliceTrack(
  track: readonly IndexedPoint[],
  startIndex: number,
  endIndex: number,
): GeoPoint[] {
  return track
    .filter((point) => point.index >= startIndex && point.index <= endIndex)
    .map(({ lat, lng }) => ({ lat, lng }))
}

/** Why a proposed segment slice would be rejected by the backend. */
export type SliceProblem = 'tooFewPoints' | 'tooShort' | 'tooLong'

/**
 * Client-side mirror of the backend's slice checks, for instant feedback in
 * the create dialog (the backend re-validates, including the GPS gap check).
 *
 * @param pointCount - GPS points in the slice.
 * @param distance - Slice length in metres.
 * @param group - The activity's sport group.
 * @returns The first problem found, or `null` when the slice looks valid.
 */
export function sliceProblem(
  pointCount: number,
  distance: number,
  group: SportGroup,
): SliceProblem | null {
  if (pointCount < MIN_SEGMENT_POINTS) {
    return 'tooFewPoints'
  }
  if (distance < MIN_SEGMENT_DISTANCE_M[group]) {
    return 'tooShort'
  }
  if (distance > MAX_SEGMENT_DISTANCE_M) {
    return 'tooLong'
  }
  return null
}

/**
 * Signed difference to a reference time as `+M:SS` / `-M:SS`.
 *
 * @param elapsed - The effort's elapsed seconds.
 * @param reference - The reference (e.g. the PR) in seconds.
 * @returns The formatted delta; `+00:00` when equal.
 */
export function formatTimeDelta(elapsed: number, reference: number): string {
  const delta = Math.round(elapsed) - Math.round(reference)
  return `${delta < 0 ? '-' : '+'}${formatHmsDuration(Math.abs(delta))}`
}

/** Medal tiers shown for an effort's historical rank. */
export type Medal = 'gold' | 'silver' | 'bronze'

/**
 * The medal for a rank, Strava style: PR, 2nd and 3rd best time.
 *
 * @param rank - A 1-based rank, or null.
 * @returns The medal, or `null` outside the top three.
 */
export function medalFor(rank: number | null): Medal | null {
  if (rank === 1) {
    return 'gold'
  }
  if (rank === 2) {
    return 'silver'
  }
  if (rank === 3) {
    return 'bronze'
  }
  return null
}

/**
 * Chart options for a user's effort history: elapsed time per effort, oldest
 * first, so progression on a regular climb reads left to right.
 *
 * @param efforts - The user's efforts (excluded ones are dropped).
 * @param label - Series label.
 * @param formatDate - Formats an effort's ISO start time for the x-axis.
 * @returns Render options, or `null` with fewer than two efforts.
 */
export function buildEffortHistoryChart(
  efforts: readonly SegmentEffort[],
  label: string,
  formatDate: (iso: string) => string,
): ChartRenderOptions | null {
  const included = efforts
    .filter((effort) => !effort.isExcluded)
    .sort((a, b) => a.startTime.localeCompare(b.startTime))
  if (included.length < 2) {
    return null
  }
  return {
    kind: 'line',
    series: [
      {
        label,
        data: included.map((effort) => Math.round(effort.elapsedTime)),
        color: themeColor('--color-effort'),
      },
    ],
    labels: included.map((effort) => formatDate(effort.startTime)),
    valueFormat: (value) => formatHmsDuration(value),
    invertY: true,
  }
}
