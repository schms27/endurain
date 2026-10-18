import type { Schemas } from '@/types'

/** Raw list payload for a route (no geometry), as the backend sends it. */
export type RouteSummaryDto = Schemas['RouteSummary']
/** Raw detail payload for a route, as the backend sends it. */
export type RouteDetailDto = Schemas['RouteRead']
/** Raw page of routes, as the backend sends it. */
export type RoutesPageDto = Schemas['RoutesPage']
/** Point-of-interest category. */
export type PoiKind = Schemas['PoiKind']
/** Raw public-page payload for a route, as the backend sends it. */
export type PublicRouteDto = Schemas['PublicRouteRead']
/** Raw home-location warning, as the backend sends it. */
export type RouteHomeWarningDto = Schemas['RouteHomeWarning']
/** How a route was created: 1 import, 2 saved from an activity, 4 copy. */
export type RouteSource = Schemas['RouteSource']
/** Who can see a route: 0 public, 1 followers, 2 private (activity codes). */
export type RouteVisibility = Schemas['RouteVisibility']

/** Route source codes, mirroring the backend's `RouteSource`. */
export const ROUTE_SOURCE = {
  import: 1,
  activity: 2,
  copy: 4,
} as const satisfies Record<string, RouteSource>

/** Route visibility codes, mirroring the backend's `RouteVisibility`. */
export const ROUTE_VISIBILITY = {
  public: 0,
  followers: 1,
  private: 2,
} as const satisfies Record<string, RouteVisibility>

/** Endpoint-trimming choices (metres) offered in the share dialog. */
export const HIDE_ENDPOINTS_OPTIONS = [0, 100, 200, 500, 1000] as const

/** A route in the library list. */
export interface RouteSummary {
  id: number
  name: string
  activityType: number | null
  source: RouteSource
  visibility: RouteVisibility
  /** Length in metres (with the hidden ends removed for non-owners). */
  distance: number
  /** Elevation gain in metres, when known. */
  elevationGain: number | null
  /** Elevation loss in metres, when known. */
  elevationLoss: number | null
  isLoop: boolean
  city: string | null
  country: string | null
  createdAt: string
}

/** One vertex of a route: latitude, longitude and optional elevation (m). */
export interface RoutePoint {
  lat: number
  lng: number
  ele: number | null
}

/** A point of interest along a route. */
export interface RoutePoi {
  name: string
  description: string | null
  kind: PoiKind
  lat: number
  lng: number
  ele: number | null
}

/** Full route details for the detail page. */
export interface RouteDetail extends RouteSummary {
  userId: number
  description: string | null
  /** Owner only. */
  sourceActivityId: number | null
  /** The route this one was copied from. */
  sourceRouteId: number | null
  /** Owner only. */
  originalFilename: string | null
  /** Unlisted link token; owner only, `null` when there is no link. */
  shareToken: string | null
  /** Metres hidden at both ends for everyone but the owner. */
  hideEndpointsM: number
  /** Whether the viewer owns the route. */
  isOwner: boolean
  points: RoutePoint[]
  pois: RoutePoi[]
  elevationMin: number | null
  elevationMax: number | null
}

/** Creator shown on a public route page (only when the server shares it). */
export interface RouteOwner {
  id: number
  name: string
  username: string
}

/** A route as served on its public page. */
export interface PublicRoute extends RouteDetail {
  owner: RouteOwner | null
}

/** Visibility and privacy options of a route. */
export interface RouteSharingInput {
  visibility: RouteVisibility
  hideEndpointsM: number
}

/** Which visible endpoints may reveal where the owner lives. */
export interface RouteHomeWarning {
  startNearHome: boolean
  endNearHome: boolean
}

/** One page of the library. */
export interface RoutesPage {
  records: RouteSummary[]
  total: number
}

/** Editable route attributes. */
export interface RouteInput {
  name: string
  description: string | null
}

/** Accepted route file extensions, mirroring the backend allow-list. */
export const ROUTE_FILE_EXTENSIONS = ['gpx', 'tcx', 'fit'] as const

/** Largest route file the backend accepts (20 MiB). */
export const MAX_ROUTE_FILE_BYTES = 20 * 1024 * 1024

/**
 * File-picker `accept` value. MIME types are listed alongside extensions
 * because iOS filters by MIME/UTI (see the activity upload types).
 */
export const ROUTE_FILE_ACCEPT = [
  ...ROUTE_FILE_EXTENSIONS.map((extension) => `.${extension}`),
  'application/gpx+xml',
  'application/vnd.garmin.tcx+xml',
  'application/vnd.ant.fit',
  'application/octet-stream',
].join(',')
