# Proposal: Custom routes (create, import, export and share)

Status: **Draft** · Date: 2026-10-18 · Inspired by: Strava Routes ·
Index: [proposals overview](README.md)

## 1. Summary

A **route** is a planned path with no timestamps. A user can get one in three
ways:

- **Import** a GPX, TCX or FIT course file (from Komoot, RideWithGPS,
  OsmAnd, a club website, and so on).
- **Save** all or part of a past activity as a route.
- **Draw** it on a map, optionally snapping to roads and trails through a
  routing engine.

Routes live in a personal library with a map, an elevation profile and
points of interest. They can be private, shared with followers, public, or
shared through an unlisted link, and downloaded as GPX (later FIT or TCX) for
a bike computer or watch. In a later phase Endurain can recognise activities
that followed a route ("You've ridden this route 4 times, best 1:12:03").

## 2. Goals and non-goals

**Goals**

- A route library per user, with a detail page (map, elevation profile, POIs,
  stats).
- Import of common route formats, including files without timestamps.
- Save an activity, or a slice of it, as a route.
- Sharing that matches Endurain's visibility model, plus copying a shared
  route into your own library.
- Export for devices.
- A route builder with freehand drawing and optional snap-to-road routing.

**Non-goals (v1)**

- Turn-by-turn cue sheets and voice navigation.
- Offline maps.
- Route recommendations or "popular routes": these need heatmap data that
  Endurain does not have.
- Pushing routes to vendor clouds (Garmin Connect, Wahoo, Hammerhead, COROS)
  through their APIs. This is investigated in Phase 5 only.
- Collaborative editing of one route by several users.

## 3. What exists today

| Area | Current state | Relevance |
| --- | --- | --- |
| GPX parsing | `activities/activity_file_import/utils_gpx.py::parse_gpx_file` reads only `gpx.tracks`, skips trackpoints without time ("OsmAnd exports"), and rejects files with no timed segment. `<rte>` and `<wpt>` are ignored. | Routes need a separate, time-free parse path. gpxpy itself handles routes and waypoints. |
| TCX and FIT | `tcxreader` and `fitdecode` (decode only) parse activity files. | FIT course import works with `fitdecode`. **Exporting** FIT needs an encoder (§8). |
| Upload pipeline | `core/file_uploads.py` with `safeuploads` (extension and content validation; 200 MiB cap for activity files, gzip-aware). | Reuse it with a route-specific allow-list and a smaller cap. |
| Thumbnails | `activities/activity/thumbnail.py::generate_activity_thumbnail(id, lat_lon_waypoints, dir, tile_url, background_color, api_key)` renders static maps through `staticmap`, using the tile-server settings. | Generalise it for route list thumbnails. |
| Tile-server settings | `server_settings` holds `tileserver_url`, `tileserver_attribution`, and `tileserver_api_key` (Fernet-encrypted). | A precedent for routing and elevation provider settings with encrypted keys. |
| Sharing | Activities use visibility 0/1/2. The `public_shareable_links` and `public_shareable_links_user_info` server settings and `public_router.py` modules serve public activities by numeric id. | Same model for routes, plus unguessable share tokens (§7). |
| Rate limiting and cache | `slowapi` (`core/rate_limit.py`) and Redis (`core/redis.py`) are available. | Throttle and cache routing-engine calls. |
| Frontend map | `useMapProvider` seam: display only, one polyline, start and finish markers. Leaflet implementation. | Needs overlays (shared with segments) and an optional editor capability. |
| Elevation | Activity elevation comes from the device. There is no digital elevation model (DEM) service. | Drawn routes need elevation from the routing engine or an optional elevation service. |
| Geometry helpers | None shared yet. The segments proposal introduces `core/geo.py` (distances, simplification, resampling, bounding boxes). | Reused here. |

## 4. Feasibility

**Verdict: feasible.** The core (import, save from activity, library,
GPX export, sharing) is low risk and independent of segments. The route
builder carries most of the cost and depends on an *optional, external*
routing service for snapping.

