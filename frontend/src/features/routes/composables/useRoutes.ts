import { computed, type MaybeRefOrGetter, toValue } from 'vue'
import { storeToRefs } from 'pinia'
import { keepPreviousData, useQuery } from '@tanstack/vue-query'

import type { RouteDetail, RouteInput, RouteSharingInput } from '@/features/routes/types'

import { queryKeys } from '@/services/queryKeys'
import { useInvalidatingMutation } from '@/composables/useInvalidatingMutation'
import { useAuthStore } from '@/features/auth/stores/auth'
import {
  copyRoute,
  createRouteFromActivity,
  createRouteShareToken,
  deleteRoute,
  fetchRoute,
  fetchRouteHomeWarning,
  fetchRoutes,
  fetchSharedRoute,
  fetchUserRoutes,
  importRouteFile,
  revokeRouteShareToken,
  type SharedRouteRef,
  updateRoute,
  updateRouteSharing,
} from '@/features/routes/services/routes'

/**
 * One page of the routes on a user's profile that the viewer can see.
 *
 * @param userId - Reactive profile user id, or `null`.
 * @param page - Reactive 1-based page number.
 * @param pageSize - Reactive records per page.
 * @param enabled - Reactive gate (e.g. only while the tab is open).
 * @returns The TanStack query result for the current page.
 */
export function useUserRoutesQuery(
  userId: MaybeRefOrGetter<number | null>,
  page: MaybeRefOrGetter<number>,
  pageSize: MaybeRefOrGetter<number>,
  enabled: MaybeRefOrGetter<boolean> = true,
) {
  const { isAuthenticated } = storeToRefs(useAuthStore())
  const params = computed(() => ({ page: toValue(page), numRecords: toValue(pageSize) }))
  const id = computed(() => toValue(userId))

  return useQuery({
    queryKey: computed(() => queryKeys.routes.user(id.value ?? -1, params.value)),
    queryFn: ({ signal }) => fetchUserRoutes(id.value as number, params.value, signal),
    placeholderData: keepPreviousData,
    enabled: computed(() => isAuthenticated.value && id.value !== null && toValue(enabled)),
  })
}

/**
 * A route opened through its share link, or anonymously by public id. Works
 * without auth.
 *
 * @param ref - Reactive token or public id, or `null` to disable.
 * @returns The TanStack query result for the route.
 */
export function useSharedRouteQuery(ref: MaybeRefOrGetter<SharedRouteRef | null>) {
  const current = computed(() => toValue(ref))
  const key = computed(() => {
    const value = current.value
    if (!value) {
      return ''
    }
    return 'token' in value ? `token:${value.token}` : `id:${value.publicId}`
  })

  return useQuery({
    queryKey: computed(() => queryKeys.routes.shared(key.value)),
    queryFn: ({ signal }) => fetchSharedRoute(current.value as SharedRouteRef, signal),
    enabled: computed(() => current.value !== null),
    retry: false,
  })
}

/**
 * The owner's home-location warning for a route.
 *
 * @param id - Reactive route id, or `null`.
 * @param enabled - Reactive gate (e.g. only while the share dialog is open).
 * @returns The TanStack query result.
 */
export function useRouteHomeWarningQuery(
  id: MaybeRefOrGetter<number | null>,
  enabled: MaybeRefOrGetter<boolean>,
) {
  const routeId = computed(() => toValue(id))

  return useQuery({
    queryKey: computed(() => queryKeys.routes.homeWarning(routeId.value ?? -1)),
    queryFn: ({ signal }) => fetchRouteHomeWarning(routeId.value as number, signal),
    enabled: computed(() => routeId.value !== null && toValue(enabled)),
  })
}

/**
 * Saves a copy of a visible or shared route to the viewer's library.
 *
 * @returns The mutation.
 */
export function useCopyRouteMutation() {
  return useInvalidatingMutation<RouteDetail, { id: number } | { token: string }>({
    mutationKey: queryKeys.routes.all(),
    mutationFn: (source) => copyRoute(source),
  })
}

