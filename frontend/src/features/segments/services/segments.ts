import type {
  Leaderboard,
  LeaderboardEntry,
  LeaderboardPeriod,
  LeaderboardScope,
  SegmentCreateInput,
  SegmentDetail,
  SegmentDetailDto,
  SegmentEditInput,
  SegmentEffort,
  SegmentEffortDto,
  SegmentLeaderboardDto,
  SegmentLeaderboardEntryDto,
  SegmentSummary,
  SegmentSummaryDto,
} from '@/features/segments/types'

import { apiFetch } from '@/services/http'

/**
 * Maps a list payload to the clean {@link SegmentSummary} model.
 *
 * @param dto - Raw segment summary.
 * @returns The normalized segment summary.
 */
export function mapSegmentSummary(dto: SegmentSummaryDto): SegmentSummary {
  return {
    id: dto.id,
    userId: dto.user_id ?? null,
    name: dto.name,
    sportGroup: dto.sport_group,
    visibility: dto.visibility,
    distance: dto.distance,
    elevationGain: dto.elevation_gain ?? null,
    averageGrade: dto.average_grade ?? null,
    city: dto.city ?? null,
    country: dto.country ?? null,
    isArchived: dto.is_archived,
    effortCount: dto.effort_count,
    athleteCount: dto.athlete_count,
    createdAt: dto.created_at,
  }
}

/**
 * Maps a detail payload to the clean {@link SegmentDetail} model, turning the
 * `[lat, lon, ele]` geometry into named points.
 *
 * @param dto - Raw segment detail.
 * @returns The normalized segment detail.
 */
export function mapSegmentDetail(dto: SegmentDetailDto): SegmentDetail {
  return {
    ...mapSegmentSummary(dto),
    description: dto.description ?? null,
    points: dto.geometry
      .filter((point) => typeof point[0] === 'number' && typeof point[1] === 'number')
      .map((point) => ({
        lat: point[0] as number,
        lng: point[1] as number,
        ele: typeof point[2] === 'number' ? point[2] : null,
      })),
    elevationLoss: dto.elevation_loss ?? null,
    maximumGrade: dto.maximum_grade ?? null,
    sourceActivityId: dto.source_activity_id ?? null,
  }
}

/**
 * Maps an effort payload to the clean {@link SegmentEffort} model.
 *
 * @param dto - Raw segment effort.
 * @returns The normalized effort.
 */
export function mapSegmentEffort(dto: SegmentEffortDto): SegmentEffort {
  return {
    id: dto.id,
    segmentId: dto.segment_id,
    segmentName: dto.segment_name ?? null,
    activityId: dto.activity_id,
    userId: dto.user_id,
    startTime: dto.start_time,
    elapsedTime: dto.elapsed_time,
    distance: dto.distance,
    startIndex: dto.start_index,
    endIndex: dto.end_index,
    averageHr: dto.average_hr ?? null,
    maxHr: dto.max_hr ?? null,
    averagePower: dto.average_power ?? null,
    averageCadence: dto.average_cad ?? null,
    averageSpeed: dto.average_speed ?? null,
    isExcluded: dto.is_excluded,
    currentRank: dto.current_rank ?? null,
    historicalRank: dto.historical_rank ?? null,
    prElapsedTime: dto.pr_elapsed_time ?? null,
  }
}

/**
 * Maps a leaderboard row to the clean {@link LeaderboardEntry} model.
 *
 * @param dto - Raw leaderboard row.
 * @returns The normalized entry.
 */
export function mapLeaderboardEntry(dto: SegmentLeaderboardEntryDto): LeaderboardEntry {
  return {
    rank: dto.rank,
    userId: dto.user_id,
    userName: dto.user_name ?? null,
    username: dto.username ?? null,
    userPhotoPath: dto.user_photo_path ?? null,
    effortId: dto.effort_id,
    activityId: dto.activity_id,
    startTime: dto.start_time ?? null,
    elapsedTime: dto.elapsed_time,
    averageHr: dto.average_hr ?? null,
    averagePower: dto.average_power ?? null,
    averageSpeed: dto.average_speed ?? null,
  }
}

/**
 * Maps a leaderboard page to the clean {@link Leaderboard} model.
 *
 * @param dto - Raw leaderboard page.
 * @returns The normalized leaderboard.
 */
export function mapLeaderboard(dto: SegmentLeaderboardDto): Leaderboard {
  return {
    entries: dto.entries.map(mapLeaderboardEntry),
    total: dto.total,
    viewerEntry: dto.viewer_entry ? mapLeaderboardEntry(dto.viewer_entry) : null,
  }
}

/**
 * Fetches a single segment.
 *
 * @param id - Segment id.
 * @param signal - Optional abort signal.
 * @returns The segment detail.
 * @throws {HttpError} When the request fails (404 when missing or not visible).
 */
export async function fetchSegment(id: number, signal?: AbortSignal): Promise<SegmentDetail> {
  return mapSegmentDetail(await apiFetch<SegmentDetailDto>(`/segments/${id}`, { signal }))
}

/** Leaderboard request filters. */
export interface LeaderboardParams {
  scope: LeaderboardScope
  period: LeaderboardPeriod
  /** 1-based page number. */
  page: number
  /** Page size. */
  numRecords: number
}