| Sub-feature | Feasibility | Size | Notes |
| --- | --- | --- | --- |
| Import GPX (trk/rte/wpt, timed or not), FIT course, TCX course | High | S–M | A new time-free parser path; gpxpy and fitdecode already cover the formats. |
| Save activity (or slice) as route | High | S | Copies the lat/lon and elevation streams and drops time. Shares the range slider with segment creation. |
| Library, detail page, elevation profile, POIs | High | M | |
| GPX export | High | S | gpxpy can write GPX. |
| FIT course export | Medium | S–M | Needs a FIT encoder; check licence compatibility with AGPL-3.0. |
| TCX course export | High | S | Small XML template. |
| Sharing: visibility, unlisted link, public page, copy to my routes | High | S–M | Reuses the visibility model and public-link setting. |
| Builder: freehand drawing | High | M | Needs editor support in the map seam; Leaflet supports draggable markers natively. |
| Builder: snap to roads and trails | Medium | M | Needs a routing engine. Self-hosted BRouter, GraphHopper, Valhalla or OSRM, or a hosted API with a key. |
| Elevation for drawn routes | Medium | S | From the routing engine response, or an optional DEM service. |
| Route completions | Medium | M | Reuses the segment matcher in "coverage mode". Cheap if segments are built first. |
| Import Strava routes | Medium | S | The Strava API offers route export for the athlete's own routes. Showing them to other users conflicts with the API terms (§9). |
| Push to vendor devices or clouds | Low | ? | Unofficial or partner-only APIs, and ongoing maintenance. |

## 5. Data model

### 5.1 `routes`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | PK | |
| `user_id` | FK `users.id` `ON DELETE CASCADE` | Owner. |
| `name` | `String(250)` | Defaults to the file's `<name>`, else "Route <date>". |
| `description` | `String(2500)` nullable | |
| `activity_type` | `Integer` nullable | Intended sport, using the same codes as activities. |
| `visibility` | `SmallInteger` | 0 public, 1 followers, 2 private (default from the user's `default_activity_visibility`). |
| `share_token` | `String(43)` nullable, unique | `secrets.token_urlsafe(32)`, for "anyone with the link". Can be rotated or revoked. |
| `hide_endpoints_m` | `SmallInteger` default 0 | Trim the first and last N metres from every non-owner view and export (§7.3). |
| `source` | `SmallInteger` | 1 import, 2 activity, 3 builder, 4 copy, 5 Strava. |
| `source_activity_id` | FK `activities.id` `ON DELETE SET NULL` | |
| `source_route_id` | FK `routes.id` `ON DELETE SET NULL` | Attribution for copies. |
| `original_filename` | `String(250)` nullable | |
| `geometry` | `JSON` | `[[lat, lon, ele \| null], …]`, simplified (Douglas–Peucker about 1–2 m), at most 20 000 points. |
| `waypoints` | `JSON` nullable | POIs: `[{name, description, kind, lat, lon, ele}]`. `kind` is one of generic, water, food, summit, viewpoint, danger, shelter, toilet. |
| `builder_state` | `JSON` nullable | Control points and per-leg `{mode: freehand \| routed, profile}`, so editing keeps the original intent. |
| `distance` | `DECIMAL` | Metres. |
| `elevation_gain`, `elevation_loss`, `elevation_min`, `elevation_max` | `Integer` nullable | |
| `is_loop` | `Boolean` | Start and end within 100 m. |
| `start_lat`, `start_lon`, `end_lat`, `end_lon` | `Float` | |
| `bbox_min_lat`, `bbox_min_lon`, `bbox_max_lat`, `bbox_max_lon` | `Float`, indexed | Same convention as the segments proposal. |
| `city`, `town`, `country` | `String(250)` nullable | Reverse-geocoded start (`location_based_on_coordinates`). |
| `map_thumbnail_path` | `String(500)` nullable | |
| `created_at`, `updated_at` | `DateTime(tz)` | |

POIs are stored as JSON on the route because they are never queried on
their own. Copying a route creates a new row (`source = 4`) instead of a
bookmark. The copy survives if the original is deleted or made private, and
the owner can edit it freely.

### 5.2 Phase 5: `route_completions`

`(id, route_id, activity_id, user_id, elapsed_time, coverage, created_at)`
with `ON DELETE CASCADE` on both foreign keys, unique on
`(route_id, activity_id)`.

### 5.3 Settings

- **`server_settings`**:
  - `routes_enabled` (default `true`).
  - `routing_provider` (`none` | `brouter` | `graphhopper` | `valhalla` |
    `osrm` | `openrouteservice`, default `none`).
  - `routing_url`, `routing_api_key` (Fernet-encrypted, like
    `tileserver_api_key`).
  - `elevation_provider` (`none` | `routing` | `opentopodata` |
    `open_elevation`), `elevation_url`.
  - `routes_max_upload_mb` (default 20).
- **Scopes** in `auth/constants.py`: `routes:read`, `routes:write`. Add them
  to the regular access scope and to the API-key read-only set.

## 6. Creating routes

### 6.1 Import

`POST /routes/import` (multipart, one or more files, `routes:write`):

1. **Validate:** use `safeuploads` with the allow-list `.gpx`, `.tcx`,
   `.fit` (and `.gz` variants, as for activities), within the
   `routes_max_upload_mb` cap.
2. **Parse** into a normalised `ParsedRoute(name, description, points, pois)`
   in a new `routes/route_file_import/` module, separate from the activity
   parsers so neither path can break the other:
   - **GPX 1.0/1.1** (gpxpy):
     - Prefer `<trk>`/`<trkseg>`/`<trkpt>`; fall back to `<rte>`/`<rtept>`.
       Timestamps are ignored when present.
     - Multiple segments are concatenated in file order. The UI warns when a
       gap is larger than 200 m, because the result joins them with a
       straight line.
     - `<wpt>` becomes POIs, with `<sym>`/`<type>` mapped to `kind`.
   - **FIT course** (fitdecode): `record` messages give the positions
     (semicircles converted to degrees) and altitude; `course_point` messages
     give the POIs; the `course` message gives the name. FIT *activity* files
     are accepted too, with times dropped.
   - **TCX** `<Courses>`: check `tcxreader` course support first. Otherwise,
     parse the small course subset with the same hardened XML settings the
     activity importers use.
   - **Phase 5:** KML/KMZ `LineString` and GeoJSON `LineString` or
     `MultiLineString`.
3. **Derive:** distance and bounding box (`core/geo.py`), elevation gain and
   loss (reuse `compute_elevation_gain_and_loss`), `is_loop`, and the
   reverse-geocoded start. Simplify to at most 20 000 points.
4. **Fill missing elevation:** if the file has none and `elevation_provider`
   is set, sample it (§6.3).
5. **Store** the row and generate the thumbnail (the generalised activity
   thumbnail function).

The UI accepts drag-and-drop of several files. Each file becomes one route.
For multi-track GPX files, the user chooses between one route per track or
merging them.

### 6.2 Save activity as route

`POST /routes/from_activity/{activity_id}` with an optional
`start_index`/`end_index` (`routes:write`). It is offered only for the
caller's **own** activities with a lat/lon stream (from the activity actions
menu):

