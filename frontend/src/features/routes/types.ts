import type { Schemas } from '@/types'

/** Raw list payload for a route (no geometry), as the backend sends it. */
export type RouteSummaryDto = Schemas['RouteSummary']
/** Raw detail payload for a route, as the backend sends it. */
export type RouteDetailDto = Schemas['RouteRead']
/** Raw page of routes, as the backend sends it. */
export type RoutesPageDto = Schemas['RoutesPage']
/** Point-of-interest category. */
export type PoiKind = Schemas['PoiKind']
/** How a route was created: 1 import, 2 saved from an activity. */
export type RouteSource = Schemas['RouteSource']

/** Route source codes, mirroring the backend's `RouteSource`. */
export const ROUTE_SOURCE = {
  import: 1,
  activity: 2,
} as const satisfies Record<string, RouteSource>

/** A route in the library list. */
export interface RouteSummary {
  id: number
  name: string
  activityType: number | null
  source: RouteSource
  /** Length in metres. */
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
  description: string | null
  sourceActivityId: number | null
  originalFilename: string | null
  points: RoutePoint[]
  pois: RoutePoi[]
  elevationMin: number | null
  elevationMax: number | null
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
