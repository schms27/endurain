import { computed, type MaybeRefOrGetter, toValue } from 'vue'
import { storeToRefs } from 'pinia'
import { keepPreviousData, useQuery } from '@tanstack/vue-query'

import type {
  LeaderboardPeriod,
  LeaderboardScope,
  SegmentCreateInput,
  SegmentDetail,
  SegmentEditInput,
  SegmentEffort,
} from '@/features/segments/types'

import { queryKeys } from '@/services/queryKeys'
import { useInvalidatingMutation } from '@/composables/useInvalidatingMutation'
import { useAuthStore } from '@/features/auth/stores/auth'
import {
  DEFAULT_PUBLIC_SERVER_SETTINGS,
  fetchPublicServerSettings,
} from '@/features/config/services/serverSettings'
import {
  createSegment,
  deleteSegment,
  fetchActivitySegmentEfforts,
  fetchLeaderboard,
  fetchMySegmentEfforts,
  fetchSegment,
  fetchSimilarSegments,
  rematchSegment,
  setEffortExcluded,
  type SegmentSlice,
  updateSegment,
} from '@/features/segments/services/segments'

/** Shared cache lifetime; server settings rarely change within a session. */
const SETTINGS_STALE_TIME = 5 * 60_000

/**
 * Whether segments are enabled on this instance, and whether regular users
 * may publish them. Reuses the cached public server settings query.
 *
 * @returns Reactive `enabled` and `publicCreationAdminsOnly` flags.
 */
export function useSegmentsSettings() {
  const query = useQuery({
    queryKey: queryKeys.public.serverSettings(),
    queryFn: fetchPublicServerSettings,
    placeholderData: DEFAULT_PUBLIC_SERVER_SETTINGS,
    retry: 1,
    staleTime: SETTINGS_STALE_TIME,
  })
  return {
    enabled: computed(() => query.data.value?.segments_enabled ?? true),
    publicCreationAdminsOnly: computed(
      () => query.data.value?.segments_public_creation === 'admins',
    ),
  }
}

/**
 * Whether a reactive id is a usable positive number.
 *
 * @param id - The id, or `null`.
 * @returns `true` for a finite positive id.
 */
function isValidId(id: number | null): id is number {
  return id !== null && Number.isFinite(id) && id > 0
}

/**
 * A single segment. Gated on a valid id and auth.
 *
 * @param id - The reactive segment id, or `null`.
 * @returns The TanStack query result for the segment.
 */
export function useSegmentQuery(id: MaybeRefOrGetter<number | null>) {
  const { isAuthenticated } = storeToRefs(useAuthStore())
  const segmentId = computed(() => toValue(id))

  return useQuery<SegmentDetail>({
    queryKey: computed(() => queryKeys.segments.detail(segmentId.value ?? -1)),
    queryFn: ({ signal }) => fetchSegment(segmentId.value as number, signal),
    enabled: computed(() => isAuthenticated.value && isValidId(segmentId.value)),
  })
}

/**
 * One page of a segment leaderboard. Keeps the previous page visible while
 * the next one loads.
 *
 * @param id - The reactive segment id, or `null`.
 * @param scope - Reactive leaderboard scope.
 * @param period - Reactive leaderboard period.
 * @param page - Reactive 1-based page number.
 * @param pageSize - Reactive records per page.
 * @returns The TanStack query result for the page.
 */
export function useSegmentLeaderboardQuery(
  id: MaybeRefOrGetter<number | null>,
  scope: MaybeRefOrGetter<LeaderboardScope>,
  period: MaybeRefOrGetter<LeaderboardPeriod>,
  page: MaybeRefOrGetter<number>,
  pageSize: MaybeRefOrGetter<number>,
) {
  const { isAuthenticated } = storeToRefs(useAuthStore())
  const segmentId = computed(() => toValue(id))
  const params = computed(() => ({
    scope: toValue(scope),
    period: toValue(period),
    page: toValue(page),
    numRecords: toValue(pageSize),
  }))

  return useQuery({
    queryKey: computed(() => queryKeys.segments.leaderboard(segmentId.value ?? -1, params.value)),
    queryFn: ({ signal }) => fetchLeaderboard(segmentId.value as number, params.value, signal),
    placeholderData: keepPreviousData,
    enabled: computed(() => isAuthenticated.value && isValidId(segmentId.value)),
  })
}