- Copy the lat/lon points in range, join the elevation stream by timestamp,
  then drop all time data.
- Simplify, derive the stats, and set `source = 2` and `source_activity_id`.
- The slice picker is the same two-thumb range component as segment creation.
  Build it once and share it.
- Default visibility is **private**, whatever the activity's visibility.

Copying a route from *another user's* public activity is deferred, because
it bypasses that user's intent for the route itself (open question 4).

### 6.3 Route builder

**Interaction:**

- Click to add control points; drag to move; click a point to delete it;
  drag the line to insert a point.
- Undo and redo.
- Per-leg mode: *freehand* or *routed*, with a profile (road bike, gravel,
  MTB, hiking, running).
- Helpers: reverse route, close loop, out-and-back.
- Live distance, elevation gain and elevation profile.
- POI placement.
- Save, or save as copy.

The `builder_state` is stored, so reopening the editor restores the control
points instead of thousands of geometry points.

**Frontend: map seam editor capability.** It is optional, so builds without
an editor (or the no-op provider) hide the builder:

```ts
export interface RouteEditorOptions {
  controlPoints: GeoPoint[]
  /** Rendered geometry between control points (already routed or straight). */
  legs: GeoPoint[][]
  pois?: Array<GeoPoint & { id: string; kind: string }>
}

export interface RouteEditorInstance extends MapInstance {
  setState(options: RouteEditorOptions): void
  on(event: 'mapClick' | 'pointMove' | 'pointRemove' | 'lineInsert',
     handler: (payload: { index?: number; point: GeoPoint }) => void): () => void
}

export interface MapProvider {
  readonly name: string
  mount(target: HTMLElement, options: MapRenderOptions): MapInstance
  /** Optional: providers that support editing implement this. */
  mountEditor?(target: HTMLElement, options: RouteEditorOptions): RouteEditorInstance
}
```

