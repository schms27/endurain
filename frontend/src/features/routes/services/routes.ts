import {
  MAX_ROUTE_FILE_BYTES,
  ROUTE_FILE_EXTENSIONS,
  type RouteDetail,
  type RouteDetailDto,
  type RouteInput,
  type RoutesPage,
  type RouteSummary,
  type RouteSummaryDto,
  type RoutesPageDto,
} from '@/features/routes/types'
import { apiFetch } from '@/services/http'

/** Why a route file was rejected before upload. */
export type RouteFileProblem = 'empty' | 'extension' | 'size'

/** Raised when a route file fails client-side checks (no request is sent). */
export class RouteFileValidationError extends Error {
  constructor(readonly problem: RouteFileProblem) {
    super(`Invalid route file: ${problem}`)
    this.name = 'RouteFileValidationError'
  }
}

/** Pagination + search input for a routes list request. */
export interface RoutesListParams {
  /** 1-based page number. */
  page: number
  /** Page size. */
  numRecords: number
  /** Optional name search term. */
  search?: string
}

/**
 * Maps a list payload to the clean {@link RouteSummary} model.
 *
 * @param dto - Raw route summary.
 * @returns The normalized route summary.
 */
export function mapRouteSummary(dto: RouteSummaryDto): RouteSummary {
  return {
    id: dto.id,
    name: dto.name,
    activityType: dto.activity_type ?? null,
    source: dto.source,
    distance: dto.distance,
    elevationGain: dto.elevation_gain ?? null,
    elevationLoss: dto.elevation_loss ?? null,
    isLoop: dto.is_loop,
    city: dto.city ?? null,
    country: dto.country ?? null,
    createdAt: dto.created_at,
  }
}

/**
 * Maps a detail payload to the clean {@link RouteDetail} model, turning the
 * `[lat, lon, ele]` geometry into named points.
 *
 * @param dto - Raw route detail.
 * @returns The normalized route detail.
 */
export function mapRouteDetail(dto: RouteDetailDto): RouteDetail {
  return {
    ...mapRouteSummary(dto),
    description: dto.description ?? null,
    sourceActivityId: dto.source_activity_id ?? null,
    originalFilename: dto.original_filename ?? null,
    points: dto.geometry
      .filter((point) => typeof point[0] === 'number' && typeof point[1] === 'number')
      .map((point) => ({
        lat: point[0] as number,
        lng: point[1] as number,
        ele: typeof point[2] === 'number' ? point[2] : null,
      })),
    pois: dto.waypoints.map((poi) => ({
      name: poi.name,
      description: poi.description ?? null,
      kind: poi.kind,
      lat: poi.lat,
      lng: poi.lon,
      ele: poi.ele ?? null,
    })),
    elevationMin: dto.elevation_min ?? null,
    elevationMax: dto.elevation_max ?? null,
  }
}

/**
 * Fetches one page of the user's routes.
 *
 * @param params - Page, size and optional search term.
 * @param signal - Optional abort signal.
 * @returns The page of routes and the total count.
 * @throws {HttpError} When the request fails.
 */
export async function fetchRoutes(
  { page, numRecords, search }: RoutesListParams,
  signal?: AbortSignal,
): Promise<RoutesPage> {
  const params = new URLSearchParams({
    page_number: String(page),
    num_records: String(numRecords),
  })
  const term = search?.trim()
  if (term) {
    params.set('q', term)
  }
  const response = await apiFetch<RoutesPageDto>(`/routes?${params.toString()}`, { signal })
  return { records: response.records.map(mapRouteSummary), total: response.total }
}

/**
 * Fetches a single route.
 *
 * @param id - Route id.
 * @param signal - Optional abort signal.
 * @returns The route detail.
 * @throws {HttpError} When the request fails (404 when missing).
 */
export async function fetchRoute(id: number, signal?: AbortSignal): Promise<RouteDetail> {
  return mapRouteDetail(await apiFetch<RouteDetailDto>(`/routes/${id}`, { signal }))
}

/**
 * Lowercase extension of a file name, used only for the allow-list check.
 *
 * @param filename - The user-supplied file name.
 * @returns The extension without the dot, or `''`.
 */
function getExtension(filename: string): string {
  const dot = filename.lastIndexOf('.')
  return dot >= 0 ? filename.slice(dot + 1).toLowerCase() : ''
}

/**
 * Fail-fast client-side checks mirroring the backend (which re-validates).
 *
 * @param file - The selected file.
 * @throws {RouteFileValidationError} When the file is empty, of an
 *   unsupported type, or too large.
 */
export function assertValidRouteFile(file: File): void {
  if (file.size === 0) {
    throw new RouteFileValidationError('empty')
  }
  if (!(ROUTE_FILE_EXTENSIONS as readonly string[]).includes(getExtension(file.name))) {
    throw new RouteFileValidationError('extension')
  }
  if (file.size > MAX_ROUTE_FILE_BYTES) {
    throw new RouteFileValidationError('size')
  }
}

/**
 * Imports a route from a GPX, TCX or FIT file. The file name travels only as
 * the multipart part name; the server never uses it to build a path.
 *
 * @param file - The route file.
 * @param signal - Optional abort signal.
 * @returns The created route.
 * @throws {RouteFileValidationError} When client-side checks fail.
 * @throws {HttpError} When the server rejects the file.
 */
export async function importRouteFile(file: File, signal?: AbortSignal): Promise<RouteDetail> {
  assertValidRouteFile(file)
  const formData = new FormData()
  formData.append('file', file, file.name)
  const dto = await apiFetch<RouteDetailDto>('/routes/import', {
    method: 'POST',
    body: formData,
    signal,
    timeoutMs: 0,
  })
  return mapRouteDetail(dto)
}

/**
 * Saves one of the user's activities as a route.
 *
 * @param activityId - The activity to copy.
 * @returns The created route.
 * @throws {HttpError} When the request fails.
 */
export async function createRouteFromActivity(activityId: number): Promise<RouteDetail> {
  const dto = await apiFetch<RouteDetailDto>(`/routes/from_activity/${activityId}`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
  return mapRouteDetail(dto)
}

/**
 * Updates a route's name and description.
 *
 * @param id - Route id.
 * @param input - New values.
 * @returns The updated route.
 * @throws {HttpError} When the request fails.
 */
export async function updateRoute(id: number, input: RouteInput): Promise<RouteDetail> {
  const dto = await apiFetch<RouteDetailDto>(`/routes/${id}`, {
    method: 'PUT',
    body: JSON.stringify({ name: input.name, description: input.description }),
  })
  return mapRouteDetail(dto)
}

/**
 * Deletes a route.
 *
 * @param id - Route id.
 * @throws {HttpError} When the request fails.
 */
export async function deleteRoute(id: number): Promise<void> {
  await apiFetch<void>(`/routes/${id}`, { method: 'DELETE', responseType: 'void' })
}

/**
 * Downloads a route as GPX.
 *
 * @param id - Route id.
 * @returns The GPX file contents.
 * @throws {HttpError} When the request fails.
 */
export async function exportRouteGpx(id: number): Promise<Blob> {
  return apiFetch<Blob>(`/routes/${id}/export?format=gpx`, { responseType: 'blob' })
}
