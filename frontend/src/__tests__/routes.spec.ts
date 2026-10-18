import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { RouteDetailDto, RoutePoint } from '@/features/routes/types'

import { apiFetch } from '@/services/http'
import {
  assertValidRouteFile,
  copyRoute,
  createRouteFromActivity,
  createRouteShareToken,
  deleteRoute,
  exportRouteGpx,
  exportSharedRouteGpx,
  fetchRoute,
  fetchRouteHomeWarning,
  fetchRoutes,
  fetchSharedRoute,
  fetchUserRoutes,
  importRouteFile,
  mapRouteDetail,
  revokeRouteShareToken,
  RouteFileValidationError,
  routeShareUrl,
  updateRoute,
  updateRouteSharing,
} from '@/features/routes/services/routes'
import { MAX_ROUTE_FILE_BYTES } from '@/features/routes/types'
import {
  buildElevationProfile,
  buildProfileSamples,
  haversineMeters,
  MAX_PROFILE_SAMPLES,
} from '@/features/routes/utils/elevationProfile'

vi.mock('@/services/http', () => ({
  apiFetch: vi.fn<typeof apiFetch>(),
}))

const routeDto: RouteDetailDto = {
  id: 7,
  user_id: 1,
  name: 'Castle loop',
  activity_type: null,
  source: 1,
  visibility: 2,
  distance: 1234.5,
  elevation_gain: 40,
  elevation_loss: 38,
  is_loop: true,
  city: 'Lisbon',
  country: null,
  created_at: '2024-01-01T00:00:00Z',
  description: null,
  source_activity_id: null,
  source_route_id: null,
  original_filename: 'castle.gpx',
  share_token: 'secret-token',
  hide_endpoints_m: 200,
  is_owner: true,
  geometry: [
    [38.7, -9.1, 10],
    [38.71, -9.1, null],
    [null, -9.1, 5],
  ],
  waypoints: [{ name: 'Fountain', kind: 'water', lat: 38.705, lon: -9.1 }],
  elevation_min: 10,
  elevation_max: 50,
  updated_at: '2024-01-01T00:00:00Z',
}

/** Runs `action` and returns what it threw, or `null`. */
function captureError(action: () => void): unknown {
  try {
    action()
    return null
  } catch (err) {
    return err
  }
}

function file(name: string, size: number): File {
  const created = new File(['x'], name)
  Object.defineProperty(created, 'size', { value: size })
  return created
}