Editor state (control points, legs, undo stack) lives in a framework-agnostic
reducer in `features/routes/utils/routeEditorState.ts`, which is unit-tested
without a map. The Leaflet implementation uses draggable markers and
polylines. This needs **no new dependency**: `leaflet-routing-machine` was
considered and rejected, because it couples the UI to specific routing APIs
and duplicates the backend proxy.

**Backend: routing proxy.** The endpoint is
`POST /routes/routing/leg {from, to, profile}` → `{points: [[lat, lon, ele?]], distance}`.

- **Why a proxy:**
  - It keeps provider API keys server-side.
  - It avoids CORS problems.
  - It enforces rate limits (`slowapi`, per user).
  - It caches legs in Redis, keyed by `hash(provider, profile, from, to)`
    with a 24 h TTL, so dragging a point only re-routes the two adjacent legs.
- **Provider adapters** in `routes/routing_providers/`, behind a small
  protocol `route_leg(points, profile) -> RoutedLeg`:
  1. **BRouter** first: easy to self-host, bike and foot profiles tuned for
     cycling and hiking, and it returns elevation in its GeoJSON output.
  2. GraphHopper and openrouteservice (self-hosted or hosted with an API
     key).
  3. Valhalla and OSRM.

  Profile names are mapped per adapter. The engines run as separate services
  over HTTP, so their licences do not affect Endurain's. Do not point at
  public demo instances by default: check each provider's usage policy, and
  document self-hosting instead.
- **No provider configured:** the builder works in freehand mode only, and
  the UI says so.

**Elevation.** Elevation comes from the routing response when the provider
returns it. Otherwise, if `elevation_provider` is set, the backend resamples
the route every 30–50 m, queries the DEM service in batches (OpenTopoData,
for example, accepts many locations per request), interpolates back onto the
geometry, and caches the result in Redis. Without a provider, the route has
no elevation, and the profile chart shows an empty state.

**Docs:** add an *Advanced* hosting section with an optional BRouter service
snippet for `docker-compose.yml`. It should mention that the regional
routing data files must be downloaded for the area served.

## 7. Sharing

### 7.1 Access levels

| Level | Who can see it | Mechanism |
| --- | --- | --- |
| Private (2) | Owner | Default for imports and for routes saved from activities. |
| Followers (1) | Accepted followers | Same follower condition as `_visible_to_requester_condition`. |
| Public (0) | Any signed-in user on the instance; anonymous visitors if `public_shareable_links` is on | Public router by id. |
| Unlisted link | Anyone with the token, if `public_shareable_links` is on | `share_token`, independent of visibility. Rotate or revoke from the share dialog. |

The unlisted link exists because routes often start at someone's front door.
Users should be able to send a route to a friend without making it
discoverable or guessable by id. That is also why the token is used instead of
the numeric ids the public activity links rely on.

### 7.2 Surfaces

- **Share dialog:** a visibility selector, "Create link" (copy, rotate,
  revoke), the endpoint-trimming option, and a privacy warning when the start
  or end lies within 200 m of the start of several of the owner's activities
  (a home-location heuristic).
- **Public route page** at `/r/:token` and `/route/:id` for anonymous public
  routes: map, elevation profile, stats, and a GPX download. The creator's
  name is shown only if `public_shareable_links_user_info` is on. This page is
  served by the routes `public_router.py`.
- **Profile page** (`/user/:id`): a "Routes" tab listing routes visible to the
  viewer.
- **"Save to my routes":** copies a visible route into the viewer's library
  (`source = 4`, attribution via `source_route_id`, private by default).
- **Phase 5:** federation (ActivityPub `Note` with a GPX attachment) once the
  Federation roadmap item exists.

### 7.3 Endpoint trimming

When `hide_endpoints_m > 0`, every non-owner response removes the first and
last N metres of geometry: map, export, public page and copy. It also
recomputes the displayed distance. This is a lightweight stand-in for privacy
zones, which Endurain does not have yet (see the Local Legends proposal, §7).
The owner always sees the full route.

