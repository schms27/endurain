import { F, T, R, I, C, shell, card, button, input, select, field, row, col, tabs, badge, sportBadge, avatar, progress, pageHeader, metricsGrid, mapThumb, lineChart, barChart, table, pagination, SPORT_ICON } from './ui.mjs'

// ---- shared bits ----
export function streakCard() {
  const weeks = ['met', 'met', 'part', 'none', 'met', 'part', 'met', 'met', 'met', 'met', 'met', 'cur']
  const color = { met: C.goal, part: C.brand + '66', none: '$muted-foreground-15', cur: C.brand + '66' }
  return card('Weekly streak card', {},
    T('Weekly streak', 'cardHeading'),
    row('Streak', { gap: 24, sw: 'fill' },
      row('Current streak', { gap: 12 },
        F('Flame', { dir: 'h', w: 48, h: 48, radius: 24, fill: C.brand + '26', main: 'center', cross: 'center' }, I('flame', C.brand, 24)),
        col('Text', { gap: 2 }, T('6 weeks', 'metric'), T('Current streak', 'caption'))),
      col('This week', { gap: 6, sw: 'fill' }, progress(0.66, { w: 600 }), T('2 of 3 this week', 'hint'))),
    col('History', { gap: 6, sw: 'fill' },
      row('Recent weeks', { gap: 4, sw: 'fill' }, weeks.map((w, i) => R(`Week ${i + 1}`, { h: 12, sw: 'fill', radius: 2, fill: color[w], stroke: w === 'cur' ? '$foreground-40' : null, strokeAlign: 'outside' }))),
      row('Labels', { main: 'between', sw: 'fill' }, T('11 weeks ago', 'micro'), T('This week', 'micro'))),
    F('Longest', { dir: 'v', pad: [12, 0, 0, 0], sw: 'fill', stroke: '$border', sides: [1, 0, 0, 0] }, T('Longest streak: 9 weeks (Mar 2 – May 3)', 'hint')),
  )
}

