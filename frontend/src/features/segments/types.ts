import type { Schemas } from '@/types'

/** Raw list payload for a segment (no geometry), as the backend sends it. */
export type SegmentSummaryDto = Schemas['SegmentSummary']
/** Raw detail payload for a segment, as the backend sends it. */
export type SegmentDetailDto = Schemas['SegmentRead']
/** Raw segment effort payload, as the backend sends it. */
export type SegmentEffortDto = Schemas['SegmentEffortRead']
/** Raw leaderboard page, as the backend sends it. */
export type SegmentLeaderboardDto = Schemas['SegmentLeaderboard']
/** Raw leaderboard row, as the backend sends it. */
export type SegmentLeaderboardEntryDto = Schemas['SegmentLeaderboardEntry']

/** Sport group a segment belongs to (`run`, `ride`, `e_ride`, `foot`). */
export type SportGroup = Schemas['SportGroup']
/** Whose efforts a leaderboard ranks. */
export type LeaderboardScope = Schemas['LeaderboardScope']
/** Time window of a leaderboard. */
export type LeaderboardPeriod = Schemas['LeaderboardPeriod']

/** Segment visibility codes (same as activities; followers-only is not offered). */
export const SEGMENT_VISIBILITY = {
  public: 0,
  private: 2,
} as const

/** A segment visibility code. */
export type SegmentVisibility = (typeof SEGMENT_VISIBILITY)[keyof typeof SEGMENT_VISIBILITY]

/**
 * Activity types matched against each sport group, mirroring the backend's
 * `SPORT_GROUP_ACTIVITY_TYPES`. Virtual and indoor types are absent on
 * purpose: their coordinates are synthetic or missing.
 */
export const SPORT_GROUP_ACTIVITY_TYPES: Record<SportGroup, readonly number[]> = {
  run: [1, 2, 34],
  ride: [4, 5, 6, 27, 29],
  e_ride: [35, 36],
  foot: [11, 12, 44],
}

/** Shortest segment the backend accepts per sport group, in metres. */
export const MIN_SEGMENT_DISTANCE_M: Record<SportGroup, number> = {
  run: 200,
  foot: 200,
  ride: 400,
  e_ride: 400,
}

/** Longest segment the backend accepts, in metres. */
export const MAX_SEGMENT_DISTANCE_M = 100_000

/** Fewest GPS points a segment slice may have. */
export const MIN_SEGMENT_POINTS = 10

/** A segment in a list (no geometry). */
export interface SegmentSummary {
  id: number
  userId: number | null
  name: string
  sportGroup: SportGroup
  visibility: number
  /** Length in metres. */
  distance: number
  /** Elevation gain in metres, when known. */
  elevationGain: number | null
  /** Average grade in percent, when known. */
  averageGrade: number | null
  city: string | null
  country: string | null
  isArchived: boolean
  effortCount: number
  athleteCount: number
  createdAt: string
}

/** One vertex of a segment: latitude, longitude and optional elevation (m). */
export interface SegmentPoint {
  lat: number
  lng: number
  ele: number | null
}

/** Full segment details for the detail page. */
export interface SegmentDetail extends SegmentSummary {
  description: string | null
  points: SegmentPoint[]
  elevationLoss: number | null
  /** Steepest 100 m stretch in percent, when known. */
  maximumGrade: number | null
  sourceActivityId: number | null
}

/** One pass of an activity over a segment. */
export interface SegmentEffort {
  id: number
  segmentId: number
  segmentName: string | null
  activityId: number
  userId: number
  startTime: string
  /** Elapsed seconds from start gate to end gate. */
  elapsedTime: number
  /** Distance covered on the segment in metres. */
  distance: number
  /** First index into the activity's lat/lon stream. */
  startIndex: number
  /** Last index into the activity's lat/lon stream (inclusive). */
  endIndex: number
  averageHr: number | null
  maxHr: number | null
  averagePower: number | null
  averageCadence: number | null
  /** Average speed in m/s. */
  averageSpeed: number | null
  isExcluded: boolean
  /** Rank among the owner's efforts today (1 = PR); owner only. */
  currentRank: number | null
  /** Rank at the time it was ridden or run (the medal); owner only. */
  historicalRank: number | null
  /** The owner's current PR on the segment in seconds; owner only. */
  prElapsedTime: number | null
}

/** One athlete's best visible effort on a segment. */
export interface LeaderboardEntry {
  rank: number
  userId: number
  userName: string | null
  username: string | null
  userPhotoPath: string | null
  effortId: number
  activityId: number
  /** Null when the athlete hides start times. */
  startTime: string | null
  elapsedTime: number
  averageHr: number | null
  averagePower: number | null
  averageSpeed: number | null
}

/** A page of a segment leaderboard. */
export interface Leaderboard {
  entries: LeaderboardEntry[]
  /** Number of ranked athletes. */
  total: number
  /** The viewer's own entry, when they have one. */
  viewerEntry: LeaderboardEntry | null
}

/** Input to create a segment from a slice of an activity. */
export interface SegmentCreateInput {
  activityId: number
  startIndex: number
  endIndex: number
  name: string
  description: string | null
  visibility: SegmentVisibility
}

/** Editable segment attributes (the geometry is immutable). */
export interface SegmentEditInput {
  name: string
  description: string | null
  visibility: SegmentVisibility
}