## 8. Export

`GET /routes/{id}/export?format=gpx|tcx|fit` (`routes:read`; the public
variant is gated like the page):

- **GPX 1.1** (Phase 1) via gpxpy:
  - A `<trk>` with `<ele>` by default, which has the widest device and app
    compatibility. `?gpx_type=rte` writes `<rte>` instead.
  - POIs are written as `<wpt>`.
  - The filename is a slug of the route name.
- **TCX course** (Phase 5): `<Courses><Course>` with `<Track>` and
  `<CoursePoint>`.
- **FIT course** (Phase 5): needed for copying straight to Garmin devices
  over USB.
  - The file consists of `file_id` (type course), `course`, `lap`, `event`,
    `record` (with synthetic timestamps from a nominal speed) and
    `course_point` messages.
  - Options: evaluate a Python FIT encoder from PyPI, or write this small
    message subset directly.
  - Either way, **check licence compatibility with AGPL-3.0**, and test
    against the FIT SDK validator and at least one real device.

## 9. Strava and vendor integrations

- **Strava routes import (Phase 5):** the Strava API lets an athlete list and
  export their own routes. Importing them as **private** routes is
  reasonable. Showing them to other users conflicts with Strava's API
  agreement (revised in late 2024 to restrict displaying a user's Strava data
  to other users): imported routes are locked to private, and the UI explains
  why. Check the current terms and the scopes required before implementing.
- **Garmin Connect course upload, Wahoo, Hammerhead, COROS:** investigate
  only. The Garmin integration uses an unofficial client library, and other
  vendors need partner agreements. File export (GPX or FIT) plus each
  vendor's own import covers most needs in the meantime.

## 10. Route completions (Phase 5)

When an activity is imported, match it against the owner's routes (owned and
copied) with the segment matcher in *coverage mode*:

- Route samples covered within a 40 m corridor ≥ 90 %, in either direction
  for loops.
- Length ratio 0.9–1.3.

This creates `route_completions` rows, which drive "Completed 4 ×, best
1:12:03" on the route page and a "Route: …" chip on the activity. If segments
ship first, this is mostly configuration of the existing queue and matcher;
otherwise it waits for, or becomes the first user of, `core/geo.py`. A
"Create segment from this route section" action ties the two features
together.

## 11. API

| Method | Path | Scope | Purpose |
| --- | --- | --- | --- |
| `POST` | `/routes/import` | write | Multipart import of one or more files. |
| `POST` | `/routes/from_activity/{activity_id}` | write | Save an activity slice as a route. |
| `POST` | `/routes` | write | Create from the builder (`geometry`, `builder_state`, `waypoints`). |
| `GET` | `/routes` | read | The caller's library: search `q`, `activity_type`, distance range, `source`; pagination. |
| `GET` | `/routes/{id}` | read | Detail (visibility checked; endpoint trimming for non-owners). |
| `PUT` | `/routes/{id}` | write | Edit metadata, geometry or builder state, POIs, visibility. |
| `DELETE` | `/routes/{id}` | write | |
| `POST` | `/routes/{id}/copy` | write | Save a visible route to my routes. |
| `POST` / `DELETE` | `/routes/{id}/share_token` | write | Create or rotate, and revoke, the unlisted link. |
| `GET` | `/routes/{id}/export` | read | GPX now; TCX and FIT later. |
| `GET` | `/users/{id}/routes` | read | Routes on a profile visible to the viewer. |
| `POST` | `/routes/routing/leg` | write | Routing proxy (rate-limited). |
| `POST` | `/routes/elevation` | write | Elevation lookup for freehand legs (rate-limited). |
| `GET` | `/public/routes/by_token/{token}`, `/public/routes/{id}` | none | Public page data, gated by `public_shareable_links`. |
| `GET` | `/public/routes/by_token/{token}/export`, `/public/routes/{id}/export` | none | Public GPX download, gated the same way. |

## 12. Frontend