/**
 * Updates a route's visibility and endpoint trimming.
 *
 * @returns The mutation.
 */
export function useUpdateRouteSharingMutation() {
  return useInvalidatingMutation<RouteDetail, { id: number; input: RouteSharingInput }>({
    mutationKey: queryKeys.routes.all(),
    mutationFn: ({ id, input }) => updateRouteSharing(id, input),
  })
}

/**
 * Creates or rotates a route's share link.
 *
 * @returns The mutation.
 */
export function useCreateRouteShareTokenMutation() {
  return useInvalidatingMutation<RouteDetail, number>({
    mutationKey: queryKeys.routes.all(),
    mutationFn: (id) => createRouteShareToken(id),
  })
}

/**
 * Revokes a route's share link.
 *
 * @returns The mutation.
 */
export function useRevokeRouteShareTokenMutation() {
  return useInvalidatingMutation<RouteDetail, number>({
    mutationKey: queryKeys.routes.all(),
    mutationFn: (id) => revokeRouteShareToken(id),
  })
}

/**
 * One page of the user's routes. Keyed on page, size and search term; keeps
 * the previous page visible while the next one loads. Gated on auth.
 *
 * @param page - Reactive 1-based page number.
 * @param pageSize - Reactive records per page.
 * @param search - Reactive (debounced) name search term.
 * @returns The TanStack query result for the current page.
 */
export function useRoutesQuery(
  page: MaybeRefOrGetter<number>,
  pageSize: MaybeRefOrGetter<number>,
  search: MaybeRefOrGetter<string>,
) {
  const { isAuthenticated } = storeToRefs(useAuthStore())
  const params = computed(() => ({
    page: toValue(page),
    numRecords: toValue(pageSize),
    search: toValue(search).trim(),
  }))

  return useQuery({
    queryKey: computed(() => queryKeys.routes.list(params.value)),
    queryFn: ({ signal }) => fetchRoutes(params.value, signal),
    placeholderData: keepPreviousData,
    enabled: isAuthenticated,
  })
}

/**
 * A single route. Gated on a valid id and auth.
 *
 * @param id - The reactive route id, or `null`.
 * @returns The TanStack query result for the route.
 */
export function useRouteQuery(id: MaybeRefOrGetter<number | null>) {
  const { isAuthenticated } = storeToRefs(useAuthStore())
  const routeId = computed(() => toValue(id))

  return useQuery<RouteDetail>({
    queryKey: computed(() => queryKeys.routes.detail(routeId.value ?? -1)),
    queryFn: ({ signal }) => fetchRoute(routeId.value as number, signal),
    enabled: computed(
      () => isAuthenticated.value && routeId.value !== null && Number.isFinite(routeId.value),
    ),
  })
}

/**
 * Imports one route file; invalidates the routes domain on settle.
 *
 * @returns The mutation.
 */
export function useImportRouteMutation() {
  return useInvalidatingMutation<RouteDetail, File>({
    mutationKey: queryKeys.routes.all(),
    mutationFn: (file) => importRouteFile(file),
  })
}

/**
 * Saves an activity as a route; invalidates the routes domain on settle.
 *
 * @returns The mutation.
 */
export function useCreateRouteFromActivityMutation() {
  return useInvalidatingMutation<RouteDetail, number>({
    mutationKey: queryKeys.routes.all(),
    mutationFn: (activityId) => createRouteFromActivity(activityId),
  })
}

/**
 * Updates a route's name and description.
 *
 * @returns The mutation.
 */
export function useUpdateRouteMutation() {
  return useInvalidatingMutation<RouteDetail, { id: number; input: RouteInput }>({
    mutationKey: queryKeys.routes.all(),
    mutationFn: ({ id, input }) => updateRoute(id, input),
  })
}

/**
 * Deletes a route.
 *
 * @returns The mutation.
 */
export function useDeleteRouteMutation() {
  return useInvalidatingMutation<void, number>({
    mutationKey: queryKeys.routes.all(),
    mutationFn: (id) => deleteRoute(id),
  })
}
