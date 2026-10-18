# Proposal: Local Legends

Status: **Draft** · Date: 2026-10-18 · Inspired by: Strava Local Legends ·
Index: [proposals overview](README.md)

## 1. Summary

For each segment, the **Local Legend** is the athlete with the most efforts
on that segment over a rolling 90-day window. It rewards consistency instead
of speed, so it complements the time-based leaderboards in the segments
proposal. Someone who runs the same river path four times a week can hold the
title without ever being the fastest.

## 2. Dependency

**Hard dependency: [Segments](segments-and-records.md), phases 0–2.** Local
Legends counts rows in `segment_efforts` and reuses the segment visibility
rules (§8.4 of the segments proposal) and its privacy opt-out. Without
segments there is nothing meaningful to count.

*Rejected alternative:* an "area legend" on map tiles, such as the most
active user per 1 km cell. It needs no segments, but it is far more
privacy-invasive (it effectively maps where people live and train) and less
meaningful.

## 3. Feasibility

**Verdict: technically easy and cheap once segments exist. Product value
depends on the instance having several active users. Privacy is the main
design concern.**

| Aspect | Assessment |
| --- | --- |
| Computation | One aggregate query per segment over an index that already exists (`segment_efforts (segment_id, start_time)`). Recomputing every segment nightly is trivial at instance scale. |
| Effort | Small: about 5–8 days including UI, notifications, i18n and tests. |
| Value on single-user instances | Low. With one user, that user is the legend of every segment. Mitigated by a minimum-athletes threshold and a personal "consistency" panel (§6.4). |
| Value on family, club or community instances | Good. It is a social, low-pressure motivator. |
| Privacy | The most sensitive of the three proposals. It reveals how regularly someone is at a place. Mitigated by counting only public activities, never exposing other users' effort dates in Local Legend views, and opt-outs (§7). |
| Gaming | Laps of a short segment inflate counts. Mitigated by counting at most one effort per activity. Virtual and indoor activities are already excluded by the segment sport groups; hidden duplicates are excluded. |

## 4. Rules

| Rule | Proposal |
| --- | --- |
| Window | Trailing `local_legends_window_days` (default 90) from now, compared against `segment_efforts.start_time` in UTC. |
| What counts | Distinct activities with at least one qualifying effort on the segment (`COUNT(DISTINCT activity_id)`). Configurable to count every effort. |
| Qualifying effort (canonical title) | Segment is public and not archived. Activity has `visibility = 0` (public), is not `is_hidden`, and does not have `hide_map`. Effort is not `is_excluded`. Owner has neither `hide_from_segment_leaderboards` nor `hide_from_local_legends` set. The Strava-source rule from the segments proposal applies. |
| Minimum competition | A title is awarded only if at least `local_legends_min_athletes` (default 2) distinct users have qualifying efforts in the window. |
| Minimum count | The holder needs at least 2 qualifying activities in the window. |
| Tie-break | 1. The current holder keeps the title, which avoids flapping. 2. Otherwise, the athlete who reached the tied count first wins: the earliest time of their *k*-th qualifying effort in the window, where *k* is the tied count. 3. Lowest user id, as a deterministic last resort. |

**Two views, one title.**

1. **Canonical Local Legend.** Computed only from qualifying (public)
   efforts. It is stored, drives the laurel icon and notifications, and is
   shown to anyone who can see the segment. Counting followers-only
   activities here would leak to non-followers how often someone visited a
   place.
2. **"Among people you follow."** Computed per request from every effort the
   viewer may see (`_visible_to_requester_condition`), so followers-only
   activities count. It is never stored and never triggers notifications.

## 5. Data model

### 5.1 `segment_local_legends` (current holder)

| Column | Type | Notes |
| --- | --- | --- |
| `segment_id` | PK, FK `segments.id` `ON DELETE CASCADE` | One row per segment that currently has a legend. |
| `user_id` | FK `users.id` `ON DELETE CASCADE` | The holder. |
| `effort_count` | `Integer` | Qualifying count in the window at the last computation. |
| `holder_since` | `DateTime(tz)` | When the title was gained, for "Local Legend since …". |
| `computed_at` | `DateTime(tz)` | |

### 5.2 Optional (Phase 3): `segment_local_legend_history`