/**
 * The viewer's efforts on a segment.
 *
 * @param id - The reactive segment id, or `null`.
 * @returns The TanStack query result.
 */
export function useMySegmentEffortsQuery(id: MaybeRefOrGetter<number | null>) {
  const { isAuthenticated } = storeToRefs(useAuthStore())
  const segmentId = computed(() => toValue(id))

  return useQuery<SegmentEffort[]>({
    queryKey: computed(() => queryKeys.segments.myEfforts(segmentId.value ?? -1)),
    queryFn: ({ signal }) => fetchMySegmentEfforts(segmentId.value as number, signal),
    enabled: computed(() => isAuthenticated.value && isValidId(segmentId.value)),
  })
}

/**
 * Segment efforts of an activity. Gated on auth, a valid id and `enabled`
 * (e.g. segments switched on and the activity loaded).
 *
 * @param activityId - The reactive activity id, or `null`.
 * @param enabled - Reactive extra gate.
 * @returns The TanStack query result.
 */
export function useActivitySegmentEffortsQuery(
  activityId: MaybeRefOrGetter<number | null>,
  enabled: MaybeRefOrGetter<boolean>,
) {
  const { isAuthenticated } = storeToRefs(useAuthStore())
  const id = computed(() => toValue(activityId))

  return useQuery<SegmentEffort[]>({
    queryKey: computed(() => queryKeys.segments.activityEfforts(id.value ?? -1)),
    queryFn: ({ signal }) => fetchActivitySegmentEfforts(id.value as number, signal),
    enabled: computed(() => isAuthenticated.value && isValidId(id.value) && toValue(enabled)),
  })
}

/**
 * Existing segments that duplicate a proposed slice. Gated on `null` slices
 * (nothing to check yet), so callers debounce by passing `null` while the
 * user is still dragging.
 *
 * @param slice - The reactive proposed slice, or `null`.
 * @returns The TanStack query result.
 */
export function useSimilarSegmentsQuery(slice: MaybeRefOrGetter<SegmentSlice | null>) {
  const { isAuthenticated } = storeToRefs(useAuthStore())
  const current = computed(() => toValue(slice))

  return useQuery({
    queryKey: computed(() => queryKeys.segments.similar({ ...current.value })),
    queryFn: ({ signal }) => fetchSimilarSegments(current.value as SegmentSlice, signal),
    enabled: computed(() => isAuthenticated.value && current.value !== null),
    retry: false,
  })
}

/**
 * Creates a segment; invalidates the segments domain on settle.
 *
 * @returns The mutation.
 */
export function useCreateSegmentMutation() {
  return useInvalidatingMutation<SegmentDetail, SegmentCreateInput>({
    mutationKey: queryKeys.segments.all(),
    mutationFn: (input) => createSegment(input),
  })
}

/**
 * Updates a segment's name, description and visibility.
 *
 * @returns The mutation.
 */
export function useUpdateSegmentMutation() {
  return useInvalidatingMutation<SegmentDetail, { id: number; input: SegmentEditInput }>({
    mutationKey: queryKeys.segments.all(),
    mutationFn: ({ id, input }) => updateSegment(id, input),
  })
}

/**
 * Deletes a segment.
 *
 * @returns The mutation.
 */
export function useDeleteSegmentMutation() {
  return useInvalidatingMutation<void, number>({
    mutationKey: queryKeys.segments.all(),
    mutationFn: (id) => deleteSegment(id),
  })
}

/**
 * Queues a full rematch of a segment.
 *
 * @returns The mutation.
 */
export function useRematchSegmentMutation() {
  return useInvalidatingMutation<void, number>({
    mutationKey: queryKeys.segments.all(),
    mutationFn: (id) => rematchSegment(id),
  })
}

/**
 * Excludes or restores one of the user's efforts.
 *
 * @returns The mutation.
 */
export function useSetEffortExcludedMutation() {
  return useInvalidatingMutation<SegmentEffort, { id: number; isExcluded: boolean }>({
    mutationKey: queryKeys.segments.all(),
    mutationFn: ({ id, isExcluded }) => setEffortExcluded(id, isExcluded),
  })
}