const ACTS = [
  ['running', 'Morning tempo run along the lake', 'Tue, Oct 14, 2026 · 07:12 · Zürich, Switzerland', ['12.4', 'km'], ['58:21'], ['4:42', '/km'], ['84', 'm']],
  ['cycling', 'Sunday gravel loop over the Uetliberg', 'Sun, Oct 12, 2026 · 09:30 · Uetliberg, Switzerland', ['64.2', 'km'], ['2:41:08'], ['23.9', 'km/h'], ['812', 'm']],
  ['running', 'Easy recovery jog', 'Fri, Oct 10, 2026 · 18:05 · Zürich, Switzerland', ['6.1', 'km'], ['35:40'], ['5:51', '/km'], ['22', 'm']],
  ['swimming', 'Lunch swim — 50 m pool', 'Thu, Oct 9, 2026 · 12:15 · Hallenbad City', ['2.0', 'km'], ['41:12'], ['2:03', '/100m'], null],
  ['hiking', 'Rigi summit hike', 'Sat, Oct 4, 2026 · 08:40 · Rigi Kulm, Switzerland', ['14.8', 'km'], ['4:52:10'], ['3.0', 'km/h'], ['1,104', 'm']],
  ['cycling', 'Commute home', 'Thu, Oct 2, 2026 · 17:30 · Zürich, Switzerland', ['11.3', 'km'], ['32:05'], ['21.1', 'km/h'], ['64', 'm']],
  ['running', 'Long run — Sihl valley', 'Sun, Sep 28, 2026 · 08:00 · Adliswil, Switzerland', ['24.0', 'km'], ['2:01:44'], ['5:04', '/km'], ['210', 'm']],
  ['other', 'Strength — upper body', 'Wed, Sep 24, 2026 · 19:00 · Home gym', null, ['45:00'], null, null],
]
const COLS = [['Distance', 96], ['Duration', 80], ['Pace / Speed', 128], ['Elevation', 72]]
function activityRow(a, last) {
  const [kind, name, meta, ...cells] = a
  return F(`Row / ${name}`, { dir: 'h', gap: 12, pad: [12, 16], cross: 'center', sw: 'fill', stroke: '$border', sides: [0, 0, last ? 0 : 1, 0] },
    row('Activity', { gap: 12, sw: 'fill' },
      F('Type icon', { dir: 'h', w: 40, h: 40, radius: 20, fill: '$muted', main: 'center', cross: 'center' }, I(SPORT_ICON[kind], '$muted-foreground', 20)),
      col('Text', { gap: 2, sw: 'fill' }, T(name, { size: 15, weight: 600, color: '$foreground' }), T(meta, 'hint'))),
    row('Cells', { gap: 24, cross: 'baseline' }, cells.map((c, i) => F(`Cell ${COLS[i][0]}`, { dir: 'h', gap: 3, w: COLS[i][1], main: 'max', cross: 'baseline' },
      c ? [T(c[0], { size: 22, weight: 600, color: '$foreground' }), c[1] && T(c[1], 'hint')] : T('—', { size: 22, weight: 600, color: '$muted-foreground' })))),
  )
}
export function activityListPanel(rows = ACTS, { count = '128 activities', pages = 16 } = {}) {
  return card('List panel', { pad: 0, gap: 0 },
    F('Header', { dir: 'h', pad: [12, 16], cross: 'center', sw: 'fill', stroke: '$border', sides: [0, 0, 1, 0] },
      T(count, 'hint', { sw: 'fill' }), row('Sort', { gap: 8 }, select('Date', { w: 140 }), button('', { variant: 'outline', icon: 'arrow-down-wide-narrow' }))),
    F('Columns', { dir: 'h', gap: 12, pad: [8, 16], sw: 'fill', stroke: '$border', sides: [0, 0, 1, 0] },
      F('Activity', { dir: 'h', pad: [0, 0, 0, 52], sw: 'fill' }, T('Activity', 'caption')),
      row('Heads', { gap: 24 }, COLS.map(([l, w]) => F(`Head ${l}`, { dir: 'h', w, main: 'max' }, T(l, 'caption'))))),
    rows.map((a, i) => activityRow(a, i === rows.length - 1)),
    F('Footer', { dir: 'h', pad: [12, 16], sw: 'fill', stroke: '$border', sides: [1, 0, 0, 0] }, pagination(1, 5)),
  )
}

// ---- /activities ----
export const activities = shell('Activities', [
  pageHeader('Activities', { subtitle: 'Browse, filter, and sort all your activities.' }),
  row('Layout', { gap: 12, sw: 'fill', cross: 'min' },
    card('Filters', { w: 288, sw: 'fixed' },
      input('Search by name or location', { placeholder: true, icon: 'search' }),
      field('Activity type', select('All types')),
      row('Dates', { gap: 8, sw: 'fill', cross: 'min' }, field('From', input('mm/dd/yyyy', { placeholder: true, trailing: 'calendar' })), field('To', input('mm/dd/yyyy', { placeholder: true, trailing: 'calendar' }))),
      button('Clear filters', { variant: 'outline', size: 'sm', sw: 'fill' })),
    F('List column', { dir: 'v', sw: 'fill' }, activityListPanel())),
])

// ---- /activity/:id ----
const hrZones = [[1, '< 120 bpm', 0.08, '#9CA3AF'], [2, '120–140 bpm', 0.22, C.info], [3, '140–155 bpm', 0.41, C.goal], [4, '155–170 bpm', 0.24, C.effort], [5, '> 170 bpm', 0.05, C.hr]]
const chartCard = (title, color, values, stats) => card(`Chart / ${title}`, { sw: 'fill' },
  row('Title', { gap: 8 }, F('Swatch', { w: 10, h: 10, radius: 5, fill: color }), T(title, 'cardHeading')),
  lineChart(values, { w: 590, h: 224, color, fillArea: false }),
  row('Stats', { gap: 24 }, stats.map(([l, v, u]) => col(l, { gap: 2 }, T(l, 'caption'), F('Value', { dir: 'h', gap: 4, cross: 'baseline' }, T(v, 'itemTitle'), u && T(u, 'hint'))))))
