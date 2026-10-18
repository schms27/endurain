# Proposal: Segments, segment records and effort comparison

Status: **Draft** · Date: 2026-10-18 · Inspired by: Strava Segments ·
Index: [proposals overview](README.md)

## 1. Summary

A **segment** is a named stretch of road or trail, such as "Castle climb" or
"River path 2 km", that a user cuts out of one of their own GPS activities.
Endurain then matches every activity of a compatible sport against it. Each
pass from the segment's start to its end, in the right direction, becomes an
**effort** with an elapsed time and summary metrics. From efforts we derive:

- **Personal records**: PR, 2nd and 3rd best time per segment, with medals
  on the activity page ("PR!", "2nd best time").
- **Leaderboards** across the instance, filtered by who may see which
  activity.
- **Comparison** of two efforts: time gap over distance, speed, HR and power
  overlays, and both lines on one map.

The core value works on a single-user instance. Seeing your own progression
on your regular climbs needs no other users. Leaderboards add social value on
multi-user instances.

## 2. Goals and non-goals

**Goals**

- Create a segment from a slice of your own GPS activity.
- Match new activities, from every import path, and historical activities
  against segments automatically and in the background.
- Personal records and historical achievements per effort.
- Leaderboards that respect Endurain's visibility and privacy model.
- Side-by-side comparison of two efforts.

**Non-goals (v1)**

- Importing Strava segment definitions, efforts or leaderboards (see §10).
- Cross-instance (federated) leaderboards. That belongs to the roadmap item
  *Federation (via ActivityPub)*.
- A segment explore map, live segments on devices, and KOM/QOM-style crowns.
- Local Legends, which is a separate proposal built on top of this one: see
  [local-legends.md](local-legends.md).

## 3. What exists today

| Area | Current state | Relevance |
| --- | --- | --- |
| GPS data | `activities_streams` row with `stream_type = 7` (`STREAM_TYPE_MAP`) holds a JSON list of `{"time", "lat", "lon"}`. HR (1), power (2), cadence (3), elevation (4), speed (5), pace (6) and temperature (8) are separate rows keyed by the same `time`. | The matcher input. There is no distance stream (we compute one) and no per-activity bounding box (we add one). |
| Write path | File upload (`activities/activity/utils.py::store_activity`), Strava sync (`strava/activity_utils.py`) and profile import (`users/users_profile/import_service.py`) all call `activities/activity_streams/crud.py::create_activity_streams`. | One hook point for every import path. HR zone percentages already use it. |
| Background work | APScheduler in `core/scheduler.py`, including one-shot `date` jobs (`schedule_thumbnail_regeneration`). | Runs matching off the request path. The jobstore is in-memory, so jobs are lost on restart (see §7.4). |
| Backfills | Numbered data migrations in `backend/app/migrations/`. `migration_7.py` backfills HR zones in id-ordered batches. | Pattern for backfilling activity bounding boxes. |
| Visibility | `activities.visibility` (0 public, 1 followers, 2 private), `is_hidden`, the `hide_*` flags, and `_visible_to_requester_condition()` in `activities/activity/crud.py` (public, or followers-only with an accepted follow). | Reused as-is for leaderboard filtering. |
| Stream helpers | `filter_waypoints_by_time_range`, `calculate_avg_and_max`, `calculate_np`, `compute_elevation_gain_and_loss`, `is_stream_hidden`. numpy and geopy are dependencies. | Effort metrics and masking. |
| Database | PostgreSQL only, stock `postgres:18` image, no PostGIS. | Spatial work happens in Python behind a bounding-box prefilter. |
| Frontend | Feature folders under `frontend/src/features/*`. Maps go through the `useMapProvider` seam (one polyline, start and finish markers, Leaflet implementation); charts through `useChartProvider`. 30 locales with a parity test. | New `features/segments`; additive map-seam extension. |
| Sport groups | `users/users_goals/utils.py::_ACTIVITY_TYPE_MAP` groups activity types for goals. It includes virtual and indoor types. | Segments need their own map without virtual and indoor types. |

## 4. Feasibility

