import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '@/services/http'
import {
  bulkImportActivities,
  fetchAutoImportSettings,
  importStravaActivities,
  importStravaBikes,
  importStravaShoes,
  mapAutoImportSettings,
  runAutoImportNow,
  updateAutoImportSettings,
} from '@/features/import/services/import'

vi.mock('@/services/http', () => ({
  apiFetch: vi.fn<typeof apiFetch>(),
}))

describe('import service', () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset()
    vi.mocked(apiFetch).mockResolvedValue(undefined)
  })

  it('bulkImportActivities POSTs the bulk-import path (void)', async () => {
    await bulkImportActivities()
    expect(apiFetch).toHaveBeenCalledWith('/activities/create/bulkimport', {
      method: 'POST',
      responseType: 'void',
    })
  })

  it('importStravaActivities POSTs the Strava activities import path (void)', async () => {
    await importStravaActivities()
    expect(apiFetch).toHaveBeenCalledWith('/strava/import/activities', {
      method: 'POST',
      responseType: 'void',
    })
  })

  it('importStravaBikes POSTs the Strava bikes import path (void)', async () => {
    await importStravaBikes()
    expect(apiFetch).toHaveBeenCalledWith('/strava/import/bikes', {
      method: 'POST',
      responseType: 'void',
    })
  })

  it('importStravaShoes POSTs the Strava shoes import path (void)', async () => {
    await importStravaShoes()
    expect(apiFetch).toHaveBeenCalledWith('/strava/import/shoes', {
      method: 'POST',
      responseType: 'void',
    })
  })
})

const autoImportDto = {
  enabled: true,
  interval_minutes: 30,
  folder: 'auto_import/alice',
  pending_files: 2,
  last_run_at: '2026-10-18T10:00:00Z',
  last_run_imported: 3,
  last_run_failed: 1,
}

describe('auto import service', () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset()
  })

  it('mapAutoImportSettings normalizes the wire shape', () => {
    expect(mapAutoImportSettings(autoImportDto)).toEqual({
      enabled: true,
      intervalMinutes: 30,
      folder: 'auto_import/alice',
      pendingFiles: 2,
      lastRunAt: '2026-10-18T10:00:00Z',
      lastRunImported: 3,
      lastRunFailed: 1,
    })
  })

  it('mapAutoImportSettings maps a missing last run to null', () => {
    const { last_run_at: _lastRunAt, ...neverRun } = autoImportDto
    expect(mapAutoImportSettings(neverRun).lastRunAt).toBeNull()
  })

  it('fetchAutoImportSettings GETs the profile path', async () => {
    vi.mocked(apiFetch).mockResolvedValue(autoImportDto)
    const signal = new AbortController().signal

    const result = await fetchAutoImportSettings(signal)

    expect(apiFetch).toHaveBeenCalledWith('/profile/auto_import', { signal })
    expect(result.intervalMinutes).toBe(30)
  })

  it('updateAutoImportSettings PUTs the snake_case body', async () => {
    vi.mocked(apiFetch).mockResolvedValue(autoImportDto)

    await updateAutoImportSettings({ enabled: true, intervalMinutes: 30 })

    expect(apiFetch).toHaveBeenCalledWith('/profile/auto_import', {
      method: 'PUT',
      body: JSON.stringify({ enabled: true, interval_minutes: 30 }),
    })
  })

  it('runAutoImportNow POSTs the run path (void)', async () => {
    vi.mocked(apiFetch).mockResolvedValue(undefined)

    await runAutoImportNow()

    expect(apiFetch).toHaveBeenCalledWith('/profile/auto_import/run', {
      method: 'POST',
      responseType: 'void',
    })
  })
})