`(id, segment_id, user_id, held_from, held_until)` for "past titles" on the
profile page.

### 5.3 Settings

- **`server_settings`**:
  - `local_legends_enabled` (default `true`; it only takes effect when
    `segments_enabled` is on).
  - `local_legends_window_days` (default 90, range 7–365).
  - `local_legends_min_athletes` (default 2).
  - `local_legends_one_per_activity` (default `true`).
- **`users_privacy_settings`**: `hide_from_local_legends` (default `false`).
  It is independent of `hide_from_segment_leaderboards`: a user may want
  speed rankings but not a visible presence pattern. Setting the leaderboard
  opt-out also implies this one.

There are no changes to `segment_efforts`. The `(segment_id, start_time)`
index from the segments proposal covers the window scan; add
`(segment_id, user_id, start_time)` if profiling shows a need.

## 6. Computation

### 6.1 Query (canonical)

```sql
WITH qualifying AS (
  SELECT DISTINCT ON (e.user_id, e.activity_id)      -- one per activity
         e.user_id, e.activity_id, e.start_time
  FROM segment_efforts e
  JOIN activities a             ON a.id = e.activity_id
  JOIN users_privacy_settings p ON p.user_id = e.user_id
  WHERE e.segment_id = :segment_id
    AND e.start_time >= now() - make_interval(days => :window_days)
    AND e.is_excluded = false
    AND a.visibility = 0 AND a.is_hidden = false AND a.hide_map = false
    AND p.hide_from_segment_leaderboards = false
    AND p.hide_from_local_legends = false
  ORDER BY e.user_id, e.activity_id, e.start_time
), ranked AS (
  SELECT user_id, start_time,
         row_number() OVER (PARTITION BY user_id ORDER BY start_time) AS n,
         count(*)     OVER (PARTITION BY user_id)                     AS total
  FROM qualifying
)
SELECT user_id, total, start_time AS reached_total_at
FROM ranked
WHERE n = total                          -- time each user reached their count
ORDER BY total DESC, reached_total_at ASC, user_id ASC;
```

The service layer applies the minimum-athletes and minimum-count checks and
the incumbent rule. That is: if the current holder ties the top count, they
keep the title.

### 6.2 Module

The module is `segments/local_legends/` (`crud.py`, `schema.py`,
`router.py`, `utils.py`), inside the segments root package, so no
import-linter change is needed beyond the segments registration.
`utils.recompute_segment(segment_id, *, notify: bool) -> Change | None`
computes the holder, upserts or deletes the row, and returns a gained/lost
change for notification.

### 6.3 When to recompute

| Trigger | Scope |
| --- | --- |
| Segment queue item finished (efforts inserted or deleted for an activity) | Each segment touched. `notify=True` for new activities. |
| Segment backfill finished | That segment. `notify=False`, so creating a segment does not crown someone with a burst of notifications. |
| Activity visibility edited (`edit_activity_visibility`), activity deleted, `hide_map` toggled | Segments with an effort from that activity in the window. |
| Privacy opt-out toggled, user deleted | Segments where the user has efforts in the window, or holds the title. |
| **Daily job** (APScheduler, 03:30 server time) | Segments with a current holder, plus segments with any effort whose start time crossed the window boundary in the last 25 hours. Titles expire as the window slides even when nobody records anything. |
| Window, minimum or count settings changed | A full recompute as a one-shot job with `notify=False`. |

### 6.4 Personal consistency panel

The panel is shown on the segment page for any user: "You: 7 activities on
this segment in the last 90 days", plus a 13-week bar chart of *your own*
weekly counts. When a canonical legend exists, it adds "Local Legend: 11.
4 more to take the title." On single-user instances, or below the
minimum-athletes threshold, only this panel is shown.

## 7. Privacy and safety

- Only **public** activities count toward the canonical title, and
  `hide_map` activities never count.
- Local Legend views show **counts only**: never other users' effort dates,
  times of day, or weekly histograms. The histogram is only of the viewer's
  own efforts.
- Opt-outs: `hide_from_local_legends`, and implicitly
  `hide_from_segment_leaderboards`.
- Private segments never have a legend.
- A `hide_start_time` activity still counts (only membership in the 90-day
  window is used, never the time). Listed as an open question.
