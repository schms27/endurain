import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { ActivityStream } from '@/features/activities/types'
import type { SegmentEffort, SegmentEffortDto } from '@/features/segments/types'

import { apiFetch } from '@/services/http'
import {
  createSegment,
  fetchLeaderboard,
  fetchSimilarSegments,
  mapLeaderboard,
  mapSegmentEffort,
  setEffortExcluded,
} from '@/features/segments/services/segments'
import {
  buildEffortHistoryChart,
  cumulativeDistances,
  extractIndexedTrack,
  formatEffortSpeed,
  formatTimeDelta,
  medalFor,
  sliceProblem,
  sliceTrack,
  sportGroupOf,
} from '@/features/segments/utils/segments'
import { overlayStyleOf, OVERLAY_STYLES } from '@/providers/leafletMapProvider'

vi.mock('@/services/http', () => ({
  apiFetch: vi.fn<typeof apiFetch>(),
}))

const effortDto: SegmentEffortDto = {
  id: 3,
  segment_id: 7,
  segment_name: 'River path',
  activity_id: 11,
  user_id: 1,
  start_time: '2024-05-01T08:00:00Z',
  elapsed_time: 212.4,
  distance: 1000,
  start_index: 40,
  end_index: 240,
  average_hr: 150,
  max_hr: 170,
  average_power: null,
  normalized_power: null,
  average_cad: null,
  average_speed: 4.7,
  is_excluded: false,
  current_rank: 2,
  historical_rank: 1,
  pr_elapsed_time: 200,
}

function effort(overrides: Partial<SegmentEffort> = {}): SegmentEffort {
  return { ...mapSegmentEffort(effortDto), ...overrides }
}

beforeEach(() => {
  vi.mocked(apiFetch).mockReset()
})

describe('segment services', () => {
  it('maps an effort payload to the clean model', () => {
    expect(mapSegmentEffort(effortDto)).toMatchObject({
      segmentName: 'River path',
      startIndex: 40,
      endIndex: 240,
      averageCadence: null,
      currentRank: 2,
      historicalRank: 1,
      prElapsedTime: 200,
    })
  })

  it('maps missing ranks to null', () => {
    const { current_rank, historical_rank, pr_elapsed_time, ...rest } = effortDto
    void current_rank
    void historical_rank
    void pr_elapsed_time
    expect(mapSegmentEffort(rest)).toMatchObject({
      currentRank: null,
      historicalRank: null,
      prElapsedTime: null,
    })
  })

  it('maps a leaderboard page with the viewer entry', () => {
    const entry = {
      rank: 1,
      user_id: 2,
      user_name: 'Ana',
      username: 'ana',
      user_photo_path: null,
      effort_id: 5,
      activity_id: 9,
      start_time: null,
      elapsed_time: 180,
      average_hr: null,
      average_power: null,
      average_speed: 5.5,
    }
    const board = mapLeaderboard({ entries: [entry], total: 1, viewer_entry: null })
    expect(board.entries[0]).toMatchObject({ userId: 2, userName: 'Ana', startTime: null })
    expect(board.viewerEntry).toBeNull()
    expect(
      mapLeaderboard({ entries: [], total: 0, viewer_entry: entry }).viewerEntry?.effortId,
    ).toBe(5)
  })

  it('requests the leaderboard with scope, period and pagination', async () => {
    vi.mocked(apiFetch).mockResolvedValue({ entries: [], total: 0, viewer_entry: null })
    await fetchLeaderboard(7, { scope: 'following', period: 'this_year', page: 2, numRecords: 25 })
    const [path] = vi.mocked(apiFetch).mock.calls[0] ?? []
    expect(path).toBe(
      '/segments/7/leaderboard?scope=following&period=this_year&page_number=2&num_records=25',
    )
  })

  it('checks a slice for duplicates', async () => {
    vi.mocked(apiFetch).mockResolvedValue([])
    await fetchSimilarSegments({ activityId: 11, startIndex: 40, endIndex: 240 })
    const [path] = vi.mocked(apiFetch).mock.calls[0] ?? []
    expect(path).toBe('/segments/similar?activity_id=11&start_index=40&end_index=240')
  })

  it('creates a segment with the snake-cased slice', async () => {
    vi.mocked(apiFetch).mockResolvedValue({
      id: 7,
      user_id: 1,
      name: 'River path',
      sport_group: 'run',
      visibility: 2,
      distance: 1000,
      elevation_gain: null,
      average_grade: null,
      start_lat: 1,
      start_lon: 2,
      city: null,
      town: null,
      country: null,
      is_archived: false,
      effort_count: 0,
      athlete_count: 0,
      created_at: '2024-01-01T00:00:00Z',
      description: null,
      geometry: [
        [1, 2, null],
        [1.1, 2.1, 12],
      ],
      elevation_loss: null,
      maximum_grade: null,
      end_lat: 1.1,
      end_lon: 2.1,
      source_activity_id: 11,
      updated_at: '2024-01-01T00:00:00Z',
    })
    const segment = await createSegment({
      activityId: 11,
      startIndex: 40,
      endIndex: 240,
      name: 'River path',
      description: null,
      visibility: 2,
    })
    const [, init] = vi.mocked(apiFetch).mock.calls[0] ?? []
    expect(JSON.parse(init?.body as string)).toEqual({
      activity_id: 11,
      start_index: 40,
      end_index: 240,
      name: 'River path',
      description: null,
      visibility: 2,
    })
    expect(segment.points).toEqual([
      { lat: 1, lng: 2, ele: null },
      { lat: 1.1, lng: 2.1, ele: 12 },
    ])
  })

  it('patches the exclusion flag', async () => {
    vi.mocked(apiFetch).mockResolvedValue({ ...effortDto, is_excluded: true })
    const updated = await setEffortExcluded(3, true)
    const [path, init] = vi.mocked(apiFetch).mock.calls[0] ?? []
    expect(path).toBe('/segment_efforts/3')
    expect(init?.method).toBe('PATCH')
    expect(updated.isExcluded).toBe(true)
  })
})