- **New feature folder** `frontend/src/features/routes/`:
  - `views/RoutesView.vue` (`/routes`): a grid of thumbnail cards with
    distance, elevation and sport; filters; an import button (drag and drop);
    and "New route".
  - `views/RouteDetailView.vue` (`/route/:id`): map, elevation profile with a
    hover cursor (map seam `cursor` from the segments proposal), POI list,
    stats, and the actions export, share, copy, edit, delete. A "Completions"
    section comes in Phase 5.
  - `views/RouteEditorView.vue` (`/routes/new`, `/route/:id/edit`): the
    builder.
  - `views/PublicRouteView.vue` (`/r/:token`): anonymous and minimal; the
    router meta allows unauthenticated access.
  - Components: `RouteImportDialog.vue`, `RouteShareDialog.vue`,
    `RouteExportMenu.vue`, `ElevationProfile.vue` (shared with activities and
    segments), `RouteEditorToolbar.vue`, and `DistanceRangePicker.vue` (shared
    with segment creation).
- **Activity detail:** a "Save as route" entry in `ActivityActionsMenu.vue`
  (owner only).
- **Navigation:** a "Routes" entry in the main navigation and in
  `MenuMobileView.vue`.
- **Server settings UI:** routing and elevation providers, URL and API key
  (write-only field, as for the tile-server key), and the upload limit.
- **i18n:** a `routes` namespace in all 30 locales. Regenerate
  `api.generated.ts`.

## 13. Implementation plan

| Phase | Scope | Size |
| --- | --- | --- |
| **1. Core library** | New root package `routes/` (register it in `backend/.importlinter`); `routes`, `route_file_import` and `utils` modules. Model and Alembic revision, scopes, GPX/FIT/TCX import, save from activity, CRUD, GPX export, thumbnail generalisation. Frontend list, detail, import dialog, "Save as route", elevation profile, navigation, i18n. Needs `core/geo.py`: if segments Phase 0 hasn't landed, build it here. | M · 7–9 days |
| **2. Sharing** | Followers and public visibility, share tokens, public router and public page, profile tab, copy to my routes, endpoint trimming, home-location warning. | S–M · 3–5 days |
| **3. Builder (freehand)** | Map seam editor capability and Leaflet implementation, editor state reducer with undo and redo, POI editing, save and edit flows, elevation via an optional DEM provider. | M · 5–7 days |
| **4. Routing engines** | Provider protocol, BRouter adapter, routing proxy with Redis cache and rate limits, server settings and UI, self-hosting docs; then GraphHopper and openrouteservice adapters. | M · 4–6 days |
| **5. Extras** | TCX and FIT course export, route completions (after the segments matcher), KML/GeoJSON import, Strava routes import (private only), vendor push investigation, federation. | 2–5 days each |

Phases 1 and 2 deliver a complete, useful feature (import, organise, share,
export) without any external service. Phases 3 and 4 can be scheduled on
demand.

## 14. Testing

- **Parser fixtures:**
  - GPX with `<rte>` only; untimed `<trk>` (OsmAnd style); multiple tracks
    and segments with a gap; `<wpt>` POIs with `<sym>`.
  - No elevation; huge point counts (simplification cap).
  - Malformed XML and entity-expansion attempts.
  - A FIT course with `course_point` messages, and a TCX course.
- **Round trip:** `import(export(route))` reproduces geometry within 1 m,
  distance within 0.5 %, and the POIs.
- **Access matrix:** owner, follower and stranger, plus anonymous ×
  visibility × token present, rotated or revoked × `public_shareable_links`
  on or off × `public_shareable_links_user_info`. Endpoint trimming is
  applied to every non-owner path, including export and copy.
- **Routing adapters:** recorded provider responses through an httpx mock
  transport (no network in CI); cache hit and miss; rate-limit responses;
  provider down → clear error and freehand fallback.
- **Frontend (Vitest):** the editor reducer (add, move, insert, delete, undo,
  redo, reverse, close loop), editor seam translation, the share dialog's
  states, and the import dialog's multi-file handling.

## 15. Open questions

1. Which routing engine should be supported first? Proposed: BRouter.
2. Should unlisted share tokens ship in v1, or should routes start with plain
   visibility?
3. FIT encoder: a third-party library or a hand-written course-only encoder?
   Either way, a licence check is needed.
4. Should users be able to save a route from *someone else's* visible
   activity, and if so, should that need the activity owner's consent?
5. Should route completions wait for segments, or should routes introduce
   `core/geo.py` and the matcher first?
6. Should public routes appear on an instance-wide "Explore routes" page?
