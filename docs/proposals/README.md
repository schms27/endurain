# Feature proposals: Strava-inspired features

Status: **Draft for discussion** · Date: 2026-10-18

This folder holds feasibility analyses and implementation plans for three
features inspired by Strava. Each proposal stands on its own; this page
summarises them and shows how they relate.

| Proposal | Verdict | Size | Depends on |
| --- | --- | --- | --- |
| [Segments, segment records and comparison](segments-and-records.md) | Feasible, high value | L (≈ 20–30 person-days for phases 0–3) | none |
| [Local Legends](local-legends.md) | Feasible and cheap, value depends on instance size | S (≈ 5–8 person-days) | Segments, phases 0–2 |
| [Custom routes: create, import, share](custom-routes.md) | Feasible; core is low risk, route builder is the main cost | M–L (≈ 20–27 person-days for phases 1–4; phases 1–2 alone ≈ 10–14) | none (optional synergy with Segments) |

Sizes are rough estimates for one developer who knows the codebase, and
include tests and i18n. They are meant for ordering the work, not for
scheduling it.

## How the proposals relate

```text
                 ┌──────────────────────────────┐
                 │ Shared geo foundation        │
                 │ core/geo.py + activity bbox  │
                 └──────┬───────────────┬───────┘
                        │               │
          ┌─────────────▼───┐     ┌─────▼─────────────────┐
          │ Segments &      │     │ Custom routes         │
          │ records         │     │ (import/export/share) │
          └──────┬──────────┘     └─────┬─────────────────┘
                 │                      │
     ┌───────────▼──────┐   ┌───────────▼──────────────────┐
     │ Local Legends    │   │ Route completions            │
     │ (needs efforts)  │   │ (reuses the segment matcher) │
     └──────────────────┘   └──────────────────────────────┘
```

- **Shared foundation.** Both segments and routes need the same small set of
  geometry helpers: vectorised distances, cumulative distance along a track,
  Douglas–Peucker simplification, resampling by distance, and bounding boxes.
  They also benefit from a per-activity bounding box for fast candidate
  lookup. That foundation is planned once, as *Phase 0* of the segments
  proposal, and the routes proposal reuses it.
- **Map seam.** All three features outgrow today's `useMapProvider` contract
  (one polyline plus start and finish markers, display only). The segments
  proposal adds optional overlays and a hover cursor; the routes proposal adds
  an optional editor capability. Both extensions are additive and backwards
  compatible.
- **Visibility model.** Every proposal reuses the activity visibility codes
  (0 public, 1 followers, 2 private), the `hide_*` flags, and
  `_visible_to_requester_condition()` instead of inventing new access rules.

## Recommended order

1. **Segments, phases 0–2.** This delivers the highest value (personal
   records on your own routes are useful on a single-user instance) and lays
   the shared geo foundation.
2. **Custom routes, phases 1–2** (import, from activity, export, sharing).
   These are independent of segments and can run in parallel once Phase 0
   lands.
3. **Local Legends.** Small, and only worth doing once segments exist and the
   instance has several active users.
4. **Segment comparison (Segments, phase 3)** and the **route builder
   (Routes, phases 3–4)**, depending on demand.

## Cross-cutting constraints

- **PostgreSQL without PostGIS.** The stock deployment uses the
  `postgres:18` image. Requiring PostGIS would force a database image change
  on every existing install (Docker, bare metal, the Proxmox script). All three
  proposals therefore keep spatial work in Python/numpy behind a bounding-box
  prefilter. Core PostgreSQL `box` columns with GiST indexes are the upgrade
  path if that ever becomes too slow.
- **Strava API terms.** Strava's API agreement (revised in late 2024) limits
  showing a user's Strava data to anyone other than that user. The proposals
  never import Strava segments, leaderboards or Local Legend data. They also
  flag where Strava-synced activities could surface to other users. Check the
  current terms before implementing.
- **Privacy.** Leaderboards and Local Legends reveal where, and how often,
  people train. Endurain has no privacy zones today. Each proposal lists its
  mitigations: an opt-out, excluding `hide_map` activities, counting public
  activities only for Local Legends, and endpoint trimming for shared routes.
  A separate *privacy zones* feature would strengthen all three.
- **Project conventions.** New backend root packages must be registered in
  `backend/.importlinter`. New read/write endpoints need scopes in
  `auth/constants.py`. Schema changes ship as Alembic revisions and backfills
  as numbered data migrations in `backend/app/migrations/`. The frontend needs
  `api.generated.ts` regenerated (CI checks for OpenAPI drift), and new i18n
  keys must exist in all 30 locales (parity test).