const wave = (n, f, base, amp, noise = 0.025, seed = 1) => Array.from({ length: n }, (_, i) => Math.max(0.02, Math.min(0.98, base + amp * Math.sin(i / f + seed) + noise * Math.sin(i * 0.9 + seed * 3))))

export const activityDetail = shell('Activity detail', [
  button('Back', { variant: 'ghost', size: 'sm', icon: 'arrow-left' }),
  card('Header card', {},
    row('Athlete header', { gap: 12, sw: 'fill', cross: 'min' },
      row('Athlete', { gap: 12, sw: 'fill' }, avatar('AR', 56),
        col('Meta', { gap: 4 }, T('Alex Rivera', 'itemTitle'),
          row('Badges', { gap: 8 }, sportBadge('running', 'Running'), badge('Public', 'secondary', { icon: 'globe' })),
          T('Tue, Oct 14, 2026 · 07:12 · Zürich, Switzerland', 'caption'))),
      row('Owner actions', { gap: 4 }, button('', { variant: 'ghost', icon: 'pencil', size: 'sm' }), button('', { variant: 'ghost', icon: 'ellipsis-vertical', size: 'sm' }))),
    T('Morning tempo run along the lake', 'cardHeading'),
    T('Felt strong today — negative split on the way back with a light tailwind. Legs are finally coming around after last week\'s long run.', 'body', { sw: 'fill', style: { lh: 150 } }),
    F('Metrics', { dir: 'v', pad: [16, 0, 0, 0], sw: 'fill', stroke: '$border', sides: [1, 0, 0, 0] },
      metricsGrid([['Distance', '12.4', 'km'], ['Moving time', '58:21'], ['Avg pace', '4:42', '/km', C.info], ['Avg heart rate', '156', 'bpm', C.hr], ['Elevation gain', '84', 'm'], ['Calories', '812', 'kcal', C.effort],
        ['Elapsed time', '1:01:05'], ['Max heart rate', '178', 'bpm', C.hr], ['Avg cadence', '172', 'spm'], ['Elevation loss', '81', 'm'], ['Max speed', '18.2', 'km/h'], ['Avg power', '268', 'W']], 6))),
  mapThumb({ w: 1256, h: 600, name: 'Map' }),
  card('Gear card', {},
    row('Header', { sw: 'fill', main: 'between' }, T('Gear', 'cardHeading'), row('Actions', { gap: 4 }, button('', { variant: 'ghost', icon: 'pencil', size: 'sm' }), button('', { variant: 'ghost', icon: 'trash-2', size: 'sm' }))),
    T('Saucony Endorphin Speed 4', { size: 14, color: C.brand })),
  row('Charts row 1', { gap: 12, sw: 'fill', cross: 'min' },
    chartCard('Heart rate', C.hr, wave(40, 5, 0.6, 0.15), [['Avg', '156', 'bpm'], ['Max', '178', 'bpm']]),
    chartCard('Pace', C.info, wave(40, 4, 0.55, 0.12, 0.04, 2), [['Avg', '4:42', '/km'], ['Best', '4:05', '/km']])),
  row('Charts row 2', { gap: 12, sw: 'fill', cross: 'min' },
    chartCard('Elevation', C.goal, wave(40, 7, 0.45, 0.25, 0.02, 4), [['Gain', '84', 'm'], ['Loss', '81', 'm']]),
    card('HR zones', { sw: 'fill' }, T('Heart rate zones', 'cardHeading'),
      col('Zones', { gap: 10, sw: 'fill', pad: [16, 0] }, hrZones.map(([z, range, pct, color]) => row(`Zone ${z}`, { gap: 12, sw: 'fill' },
        col('Label', { gap: 0, w: 96 }, T(`Zone ${z}`, { size: 13, weight: 600, color: '$foreground' }), T(range, 'caption')),
        F('Bar', { w: 380, h: 10, radius: 5, fill: '$muted', clip: true, sw: 'fill', sh: 'fixed' }, R('Fill', { w: 380 * pct * 2, h: 10, radius: 5, fill: color })),
        F('Pct', { dir: 'h', w: 64, main: 'max' }, T(`${Math.round(pct * 100)}%`, { size: 13, weight: 600, color: '$foreground' }))))))),
  card('Laps', {}, T('Laps', 'cardHeading'),
    table([60, 'fill', 'fill', 'fill', 'fill', 'fill'], ['Lap', 'Distance', 'Time', 'Pace / Speed', 'Elevation', 'Heart rate'],
      [['1', '2.00 km', '9:58', '4:59 /km', '+12 m', '142 bpm'], ['2', '2.00 km', '9:32', '4:46 /km', '+18 m', '151 bpm'], ['3', '2.00 km', '9:21', '4:40 /km', '+9 m', '157 bpm'],
        ['4', '2.00 km', '9:15', '4:37 /km', '+20 m', '160 bpm'], ['5', '2.00 km', '9:08', '4:34 /km', '+15 m', '163 bpm'], ['6', '2.40 km', '11:07', '4:38 /km', '+10 m', '165 bpm']], { rowH: 40 })),
])

