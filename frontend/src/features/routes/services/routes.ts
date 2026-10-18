import {
  MAX_ROUTE_FILE_BYTES,
  ROUTE_FILE_EXTENSIONS,
  type PublicRoute,
  type PublicRouteDto,
  type RouteDetail,
  type RouteDetailDto,
  type RouteHomeWarning,
  type RouteHomeWarningDto,
  type RouteInput,
  type RouteSharingInput,
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
    visibility: dto.visibility,
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
    userId: dto.user_id,
    description: dto.description ?? null,
    sourceActivityId: dto.source_activity_id ?? null,
    sourceRouteId: dto.source_route_id ?? null,
    originalFilename: dto.original_filename ?? null,
    shareToken: dto.share_token ?? null,
    hideEndpointsM: dto.hide_endpoints_m,
    isOwner: dto.is_owner ?? false,
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

/**
 * Maps a public-page payload, keeping the optional creator.
 *
 * @param dto - Raw public route.
 * @returns The public route.
 */
export function mapPublicRoute(dto: PublicRouteDto): PublicRoute {
  return {
    ...mapRouteDetail(dto),
    isOwner: false,
    owner: dto.owner
      ? { id: dto.owner.id, name: dto.owner.name, username: dto.owner.username }
      : null,
  }
}

/**
 * Where a shared route is read from: a share-link token, or a public id for
 * anonymous viewers.
 */
export type SharedRouteRef = { token: string } | { publicId: number }

/** Public API path of a shared route. */
function sharedRoutePath(ref: SharedRouteRef): string {
  return 'token' in ref
    ? `/public/routes/by_token/${encodeURIComponent(ref.token)}`
    : `/public/routes/${ref.publicId}`
}

/**
 * Fetches a route through its share link or public id, without auth.
 *
 * @param ref - Token or public id.
 * @param signal - Optional abort signal.
 * @returns The route as anyone with the link sees it.
 * @throws {HttpError} When the request fails (404 when the link is invalid,
 *   revoked, or public links are disabled).
 */
export async function fetchSharedRoute(
  ref: SharedRouteRef,
  signal?: AbortSignal,
): Promise<PublicRoute> {
  return mapPublicRoute(
    await apiFetch<PublicRouteDto>(sharedRoutePath(ref), { auth: false, signal }),
  )
}

/**
 * Downloads a shared route as GPX, without auth.
 *
 * @param ref - Token or public id.
 * @returns The GPX file contents.
 * @throws {HttpError} When the request fails.
 */
export async function exportSharedRouteGpx(ref: SharedRouteRef): Promise<Blob> {
  return apiFetch<Blob>(`${sharedRoutePath(ref)}/export`, { auth: false, responseType: 'blob' })
}

/** Pagination input for a profile's routes. */
export interface UserRoutesParams {
  /** 1-based page number. */
  page: number
  /** Page size. */
  numRecords: number
}

/**
 * Fetches one page of a user's routes that the viewer can see.
 *
 * @param userId - Profile user id.
 * @param params - Page and size.
 * @param signal - Optional abort signal.
 * @returns The page of routes and the total count.
 * @throws {HttpError} When the request fails.
 */
export async function fetchUserRoutes(
  userId: number,
  { page, numRecords }: UserRoutesParams,
  signal?: AbortSignal,
): Promise<RoutesPage> {
  const params = new URLSearchParams({ page_number: String(page), num_records: String(numRecords) })
  const response = await apiFetch<RoutesPageDto>(`/users/${userId}/routes?${params.toString()}`, {
    signal,
  })
  return { records: response.records.map(mapRouteSummary), total: response.total }
}

/**
 * Saves a copy of a route the viewer can see into their library.
 *
 * @param source - Route id, or the share-link token it was opened with.
 * @returns The new (private) route.
 * @throws {HttpError} When the request fails.
 */
export async function copyRoute(source: { id: number } | { token: string }): Promise<RouteDetail> {
  const path =
    'token' in source
      ? `/routes/shared/${encodeURIComponent(source.token)}/copy`
      : `/routes/${source.id}/copy`
  return mapRouteDetail(await apiFetch<RouteDetailDto>(path, { method: 'POST' }))
}

/**
 * Updates who can see a route and how much of its ends is hidden.
 *
 * @param id - Route id.
 * @param input - New sharing options.
 * @returns The updated route.
 * @throws {HttpError} When the request fails.
 */
export async function updateRouteSharing(
  id: number,
  input: RouteSharingInput,
): Promise<RouteDetail> {
  const dto = await apiFetch<RouteDetailDto>(`/routes/${id}`, {
    method: 'PUT',
    body: JSON.stringify({ visibility: input.visibility, hide_endpoints_m: input.hideEndpointsM }),
  })
  return mapRouteDetail(dto)
}

/**
 * Creates or rotates a route's unlisted share link.
 *
 * @param id - Route id.
 * @returns The route with its new token.
 * @throws {HttpError} When the request fails.
 */
export async function createRouteShareToken(id: number): Promise<RouteDetail> {
  return mapRouteDetail(
    await apiFetch<RouteDetailDto>(`/routes/${id}/share_token`, { method: 'POST' }),
  )
}

/**
 * Revokes a route's unlisted share link.
 *
 * @param id - Route id.
 * @returns The route without a token.
 * @throws {HttpError} When the request fails.
 */
export async function revokeRouteShareToken(id: number): Promise<RouteDetail> {
  return mapRouteDetail(
    await apiFetch<RouteDetailDto>(`/routes/${id}/share_token`, { method: 'DELETE' }),
  )
}

/**
 * Checks whether a route's visible ends lie near where many of the owner's
 * activities start.
 *
 * @param id - Route id.
 * @param signal - Optional abort signal.
 * @returns Which ends are flagged.
 * @throws {HttpError} When the request fails.
 */
export async function fetchRouteHomeWarning(
  id: number,
  signal?: AbortSignal,
): Promise<RouteHomeWarning> {
  const dto = await apiFetch<RouteHomeWarningDto>(`/routes/${id}/home_warning`, { signal })
  return { startNearHome: dto.start_near_home, endNearHome: dto.end_near_home }
}

/**
 * Absolute URL of a route's unlisted share link.
 *
 * @param token - Share token.
 * @param origin - Page origin (defaults to the current one).
 * @returns The `/r/:token` link.
 */
export function routeShareUrl(token: string, origin: string = window.location.origin): string {
  const base = import.meta.env.BASE_URL.replace(/\/$/, '')
  return `${origin}${base}/r/${encodeURIComponent(token)}`
}