**Verdict: feasible, high value, large effort. No blockers.**

| Risk | Assessment | Mitigation |
| --- | --- | --- |
| Matching accuracy without a spatial database | Moderate. GPS noise, smart recording, tunnels and parallel roads are known problems with known heuristics. | Gate, corridor and length-ratio checks (§7). Synthetic test suite. The owner can exclude a bad effort. |
| Matching cost | Low per activity: O(track points) per candidate segment after the bounding-box prefilter, vectorised with numpy. The cost is backfilling a new segment against history. | Per-activity bounding-box columns, a durable queue, background jobs in batches. |
| Privacy | Leaderboards reveal where and when people train. Endurain has no privacy zones. | Reuse visibility rules; exclude `hide_map` activities; a user-level opt-out; mask hidden metrics (§8.4). |
| Small user bases | Many instances have 1 to 5 users, so leaderboards are thin. | Personal records are the main value; leaderboards are a bonus. |
| Abuse and spam | Low on private instances. | Server setting for who may create public segments; admin archive and delete. |

**Why not PostGIS?** It would change the database image for every existing
deployment (Docker, bare metal, the Proxmox script) and for the MariaDB to
Postgres migration path. At instance scale (thousands to tens of thousands of
activities) a bounding-box B-tree prefilter plus numpy is fast enough. The
geometry code lives in one module (`core/geo.py`), so a PostGIS or core
`box`/GiST backend could be added later without touching callers.

## 5. Concepts and rules

- **Sport group.** Each segment belongs to one group, and only activities in
  that group are matched. Virtual and indoor types are always excluded,
  because their coordinates are synthetic or missing.

  | Group | Activity types |
  | --- | --- |
  | `run` | Run (1), Trail run (2), Track run (34) |
  | `ride` | Road (4), Gravel (5), MTB (6), Commuting (27), Mixed surface (29) |
  | `e_ride` | E-Bike (35), E-Bike mountain (36) |
  | `foot` | Walk (11), Hike (12), Snow shoeing (44) |

  Excluded: Virtual run (3), Virtual cycling (7), Indoor cycling (28),
  Indoor walk (31), Treadmill (40), and all non-GPS sports. The map lives in
  `segments/constants.py` and can grow later (Nordic ski, inline skating).
- **Effort.** Crossing the start gate, then crossing the end gate, in segment
  direction, while staying in the corridor. Time is **elapsed** (wall clock,
  pauses included). One activity can hold several efforts, for example laps.
- **Personal record.** For a (segment, user) pair, the best elapsed time is
  the PR. The **historical achievement** of an effort is its rank among that
  user's efforts up to that date. Medals are shown for ranks 1 to 3.
- **Leaderboard rank.** Users are ranked by their best visible effort.
- **Segment visibility.** `public` (0): matched against every user's
  activities. `private` (2): matched only against the creator's activities,
  and only the creator sees it. *Followers-only segments are deferred*: they
  would require rematching every time the follow graph changes.
- **Immutable geometry.** A segment's geometry cannot be edited after
  creation, so existing efforts always stay valid. Name, description and
  visibility can be edited. To change the path, create a new segment.

## 6. Data model

All tables are new except the `activities` bounding-box columns. One Alembic
revision covers the schema; data migration 8 backfills the bounding boxes.