describe('routes service', () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset()
  })

  it('maps geometry and points of interest, dropping invalid vertices', () => {
    const route = mapRouteDetail(routeDto)
    expect(route.points).toEqual([
      { lat: 38.7, lng: -9.1, ele: 10 },
      { lat: 38.71, lng: -9.1, ele: null },
    ])
    expect(route.pois).toEqual([
      { name: 'Fountain', description: null, kind: 'water', lat: 38.705, lng: -9.1, ele: null },
    ])
    expect(route.originalFilename).toBe('castle.gpx')
    expect(route.isLoop).toBe(true)
    expect(route).toMatchObject({
      userId: 1,
      visibility: 2,
      shareToken: 'secret-token',
      hideEndpointsM: 200,
      isOwner: true,
      sourceRouteId: null,
    })
  })

  it('reads shared routes without auth, by token or public id', async () => {
    vi.mocked(apiFetch).mockResolvedValue({
      ...routeDto,
      is_owner: false,
      share_token: null,
      owner: { id: 1, name: 'Ana', username: 'ana' },
    })
    const shared = await fetchSharedRoute({ token: 'a/b' })
    expect(vi.mocked(apiFetch).mock.calls[0]).toEqual([
      '/public/routes/by_token/a%2Fb',
      { auth: false, signal: undefined },
    ])
    expect(shared.owner).toEqual({ id: 1, name: 'Ana', username: 'ana' })
    expect(shared.isOwner).toBe(false)

    vi.mocked(apiFetch).mockResolvedValue({ ...routeDto, owner: null })
    expect((await fetchSharedRoute({ publicId: 7 })).owner).toBeNull()
    expect(vi.mocked(apiFetch).mock.calls[1]?.[0]).toBe('/public/routes/7')

    await exportSharedRouteGpx({ publicId: 7 })
    expect(vi.mocked(apiFetch).mock.calls[2]).toEqual([
      '/public/routes/7/export',
      { auth: false, responseType: 'blob' },
    ])
  })

  it('lists the routes on a profile', async () => {
    vi.mocked(apiFetch).mockResolvedValue({ records: [routeDto], total: 1 })
    const page = await fetchUserRoutes(5, { page: 2, numRecords: 10 })
    expect(vi.mocked(apiFetch).mock.calls[0]?.[0]).toBe(
      '/users/5/routes?page_number=2&num_records=10',
    )
    expect(page.records[0]?.visibility).toBe(2)
  })

  it('copies a route by id or share token', async () => {
    vi.mocked(apiFetch).mockResolvedValue({ ...routeDto, source: 4, source_route_id: 7 })
    expect((await copyRoute({ id: 7 })).sourceRouteId).toBe(7)
    await copyRoute({ token: 'tok' })
    expect(vi.mocked(apiFetch).mock.calls.map((call) => call[0])).toEqual([
      '/routes/7/copy',
      '/routes/shared/tok/copy',
    ])
    expect(vi.mocked(apiFetch).mock.calls[0]?.[1]).toEqual({ method: 'POST' })
  })

  it('updates sharing and manages the share link', async () => {
    vi.mocked(apiFetch).mockResolvedValue(routeDto)
    await updateRouteSharing(7, { visibility: 0, hideEndpointsM: 500 })
    expect(vi.mocked(apiFetch).mock.calls[0]).toEqual([
      '/routes/7',
      { method: 'PUT', body: JSON.stringify({ visibility: 0, hide_endpoints_m: 500 }) },
    ])
    await createRouteShareToken(7)
    await revokeRouteShareToken(7)
    expect(vi.mocked(apiFetch).mock.calls.slice(1)).toEqual([
      ['/routes/7/share_token', { method: 'POST' }],
      ['/routes/7/share_token', { method: 'DELETE' }],
    ])
  })

  it('maps the home-location warning', async () => {
    vi.mocked(apiFetch).mockResolvedValue({ start_near_home: true, end_near_home: false })
    expect(await fetchRouteHomeWarning(7)).toEqual({ startNearHome: true, endNearHome: false })
    expect(vi.mocked(apiFetch).mock.calls[0]?.[0]).toBe('/routes/7/home_warning')
  })

  it('builds the share link', () => {
    expect(routeShareUrl('abc_-1', 'https://endurain.example')).toBe(
      'https://endurain.example/r/abc_-1',
    )
  })

  it('fetches a page with paging and a trimmed search term', async () => {
    vi.mocked(apiFetch).mockResolvedValue({ records: [routeDto], total: 1 })
    const page = await fetchRoutes({ page: 2, numRecords: 10, search: '  castle ' })
    expect(vi.mocked(apiFetch).mock.calls[0]?.[0]).toBe(
      '/routes?page_number=2&num_records=10&q=castle',
    )
    expect(page.total).toBe(1)
    expect(page.records[0]?.name).toBe('Castle loop')
  })

  it('omits an empty search term', async () => {
    vi.mocked(apiFetch).mockResolvedValue({ records: [], total: 0 })
    await fetchRoutes({ page: 1, numRecords: 25, search: '   ' })
    expect(vi.mocked(apiFetch).mock.calls[0]?.[0]).toBe('/routes?page_number=1&num_records=25')
  })

  it('fetches, updates, deletes and exports a route', async () => {
    vi.mocked(apiFetch).mockResolvedValue(routeDto)
    expect((await fetchRoute(7)).id).toBe(7)
    await updateRoute(7, { name: 'New', description: null })
    expect(vi.mocked(apiFetch).mock.calls[1]).toEqual([
      '/routes/7',
      { method: 'PUT', body: JSON.stringify({ name: 'New', description: null }) },
    ])
    await deleteRoute(7)
    expect(vi.mocked(apiFetch).mock.calls[2]).toEqual([
      '/routes/7',
      { method: 'DELETE', responseType: 'void' },
    ])
    await exportRouteGpx(7)
    expect(vi.mocked(apiFetch).mock.calls[3]).toEqual([
      '/routes/7/export?format=gpx',
      { responseType: 'blob' },
    ])
  })

  it('saves an activity as a route', async () => {
    vi.mocked(apiFetch).mockResolvedValue({ ...routeDto, source: 2, source_activity_id: 3 })
    const route = await createRouteFromActivity(3)
    expect(vi.mocked(apiFetch).mock.calls[0]?.[0]).toBe('/routes/from_activity/3')
    expect(route.sourceActivityId).toBe(3)
  })

  it('uploads a valid file as multipart without a timeout', async () => {
    vi.mocked(apiFetch).mockResolvedValue(routeDto)
    await importRouteFile(file('tour.GPX', 10))
    const [path, init] = vi.mocked(apiFetch).mock.calls[0] ?? []
    expect(path).toBe('/routes/import')
    expect(init?.method).toBe('POST')
    expect(init?.body).toBeInstanceOf(FormData)
    expect(init?.timeoutMs).toBe(0)
  })

  it.each([
    ['empty.gpx', 0, 'empty'],
    ['route.kml', 10, 'extension'],
    ['noext', 10, 'extension'],
    ['huge.fit', MAX_ROUTE_FILE_BYTES + 1, 'size'],
  ])('rejects %s before uploading', async (name, size, problem) => {
    const error = captureError(() => assertValidRouteFile(file(name, size)))
    expect(error).toBeInstanceOf(RouteFileValidationError)
    expect((error as RouteFileValidationError).problem).toBe(problem)
    await expect(importRouteFile(file(name, size))).rejects.toThrow(RouteFileValidationError)
    expect(apiFetch).not.toHaveBeenCalled()
  })
})

