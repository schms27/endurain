import type { Schemas } from '@/types'

/** Raw auto-import settings payload (snake_case wire shape). */
export type AutoImportSettingsDto = Schemas['AutoImportSettingsRead']

/** Update body for the auto-import settings. */
export type AutoImportSettingsUpdateDto = Schemas['AutoImportSettingsUpdate']

/** Scan intervals the backend accepts, in minutes. */
export const AUTO_IMPORT_INTERVALS = [15, 30, 60, 180, 360, 720, 1440] as const

/** The user's scheduled auto-import settings and last-run status. */
export interface AutoImportSettings {
  enabled: boolean
  intervalMinutes: number
  /** Import folder, relative to the server's activity files directory. */
  folder: string
  /** Supported files currently waiting in the folder. */
  pendingFiles: number
  /** ISO timestamp of the last scan, or `null` if it never ran. */
  lastRunAt: string | null
  lastRunImported: number
  lastRunFailed: number
}

/** Editable part of {@link AutoImportSettings}. */
export interface AutoImportSettingsInput {
  enabled: boolean
  intervalMinutes: number
}