### 6.1 `segments`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | PK | |
| `user_id` | FK `users.id` `ON DELETE SET NULL` | Creator. Private orphans are deleted by the user-deletion routine. |
| `name` | `String(250)` | |
| `description` | `String(2500)` nullable | |
| `sport_group` | `SmallInteger` | See §5. |
| `visibility` | `SmallInteger` | 0 public, 2 private (same codes as activities). |
| `geometry` | `JSON` | `[[lat, lon, ele \| null], …]`, simplified with Douglas–Peucker (about 2 m). |
| `distance` | `DECIMAL` | Metres, from the unsimplified source points. |
| `elevation_gain`, `elevation_loss` | `Integer` nullable | |
| `average_grade`, `maximum_grade` | `DECIMAL` nullable | Maximum grade over 100 m windows. |
| `start_lat`, `start_lon`, `end_lat`, `end_lon` | `Float` | |
| `bbox_min_lat`, `bbox_min_lon`, `bbox_max_lat`, `bbox_max_lon` | `Float`, indexed | Candidate lookup. |
| `city`, `town`, `country` | `String(250)` nullable | From `location_based_on_coordinates` at the start point. |
| `source_activity_id` | FK `activities.id` `ON DELETE SET NULL` | |
| `is_archived` | `Boolean` | Moderation: hidden from search and no longer matched. |
| `matcher_version` | `SmallInteger` | The algorithm version that produced its efforts (§7.5). |
| `effort_count`, `athlete_count` | `Integer` | Denormalised counters for lists. |
| `created_at`, `updated_at` | `DateTime(tz)` | |

### 6.2 `segment_efforts`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | PK | |
| `segment_id` | FK `ON DELETE CASCADE` | |
| `activity_id` | FK `ON DELETE CASCADE` | |
| `user_id` | FK `ON DELETE CASCADE` | Denormalised for leaderboard queries. |
| `start_time` | `DateTime(tz)` | Interpolated start-gate crossing. |
| `elapsed_time` | `DECIMAL(20,10)` | Seconds, matching `activities.total_elapsed_time`. |
| `distance` | `DECIMAL` | Length of the activity's sub-track. |
| `start_index`, `end_index` | `Integer` | Positions in the activity's lat/lon stream. |
| `average_hr`, `max_hr`, `average_power`, `normalized_power`, `average_cad`, `average_speed` | nullable | Computed at match time; masked on read (§8.4). |
| `is_excluded` | `Boolean` | The owner hid the effort (GPS glitch, car ride). |
| `created_at` | `DateTime(tz)` | |

Indexes: `(segment_id, elapsed_time)`, `(segment_id, user_id, elapsed_time)`,
`(segment_id, start_time)` (also used by Local Legends), `(activity_id)`.
Unique constraint: `(activity_id, segment_id, start_index)`, which makes
matching idempotent.

### 6.3 Supporting changes

- **`activities`**: add `bbox_min_lat`, `bbox_min_lon`, `bbox_max_lat`,
  `bbox_max_lon` (nullable `Float`) and an index on
  `(activity_type, bbox_min_lat, bbox_max_lat)`. Populate them inside
  `create_activity_streams` when the map stream is written, the same place HR
  zone percentages are computed. Data migration 8 backfills existing
  activities in batches, following `migration_7.py`.
- **`segment_match_queue`** (`activity_id`, `segment_id` nullable,
  `enqueued_at`, `attempts`): a durable work queue (§7.4).
- **`users_privacy_settings`**: add `hide_from_segment_leaderboards`
  (`Boolean`, default `false`).
- **`server_settings`**: add `segments_enabled` (default `true`),
  `segments_public_creation` (`all` | `admins`, default `all`), and
  `segments_hide_strava_activities_from_others` (default `true`, see §10).
- **Phase 4**: `segment_stars` (`user_id`, `segment_id`) composite PK.

**Bounding-box upgrade path.** If B-tree range scans ever become a
bottleneck, replace the four columns with a core PostgreSQL `box` column and a
GiST index (`bbox && box(...)`). Both are built in and need no extension.

## 7. Matching

### 7.1 Geometry foundation: `core/geo.py` (Phase 0)

Pure functions on numpy arrays, with no database access, so they are easy to
test and reusable by the routes proposal:

- Local equirectangular projection to metres around a reference point. This
  is accurate to well under 1 % for segment-scale extents and much faster than
  per-point `geopy.geodesic`.
- Vectorised point-to-point and point-to-polyline distances.
- Cumulative distance along a track; `bbox(points, pad_m)`.
- Douglas–Peucker simplification; resampling at a fixed distance step.
- Projecting a point onto a polyline edge, with linear interpolation of the
  edge timestamps.

### 7.2 Algorithm

Parameters live in `segments/constants.py` and can be tuned with tests:

