import type {
  AutoImportSettings,
  AutoImportSettingsDto,
  AutoImportSettingsInput,
  AutoImportSettingsUpdateDto,
} from '@/features/import/types'

import { apiFetch } from '@/services/http'

/**
 * Triggers a server-side bulk import of plain activity files placed in the
 * backend's `data/activity_files/bulk_import` folder. The work runs in the
 * background; progress arrives over the realtime channel.
 *
 * @throws {HttpError} When the request fails.
 */
export async function bulkImportActivities(): Promise<void> {
  await apiFetch('/activities/create/bulkimport', { method: 'POST', responseType: 'void' })
}

/**
 * Queues a server-side import of activities from a Strava bulk export placed in
 * the backend's `data/activity_files/strava_import` folder (background work).
 *
 * @throws {HttpError} When the request fails.
 */
export async function importStravaActivities(): Promise<void> {
  await apiFetch('/strava/import/activities', { method: 'POST', responseType: 'void' })
}

/**
 * Imports bikes from a Strava bulk export's gear CSV (completes synchronously).
 *
 * @throws {HttpError} When the request fails.
 */
export async function importStravaBikes(): Promise<void> {
  await apiFetch('/strava/import/bikes', { method: 'POST', responseType: 'void' })
}

/**
 * Imports shoes from a Strava bulk export's gear CSV (completes synchronously).
 *
 * @throws {HttpError} When the request fails.
 */
export async function importStravaShoes(): Promise<void> {
  await apiFetch('/strava/import/shoes', { method: 'POST', responseType: 'void' })
}

/**
 * Maps a raw auto-import settings payload to the clean {@link AutoImportSettings} model.
 *
 * @param dto - Raw settings payload from the backend.
 * @returns The normalized settings model.
 */
export function mapAutoImportSettings(dto: AutoImportSettingsDto): AutoImportSettings {
  return {
    enabled: dto.enabled,
    intervalMinutes: dto.interval_minutes,
    folder: dto.folder,
    pendingFiles: dto.pending_files,
    lastRunAt: dto.last_run_at ?? null,
    lastRunImported: dto.last_run_imported,
    lastRunFailed: dto.last_run_failed,
  }
}

/**
 * Fetches the user's scheduled auto-import settings and last-run status.
 *
 * @param signal - Optional abort signal from the query.
 * @returns The settings (server defaults when never saved).
 * @throws {HttpError} When the request fails.
 */
export async function fetchAutoImportSettings(signal?: AbortSignal): Promise<AutoImportSettings> {
  const dto = await apiFetch<AutoImportSettingsDto>('/profile/auto_import', { signal })
  return mapAutoImportSettings(dto)
}

/**
 * Saves the user's scheduled auto-import settings.
 *
 * @param input - Whether the schedule is on, and its interval.
 * @returns The saved settings.
 * @throws {HttpError} When the request fails.
 */
export async function updateAutoImportSettings(
  input: AutoImportSettingsInput,
): Promise<AutoImportSettings> {
  const body: AutoImportSettingsUpdateDto = {
    enabled: input.enabled,
    interval_minutes: input.intervalMinutes,
  }
  const dto = await apiFetch<AutoImportSettingsDto>('/profile/auto_import', {
    method: 'PUT',
    body: JSON.stringify(body),
  })
  return mapAutoImportSettings(dto)
}

/**
 * Starts a background scan of the user's auto-import folder right away.
 *
 * @throws {HttpError} When the request fails (409 if a scan is already running).
 */
export async function runAutoImportNow(): Promise<void> {
  await apiFetch('/profile/auto_import/run', { method: 'POST', responseType: 'void' })
}