describe('segment utils', () => {
  it('maps activity types to sport groups, excluding virtual and indoor', () => {
    expect(sportGroupOf(1)).toBe('run')
    expect(sportGroupOf(4)).toBe('ride')
    expect(sportGroupOf(35)).toBe('e_ride')
    expect(sportGroupOf(12)).toBe('foot')
    expect(sportGroupOf(3)).toBeNull()
    expect(sportGroupOf(28)).toBeNull()
  })

  it('keeps stream indices when GPS points are missing', () => {
    const streams: ActivityStream[] = [
      { id: 1, streamType: 1, waypoints: [{ hr: 120 }], hrZones: null },
      {
        id: 2,
        streamType: 7,
        waypoints: [
          { lat: 1, lon: 2 },
          { lat: null, lon: null },
          { lat: 1.001, lon: 2 },
        ],
        hrZones: null,
      },
    ]
    const track = extractIndexedTrack(streams)
    expect(track.map((point) => point.index)).toEqual([0, 2])
    expect(sliceTrack(track, 1, 2)).toEqual([{ lat: 1.001, lng: 2 }])
  })

  it('accumulates distance along a track', () => {
    const distances = cumulativeDistances([
      { lat: 0, lng: 0 },
      { lat: 0.001, lng: 0 },
      { lat: 0.002, lng: 0 },
    ])
    expect(distances[0]).toBe(0)
    expect(distances[2]).toBeCloseTo(222.4, 0)
  })

  it('mirrors the backend slice checks', () => {
    expect(sliceProblem(5, 1000, 'run')).toBe('tooFewPoints')
    expect(sliceProblem(50, 150, 'run')).toBe('tooShort')
    expect(sliceProblem(50, 300, 'ride')).toBe('tooShort')
    expect(sliceProblem(50, 300, 'run')).toBeNull()
    expect(sliceProblem(50, 150_000, 'ride')).toBe('tooLong')
  })

  it('formats signed time deltas', () => {
    expect(formatTimeDelta(212.4, 200)).toBe('+00:12')
    expect(formatTimeDelta(190, 200)).toBe('-00:10')
  })

  it('awards medals to the top three only', () => {
    expect([1, 2, 3, 4, null].map(medalFor)).toEqual(['gold', 'silver', 'bronze', null, null])
  })

  it('shows pace for runs and speed for rides', () => {
    expect(formatEffortSpeed(5, 'run', 'metric')).toBe('3:20 min/km')
    expect(formatEffortSpeed(10, 'ride', 'metric')).toBe('36.00 km/h')
    expect(formatEffortSpeed(null, 'ride', 'metric')).toBe('--')
  })

  it('charts effort history oldest first, ignoring excluded efforts', () => {
    const chart = buildEffortHistoryChart(
      [
        effort({ id: 1, startTime: '2024-03-01T00:00:00Z', elapsedTime: 230 }),
        effort({ id: 2, startTime: '2024-01-01T00:00:00Z', elapsedTime: 250 }),
        effort({ id: 3, startTime: '2024-02-01T00:00:00Z', elapsedTime: 100, isExcluded: true }),
      ],
      'Elapsed time',
      (iso) => iso.slice(0, 7),
    )
    expect(chart?.labels).toEqual(['2024-01', '2024-03'])
    expect(chart?.series[0]?.data).toEqual([250, 230])
    expect(chart?.invertY).toBe(true)
    expect(buildEffortHistoryChart([effort()], 'x', (iso) => iso)).toBeNull()
  })
})

describe('map overlays', () => {
  it('defaults overlays to the highlight style', () => {
    expect(overlayStyleOf({ id: 'a', points: [] })).toBe(OVERLAY_STYLES.highlight)
    expect(overlayStyleOf({ id: 'b', points: [], style: 'muted' })).toBe(OVERLAY_STYLES.muted)
  })
})