describe('elevation profile', () => {
  const north = (metres: number, ele: number | null): RoutePoint => ({
    lat: metres / 111_195,
    lng: 0,
    ele,
  })

  it('measures great-circle distance', () => {
    expect(haversineMeters(north(0, null), north(1000, null))).toBeCloseTo(1000, 0)
  })

  it('needs at least two elevations', () => {
    expect(buildProfileSamples([north(0, 10), north(100, null)])).toEqual([])
    expect(buildElevationProfile([north(0, null)], 'metric', 'Elevation')).toBeNull()
  })

  it('keeps short profiles as-is and skips missing elevations', () => {
    const samples = buildProfileSamples([north(0, 10), north(500, null), north(1000, 30)])
    expect(samples.map((sample) => Math.round(sample.distance))).toEqual([0, 1000])
    expect(samples.map((sample) => sample.elevation)).toEqual([10, 30])
  })

  it('resamples long profiles onto an even grid', () => {
    const points = Array.from({ length: 1001 }, (_, i) => north(i * 10, i * 0.1))
    const samples = buildProfileSamples(points)
    expect(samples).toHaveLength(MAX_PROFILE_SAMPLES)
    expect(samples[0]?.elevation).toBeCloseTo(0)
    expect(samples[samples.length - 1]?.elevation).toBeCloseTo(100)
    expect(samples[200]?.elevation).toBeCloseTo((100 * 200) / (MAX_PROFILE_SAMPLES - 1), 1)
  })

  it('renders in the viewer units', () => {
    const points = [north(0, 100), north(1609.34, 200)]
    const metric = buildElevationProfile(points, 'metric', 'Elevation')
    expect(metric?.labels).toEqual(['0.0', '1.6'])
    expect(metric?.series[0]?.data).toEqual([100, 200])
    expect(metric?.xUnit).toBe('km')
    expect(metric?.valueFormat?.(123.4)).toBe('123 m')

    const imperial = buildElevationProfile(points, 'imperial', 'Elevation')
    expect(imperial?.labels).toEqual(['0.0', '1.0'])
    expect(imperial?.series[0]?.data).toEqual([328, 656])
    expect(imperial?.xUnit).toBe('mi')
    expect(imperial?.valueFormat?.(10)).toBe('10 ft')
  })
})