| Parameter | Proposed default | Purpose |
| --- | --- | --- |
| `GATE_RADIUS_M` | 25 | Distance to the start or end point that counts as a gate pass. |
| `CORRIDOR_M` | 30 | Maximum distance from the activity polyline to a segment sample. |
| `SAMPLE_SPACING_M` | 10 | Spacing for corridor samples along the segment. |
| `MIN_COVERAGE` | 0.90 | Fraction of segment samples that must lie inside the corridor. |
| `LENGTH_RATIO` | 0.85 – 1.30 | Sub-track length divided by segment length (catches detours and shortcuts). |
| `MAX_GAP_M` | 500 | Reject if two consecutive points inside the effort are further apart. |

For one activity A and one candidate segment S:

```text
1. Project A's points and S's geometry to local metres around S.start.
2. start_passes = contiguous index runs where dist(A[i], S.start) < GATE_RADIUS_M;
   each run yields one candidate: the closest point to S.start, refined by
   projecting S.start onto the adjacent edges.
   end_passes = the same for S.end.
3. For each start pass s (in time order):
     for each end pass e after s (in time order, skipping the same pass for
     loop segments):
       L = cumulative_distance(A[s..e])
       if not LENGTH_RATIO.lo <= L / S.distance <= LENGTH_RATIO.hi: continue
       if max_gap(A[s..e]) > MAX_GAP_M: continue
       coverage = fraction of S samples within CORRIDOR_M of polyline A[s..e]
                  (monotone sliding window: both sequences are ordered along
                   the path, so the check is O(M + K) rather than O(M·K))
       if coverage >= MIN_COVERAGE:
           emit effort(s, e); continue with the next start pass after e
           break
4. For each effort: t_start and t_end come from interpolating the timestamps
   of the projected gate points; elapsed = t_end - t_start.
   Metrics come from the HR, power, cadence and elevation streams over
   [t_start, t_end] via filter_waypoints_by_time_range + calculate_avg_and_max.
```

Direction is enforced by the start-before-end ordering. An out-and-back
activity on a one-way segment yields exactly one effort. Shortcuts fail the
coverage check. Large detours fail the length ratio, and small detours only
cost time. A parallel road closer than `CORRIDOR_M` can produce a false
positive. That is accepted, and the owner can exclude the effort.

### 7.3 Candidate selection

