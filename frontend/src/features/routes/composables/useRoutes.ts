import { computed, type MaybeRefOrGetter, toValue } from 'vue'
import { storeToRefs } from 'pinia'
import { keepPreviousData, useQuery } from '@tanstack/vue-query'

import type { RouteDetail, RouteInput } from '@/features/routes/types'

import { queryKeys } from '@/services/queryKeys'
import { useInvalidatingMutation } from '@/composables/useInvalidatingMutation'
import { useAuthStore } from '@/features/auth/stores/auth'
import {
  createRouteFromActivity,
  deleteRoute,
  fetchRoute,
  fetchRoutes,
  importRouteFile,
  updateRoute,
} from '@/features/routes/services/routes'

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