- **Known gap: Endurain has no privacy zones.** A public segment that starts
  near someone's home, combined with a public legend title, hints at where
  they live. A separate *privacy zones* feature (efforts and segment creation
  suppressed within a radius of user-defined points) would close this, and
  would help segments and routes too. Recommended as a follow-up, not a
  blocker, because every input here is already public.

## 8. Notifications

- New notification types in `notifications/constants.py`, in a new numeric
  block after the existing ones (for example `LOCAL_LEGEND_GAINED = 31`,
  `LOCAL_LEGEND_LOST = 32`). The payload holds the segment id, name and
  count. They are delivered through the existing notifications table and
  websocket push.
- Gains are notified immediately. A loss is notified at most once per
  segment per 7 days, to avoid flapping between two close rivals.
- No notifications from backfills or settings-driven recomputes.
- Frontend: map the new types in the notification presenter, add i18n
  strings, and link to the segment page.

## 9. API

Endpoints use `segments:read` (from the segments proposal).

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/segments/{id}/local_legend` | Canonical holder (user, count, since) plus the viewer's own count and the gap to the title. |
| `GET` | `/segments/{id}/local_legend/following` | The per-viewer "among people you follow" ranking (counts only). |
| `GET` | `/segments/{id}/local_legend/me` | The viewer's 13-week personal histogram. |
| `GET` | `/users/{id}/local_legends` | Segments where the user currently holds the title, if they are visible to the viewer. |

`/activities/{id}/segment_efforts` (segments proposal) gains an
`owner_is_local_legend` flag per effort.

## 10. Frontend

- `features/segments/components/LocalLegendCard.vue` on the segment detail
  page: holder avatar and name, count, "since …", the viewer's count and gap,
  and a toggle for the *following* view.
- `PersonalConsistencyPanel.vue`: the viewer's own 13-week chart through
  `useChartProvider`.
- A laurel icon in `ActivitySegmentEfforts.vue` when the effort's owner is the
  current legend.
- Profile page (`/user/:id`): a "Local Legend on N segments" section linking
  to the segments.
- Admin server settings: an enable toggle, window days, minimum athletes, and
  one-per-activity. User privacy settings: the opt-out.
- i18n keys in all 30 locales.

## 11. Implementation plan

| Phase | Scope | Size |
| --- | --- | --- |
| **1. Backend** | Settings columns and Alembic revision; `segments/local_legends` module (query, incumbent tie-break, upsert and diff); hooks in the segment queue drain, visibility edit, privacy toggle and user deletion; daily job in `core/scheduler.py`; notification types; API endpoints and schemas. | S · 3–4 days |
| **2. Frontend** | Legend card, consistency panel, laurel badge, profile section, notification presenter, settings toggles, i18n, regenerated API types. | S · 2–3 days |
| **3. Optional** | History table and "past titles"; leaderboard tab with all current legends on the instance; opt-in "2 more to become Local Legend" nudge notifications. | S · 1–2 days each |

## 12. Testing

- **Window boundaries:** an effort exactly at the window start, one second
  before and one second after; the daily job expiring a title with no new
  efforts.
- **Counting:** three laps in one activity count as 1 (and as 3 with
  `one_per_activity = false`); excluded efforts and hidden duplicates don't
  count.
- **Eligibility matrix:** visibility 0/1/2 × `hide_map` × both opt-outs ×
  Strava setting, for the canonical and the following views.
- **Ties:** incumbent keeps the title; with no incumbent, earliest to reach
  the count wins; the user-id fallback.
- **Thresholds:** below minimum athletes → no title and the row is deleted;
  minimum count of 2.
- **Notifications:** gain is notified; loss is throttled to 7 days; no
  notifications from backfills or settings recomputes.
- **Frontend:** card states (no legend, viewer is legend, viewer is behind),
  the single-user fallback, and the notification presenter mapping.

## 13. Open questions

1. Is a 90-day default (Strava parity) right for small instances, or should
   the default be shorter, such as 30 days?
2. Should every effort count, or at most one per activity (proposed)?
3. Should followers-only activities ever count toward the canonical title?
   Proposed: no.
4. Should `hide_start_time` activities count? Proposed: yes, since no time
   information is exposed.
5. Should privacy zones be required before shipping this, or follow it?