/**
 * Fetches one page of a segment leaderboard.
 *
 * @param id - Segment id.
 * @param params - Scope, period and pagination.
 * @param signal - Optional abort signal.
 * @returns The leaderboard page with the viewer's own entry.
 * @throws {HttpError} When the request fails.
 */
export async function fetchLeaderboard(
  id: number,
  { scope, period, page, numRecords }: LeaderboardParams,
  signal?: AbortSignal,
): Promise<Leaderboard> {
  const params = new URLSearchParams({
    scope,
    period,
    page_number: String(page),
    num_records: String(numRecords),
  })
  const dto = await apiFetch<SegmentLeaderboardDto>(
    `/segments/${id}/leaderboard?${params.toString()}`,
    { signal },
  )
  return mapLeaderboard(dto)
}

/**
 * Fetches the viewer's own efforts on a segment, fastest first.
 *
 * @param id - Segment id.
 * @param signal - Optional abort signal.
 * @returns The viewer's efforts with personal ranks.
 * @throws {HttpError} When the request fails.
 */
export async function fetchMySegmentEfforts(
  id: number,
  signal?: AbortSignal,
): Promise<SegmentEffort[]> {
  const dtos = await apiFetch<SegmentEffortDto[]>(`/segments/${id}/efforts`, { signal })
  return dtos.map(mapSegmentEffort)
}

/**
 * Fetches the segment efforts of an activity the viewer can see.
 *
 * @param activityId - Activity id.
 * @param signal - Optional abort signal.
 * @returns Efforts in start-time order (with personal ranks for the owner).
 * @throws {HttpError} When the request fails.
 */
export async function fetchActivitySegmentEfforts(
  activityId: number,
  signal?: AbortSignal,
): Promise<SegmentEffort[]> {
  const dtos = await apiFetch<SegmentEffortDto[]>(`/segment_efforts/activity_id/${activityId}`, {
    signal,
  })
  return dtos.map(mapSegmentEffort)
}

/** A proposed slice of an activity. */
export interface SegmentSlice {
  activityId: number
  startIndex: number
  endIndex: number
}

/**
 * Fetches existing segments that duplicate a proposed slice.
 *
 * @param slice - The proposed activity slice.
 * @param signal - Optional abort signal.
 * @returns Similar segments, closest length first.
 * @throws {HttpError} When the request fails (400 for an invalid slice).
 */
export async function fetchSimilarSegments(
  { activityId, startIndex, endIndex }: SegmentSlice,
  signal?: AbortSignal,
): Promise<SegmentSummary[]> {
  const params = new URLSearchParams({
    activity_id: String(activityId),
    start_index: String(startIndex),
    end_index: String(endIndex),
  })
  const dtos = await apiFetch<SegmentSummaryDto[]>(`/segments/similar?${params.toString()}`, {
    signal,
  })
  return dtos.map(mapSegmentSummary)
}

/**
 * Creates a segment from a slice of one of the user's activities. Matching
 * against existing activities runs in the background.
 *
 * @param input - The slice and segment attributes.
 * @returns The created segment.
 * @throws {HttpError} When the request fails.
 */
export async function createSegment(input: SegmentCreateInput): Promise<SegmentDetail> {
  const dto = await apiFetch<SegmentDetailDto>('/segments', {
    method: 'POST',
    body: JSON.stringify({
      activity_id: input.activityId,
      start_index: input.startIndex,
      end_index: input.endIndex,
      name: input.name,
      description: input.description,
      visibility: input.visibility,
    }),
  })
  return mapSegmentDetail(dto)
}

/**
 * Updates a segment's name, description and visibility.
 *
 * @param id - Segment id.
 * @param input - New values.
 * @returns The updated segment.
 * @throws {HttpError} When the request fails.
 */
export async function updateSegment(id: number, input: SegmentEditInput): Promise<SegmentDetail> {
  const dto = await apiFetch<SegmentDetailDto>(`/segments/${id}`, {
    method: 'PUT',
    body: JSON.stringify({
      name: input.name,
      description: input.description,
      visibility: input.visibility,
    }),
  })
  return mapSegmentDetail(dto)
}

/**
 * Deletes a segment and its efforts.
 *
 * @param id - Segment id.
 * @throws {HttpError} When the request fails.
 */
export async function deleteSegment(id: number): Promise<void> {
  await apiFetch<void>(`/segments/${id}`, { method: 'DELETE', responseType: 'void' })
}

/**
 * Queues a full rematch of a segment against every candidate activity.
 *
 * @param id - Segment id.
 * @throws {HttpError} When the request fails.
 */
export async function rematchSegment(id: number): Promise<void> {
  await apiFetch<void>(`/segments/${id}/rematch`, { method: 'POST', responseType: 'void' })
}

/**
 * Excludes one of the user's efforts (a GPS glitch, a car ride) or restores it.
 *
 * @param id - Effort id.
 * @param isExcluded - The new exclusion state.
 * @returns The updated effort.
 * @throws {HttpError} When the request fails.
 */
export async function setEffortExcluded(id: number, isExcluded: boolean): Promise<SegmentEffort> {
  const dto = await apiFetch<SegmentEffortDto>(`/segment_efforts/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ is_excluded: isExcluded }),
  })
  return mapSegmentEffort(dto)
}