// ---- /summary ----
export const summary = shell('Summary', [
  pageHeader('Summary', { subtitle: 'Review your training totals and trends over time.' }),
  streakCard(),
  card('Controls', {},
    tabs(['Week', 'Month', 'Year', 'Lifetime'], 1, { sw: 'hug' }),
    row('Filters', { sw: 'fill', main: 'between', cross: 'max' },
      F('Type', { dir: 'v', w: 224 }, field('Activity type', select('All types'))),
      row('Period nav', { gap: 8 }, button('', { variant: 'outline', icon: 'chevron-left' }), input('October 2026', { w: 176, trailing: 'calendar' }), button('', { variant: 'outline', icon: 'chevron-right' }))),
    T('October 1 – October 31, 2026', 'hint')),
  row('Totals', { gap: 12, sw: 'fill' }, [['Distance', '312.6', 'km'], ['Duration', '21:48', 'h'], ['Elevation', '4,210', 'm'], ['Calories', '18,940', 'kcal'], ['Activities', '23', '']].map(([l, v, u]) =>
    card(`Total / ${l}`, { gap: 4 }, T(l, 'caption'), F('Value', { dir: 'h', gap: 4, cross: 'baseline' }, T(v, { size: 26, weight: 600, color: '$foreground' }), u && T(u, 'hint'))))),
  card('Breakdown', {}, T('Breakdown', 'cardHeading'),
    barChart([0.55, 0.8, 0.62, 0.95, 0.35], { h: 120, labels: ['Week 40', 'Week 41', 'Week 42', 'Week 43', 'Week 44'], highlight: 3, gap: 48 }),
    table(['fill', 'fill', 'fill', 'fill', 'fill', 'fill'], ['Period', 'Distance', 'Duration', 'Elevation', 'Calories', 'Activities'],
      [['Week 40', '58.2 km', '4:12:30', '720 m', '3,410 kcal', '5'], ['Week 41', '84.7 km', '5:40:12', '1,180 m', '4,980 kcal', '6'], ['Week 42', '66.0 km', '4:31:05', '860 m', '3,920 kcal', '5'],
        ['Week 43', '98.3 km', '6:02:44', '1,310 m', '5,620 kcal', '6'], ['Week 44', '5.4 km', '0:43:20', '140 m', '1,010 kcal', '1']], { rowH: 40 })),
  card('By type', {}, T('By activity type', 'cardHeading'),
    table([220, 'fill', 'fill', 'fill', 'fill', 'fill'], ['Type', 'Distance', 'Duration', 'Elevation', 'Calories', 'Activities'],
      [[sportBadge('running', 'Running'), '96.2 km', '8:02:11', '640 m', '6,830 kcal', '11'], [sportBadge('cycling', 'Cycling'), '198.4 km', '9:12:40', '2,466 m', '8,420 kcal', '7'],
        [sportBadge('hiking', 'Hiking'), '14.8 km', '4:52:10', '1,104 m', '2,280 kcal', '1'], [sportBadge('swimming', 'Swimming'), '3.2 km', '1:05:30', '—', '1,410 kcal', '2']], { rowH: 44 })),
  col('Activities in period', { gap: 12, sw: 'fill' }, T('Activities in this period', 'itemTitle'), activityListPanel(ACTS.slice(0, 5), { count: '23 activities' })),
])