- **New activity:** non-archived segments with the same `sport_group`
  (public, or private and owned by the activity's owner) whose bounding box
  intersects the activity's bounding box padded by `GATE_RADIUS_M`.
- **New segment:** activities in the segment's sport group, not `is_hidden`
  (and owned by the creator if the segment is private), whose bounding box
  intersects the segment's. Processed in id-ordered batches of 200.

### 7.4 Triggers and job execution

| Event | Action |
| --- | --- |
| Activity created (any import path) | `create_activity_streams` enqueues `(activity_id)` after commit. |
| Segment created | Enqueue `(segment_id)` for a backfill. |
| Activity type edited | Re-enqueue the activity (old efforts deleted, then rematched). |
| Duplicate un-hidden (`is_hidden` → false) | Enqueue the activity. |
| Activity deleted | FK cascade removes its efforts; counters are refreshed. |
| Matcher version bumped | At startup, enqueue segments with `matcher_version < MATCHER_VERSION`. |

`segment_match_queue` is drained by an APScheduler interval job (every minute)
plus an immediate one-shot kick after each enqueue. A durable table, rather
than one in-memory APScheduler job per activity, is used because:

- Bulk imports (Strava bulk import, folder import) can enqueue thousands of
  activities.
- The in-memory jobstore loses work on restart.
- With several uvicorn workers, a `pg_try_advisory_lock` around the drain
  prevents duplicate processing. The unique constraint on efforts is the
  second line of defence.

Each queue item is processed in its own transaction: delete existing efforts
for that (activity, segment) scope, insert new ones, refresh the counters. The
owner can be notified through the existing websocket manager, so the activity
page can refresh its segment card.

### 7.5 Matcher versioning

`MATCHER_VERSION` is a constant. When the algorithm or its defaults change in
a way that alters results, bump it. Affected segments are rematched in the
background, and `segments.matcher_version` records which version produced the
stored efforts.

## 8. Records, leaderboards and comparison

### 8.1 Personal records and achievements

These are computed on read; ranks are not stored, so deletions never leave
stale medals:

- **Historical achievement** of effort E (user U, segment S):
  `1 + count(U's efforts on S with elapsed < E.elapsed and start_time < E.start_time)`.
- **Current standing:** `1 + count(U's efforts on S with elapsed < E.elapsed)`.

Both are index-only lookups on `(segment_id, user_id, elapsed_time)`. The
activity detail endpoint returns efforts with both values, plus the delta to
the current PR ("+0:12 vs PR").

### 8.2 Leaderboard query

```sql
WITH visible AS (
  SELECT e.*
  FROM segment_efforts e
  JOIN activities a ON a.id = e.activity_id
  JOIN users_privacy_settings p ON p.user_id = e.user_id
  WHERE e.segment_id = :segment_id
    AND e.is_excluded = false
    AND a.hide_map = false
    AND (e.user_id = :viewer_id
         OR (p.hide_from_segment_leaderboards = false
             AND <_visible_to_requester_condition(:viewer_id)>))
    AND e.start_time >= :period_start            -- optional period filter
), best AS (
  SELECT DISTINCT ON (user_id) *
  FROM visible
  ORDER BY user_id, elapsed_time, start_time
)
SELECT best.*, rank() OVER (ORDER BY elapsed_time) AS rank
FROM best
ORDER BY elapsed_time
LIMIT :limit OFFSET :offset;
```

Filters: `scope` (`everyone`, `following`, `me`) and `period` (`all`,
`this_year`, `last_90_days`). Gender and age-group filters (from
`users.gender` and `users.birthdate`) are deferred to Phase 4 because they
reveal personal attributes.

### 8.3 Comparison

`GET /segment_efforts/compare?a=<id>&b=<id>` returns both efforts resampled
onto a shared distance grid (every 10 m, at most 500 points):

1. Cumulative distance along each effort's sub-track, scaled so both span
   `[0, segment.distance]`.
2. `np.interp` time, speed, HR, power, cadence and elevation onto the grid.
3. `gap[d] = t_a[d] − t_b[d]` (positive means A is behind B).

The frontend shows:

- A gap chart with a zero baseline.
- Overlay charts by distance for speed or pace, HR and power.
- A stats table side by side.
- A map with both sub-tracks and a cursor that follows the charts.

Default entry points are "Compare with my PR", "Compare with leader" and
"Compare with …" from a leaderboard row. Both efforts must be visible to the
viewer, and hidden metrics are omitted (§8.4).

### 8.4 Privacy rules for showing efforts to a non-owner viewer

1. The segment is public (or the viewer owns it).
2. The viewer can see the effort's activity (`_visible_to_requester_condition`).
3. The activity does not have `hide_map` set, because an effort reveals the
   route.
4. The owner has not set `hide_from_segment_leaderboards`.
5. The effort is not `is_excluded`.
6. If `hide_start_time` is set, the effort is listed without its date.
7. Metric masking mirrors streams: `hide_hr` nulls the HR fields,
   `hide_power` the power fields, `hide_cadence` the cadence, and `hide_speed`
   / `hide_pace` the speed. Elapsed time is the effort itself and is always
   shown.
8. If `segments_hide_strava_activities_from_others` is on, efforts from
   activities with `strava_activity_id IS NOT NULL` are only shown to their
   owner.
9. No anonymous or public-link access to leaderboards in v1.

## 9. API

New scopes `segments:read` and `segments:write` go in `auth/constants.py`.
They are part of the regular access scope, and the API-key read-only scope
sets should include `segments:read`.

| Method | Path | Scope | Purpose |
| --- | --- | --- | --- |
| `POST` | `/segments` | write | Create from `{activity_id, start_index, end_index, name, description, visibility}`. |
| `GET` | `/segments/similar` | read | Duplicate check for a proposed slice: same group and direction, start and end within 30 m, length within 5 %. |
| `GET` | `/segments/{id}` | read | Detail: geometry, stats, the viewer's PR and rank. |
| `PUT` | `/segments/{id}` | write | Edit name, description, visibility (owner or admin). |
| `DELETE` | `/segments/{id}` | write | Owner or admin. |
| `GET` | `/segments` | read | Search by `q`, `sport_group`, `bbox`, `created_by=me`, with pagination. |
| `GET` | `/segments/{id}/leaderboard` | read | `scope`, `period`, pagination; includes the viewer's own row. |
| `GET` | `/segments/{id}/efforts` | read | The viewer's effort history on the segment. |
| `GET` | `/activities/{id}/segment_efforts` | `activities:read` | Efforts in an activity, with achievements. |
| `PATCH` | `/segment_efforts/{id}` | write | The owner excludes or includes an effort. |
| `GET` | `/segment_efforts/compare` | read | Resampled comparison (§8.3). |
| `POST` | `/segments/{id}/rematch` | write (admin) | Force a backfill. |

Creation validation:

- The activity is the caller's own and has a lat/lon stream.
- Its activity type maps to a segment sport group.
- Length is at least 200 m (`run`, `foot`) or 400 m (`ride`, `e_ride`), and
  at most 100 km.
- The slice has at least 10 points and passes the `MAX_GAP_M` check.
- `segments_public_creation` is enforced for public segments.

## 10. Strava and third-party data

- **Do not import Strava segments, segment efforts or leaderboards.** The
  Strava API agreement restricts using and showing Strava data beyond the
  authenticated athlete; it was tightened in late 2024 to forbid showing a
  user's data to other users. Check the current terms before implementing.
- Activities synced from Strava are the user's own recordings. Their GPS data
  can be matched for the owner's own records, but showing them on other users'
  leaderboards is a grey area. The server setting
  `segments_hide_strava_activities_from_others` defaults to `true`. Users who
  want to appear can upload the original FIT files.
- Seeding segments from OpenStreetMap (named climbs, for example) is out of
  scope.

## 11. Frontend

- **New feature folder** `frontend/src/features/segments/`:
  - `services/segments.ts`, query keys in `services/queryKeys.ts`, types from
    the regenerated `api.generated.ts`.
  - `views/SegmentDetailView.vue` (`/segment/:id`): stats header (distance,
    average grade, elevation gain, location), a map with the segment line, an
    elevation profile, and tabs for *Leaderboard* and *My efforts* (an
    elapsed-time-over-date chart plus a list). Actions: edit, delete, rematch
    (admin).
  - `views/EffortCompareView.vue` (`/segment/:id/compare?a=&b=`).
  - `components/ActivitySegmentEfforts.vue`: a card on the activity detail
    page with name, time, pace or speed, medal (historical achievement),
    current rank ("3 / 12") and delta to PR. Hovering a row highlights the
    segment on the activity map.
  - `components/SegmentCreateDialog.vue`, owner only:
    - A two-thumb range slider over the activity's cumulative distance, with
      a live highlight on the map and the elevation chart. This needs no map
      click handling in v1.
    - Name, description and visibility fields.
    - A duplicate warning from `/segments/similar`.
    - On save, a toast: "Matching your activities in the background".
- **Map seam extension** (additive and optional, so the no-op and minimal
  providers keep working):

  ```ts
  export interface MapOverlay {
    id: string
    points: GeoPoint[]
    /** Semantic style; the provider resolves colours from design tokens. */
    style?: 'highlight' | 'secondary' | 'muted'
  }

  export interface MapRenderOptions {
    track: MapTrack
    interactive?: boolean
    /** Extra polylines drawn above the main track. */
    overlays?: MapOverlay[]
    /** Position marker synchronised with chart hover; null hides it. */
    cursor?: GeoPoint | null
  }
  ```

  The Leaflet implementation and `leafletMapProvider.spec.ts` are extended
  accordingly.
- **Charts:** the elevation profile, effort history and gap chart go through
  `useChartProvider`. Extend the seam if a distance-based x-axis is not yet
  supported.
- **i18n:** a new `segments` namespace in all 30 locales (parity test).
  English values can be copied to the other locales as placeholders.
- **Server settings UI:** the three new settings in the admin server
  settings page. **Privacy settings UI:** the leaderboard opt-out.

## 12. Implementation plan

| Phase | Scope | Size |
| --- | --- | --- |
| **0. Geo foundation** | `core/geo.py` with unit tests; activity bounding-box columns, Alembic revision, data migration 8 backfill; bounding box set in `create_activity_streams`. | S · 3–4 days |
| **1. Segments and matching** | New root package `segments/` (register it in `backend/.importlinter` `root_packages` and the auth-boundary `source_modules`). Sub-packages `segments.segment`, `segments.segment_efforts`, `segments.matching`. Models and migration, CRUD, schemas, routers, scopes. Matcher, queue table, drain job, hook in `create_activity_streams`, backfill on create, matcher versioning. Synthetic-track test suite. | L · 8–12 days |
| **2. Records and leaderboards** | Achievements on read, leaderboard query with the visibility matrix, privacy opt-out, server settings, activity detail card, segment detail page, create dialog, map overlay seam, i18n, regenerated API types. | M · 5–7 days |
| **3. Comparison** | Compare endpoint, gap and overlay charts, dual-track map with cursor sync. | M · 4–6 days |
| **4. Extras (optional)** | Stars and "My segments" list; nearby-segment search by map viewport (needs viewport events in the map seam); admin moderation list; "New PR" notification; gender and age filters; **best efforts** (see below). | 2–5 days each |

**Best efforts, a cheap add-on.** Distance-based records (400 m, 1 km, 1 mi,
5 km, 10 km, half marathon, marathon for runs) need no geography. A sliding
window over the cumulative-distance array from `core/geo.py` finds the fastest
sub-window in each activity. The results go in an `activity_best_efforts`
table and reuse the PR medal UI. Like segment PRs, this is valuable on a
single-user instance, and it can ship right after Phase 0.

**Sequencing inside Phase 1.** Build `core/geo.py` and the matcher first,
against fixtures and with no database. Then the models and the queue. The
import hook comes last, so a half-finished matcher never runs on real imports.

## 13. Testing

- **Matcher unit tests** with synthetic tracks generated in metres and
  projected to lat/lon:
  - A straight segment with Gaussian GPS noise (σ = 5 m) matches.
  - Reverse direction does not match.
  - Out-and-back gives one effort per matching direction.
  - Three laps give three efforts.
  - A loop segment (start equals end) works.
  - A park shortcut fails coverage.
  - A parallel road 50 m away fails.
  - A tunnel gap under `MAX_GAP_M` passes; a larger gap fails.
  - 1 s recording and smart recording (1–10 s) agree on elapsed time within
    ±1 s.
- **Property-based tests** with Hypothesis (already used in the backend):
  elapsed time is positive, efforts do not overlap, rematching is idempotent.
- **Visibility matrix** for leaderboards and comparison: owner, follower and
  stranger × visibility 0/1/2 × `hide_map` × opt-out × Strava setting ×
  `hide_hr` masking.
- **Queue and jobs:** enqueue on all three import paths, survival across a
  restart (rows persist), idempotency under concurrent drains.
- **Performance smoke test:** a 20 000-point track against 200 candidate
  segments in under 1 s on CI hardware.
- **Frontend (Vitest):** seam translation for overlays and the cursor, the
  range-slider-to-index mapping, gap chart data mapping, and composables.
- Backend tests run in WSL on Windows development machines, as described in
  the developer setup.

## 14. Open questions

1. Should walking and hiking share segments with running (one `foot` group)
   or stay separate as proposed?
2. Are followers-only segments needed in v1, given that they force rematching
   when follows change?
3. Should `segments_hide_strava_activities_from_others` default to on
   (conservative) or off?
4. Minimum and maximum segment lengths per sport group.
5. Who may create public segments by default: all users or admins only?
6. Elapsed time (proposed, Strava parity) versus moving time for ranking.
