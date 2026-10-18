import { storeToRefs } from 'pinia'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'

import type { AutoImportSettings, AutoImportSettingsInput } from '@/features/import/types'

import { queryKeys } from '@/services/queryKeys'
import { useAuthStore } from '@/features/auth/stores/auth'
import {
  bulkImportActivities,
  fetchAutoImportSettings,
  importStravaActivities,
  importStravaBikes,
  importStravaShoes,
  runAutoImportNow,
  updateAutoImportSettings,
} from '@/features/import/services/import'

/** Bulk-imports activity files from the server's bulk-import folder (background). */
export function useBulkImportMutation() {
  return useMutation<void, Error, void>({ mutationFn: () => bulkImportActivities() })
}

/** Queues activities from a Strava bulk export for import (background). */
export function useImportStravaActivitiesMutation() {
  return useMutation<void, Error, void>({ mutationFn: () => importStravaActivities() })
}

/** Imports Strava bikes (synchronous); refreshes gear lists on success. */
export function useImportStravaBikesMutation() {
  const client = useQueryClient()
  return useMutation<void, Error, void>({
    mutationFn: () => importStravaBikes(),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: queryKeys.gears.all() })
    },
  })
}

/** Imports Strava shoes (synchronous); refreshes gear lists on success. */
export function useImportStravaShoesMutation() {
  const client = useQueryClient()
  return useMutation<void, Error, void>({
    mutationFn: () => importStravaShoes(),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: queryKeys.gears.all() })
    },
  })
}

/** The user's scheduled auto-import settings, gated on authentication. */
export function useAutoImportSettingsQuery() {
  const { isAuthenticated } = storeToRefs(useAuthStore())
  return useQuery({
    queryKey: queryKeys.profile.autoImport(),
    queryFn: ({ signal }) => fetchAutoImportSettings(signal),
    enabled: isAuthenticated,
  })
}

/** Saves the auto-import settings and writes the result into the cache. */
export function useUpdateAutoImportSettingsMutation() {
  const client = useQueryClient()
  return useMutation<AutoImportSettings, Error, AutoImportSettingsInput>({
    mutationFn: (input) => updateAutoImportSettings(input),
    onSuccess: (saved) => {
      client.setQueryData(queryKeys.profile.autoImport(), saved)
    },
  })
}

/** Starts a scan of the auto-import folder now (background). */
export function useRunAutoImportMutation() {
  return useMutation<void, Error, void>({ mutationFn: () => runAutoImportNow() })
}
