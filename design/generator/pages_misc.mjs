import { F, T, R, E, I, P, C, shell, card, button, input, select, field, row, col, tabs, badge, sportBadge, avatar, progress, pageHeader, metricPill, lineChart, barChart, sideNav, pagination, switchToggle, divider, SPORT_ICON } from './ui.mjs'

const ghost = (icon) => button('', { variant: 'ghost', icon, size: 'sm' })
const listPanel = (name, { header, rows, footer }) =>
  card(name, { pad: 0, gap: 0 },
    header && F('Header', { dir: 'h', gap: 8, pad: [12, 16], cross: 'center', sw: 'fill', stroke: '$border', sides: [0, 0, 1, 0] }, header),
    rows.map((r, i) => F(`Item ${i + 1}`, { dir: 'v', gap: 4, pad: [12, 16], sw: 'fill', stroke: '$border', sides: [0, 0, i === rows.length - 1 && !footer ? 0 : 1, 0] }, r)),
    footer && F('Footer', { dir: 'h', pad: 12, sw: 'fill', main: 'center' }, footer))

// ---------------- Gear ----------------
const gearIcon = (type) => F('Type icon', { dir: 'h', w: 40, h: 40, radius: 20, fill: '$muted', main: 'center', cross: 'center' }, I(type === 'shoes' ? 'footprints' : type === 'wetsuit' ? 'waves' : 'bike', '$muted-foreground', 22))
const GEARS = [
  ['bicycle', 'Canyon Grizl CF SL', 'Bicycle', ['Strava']], ['bicycle', 'Specialized Allez (winter bike)', 'Bicycle', []],
  ['shoes', 'Saucony Endorphin Speed 4', 'Shoes', ['Garmin Connect']], ['shoes', 'Hoka Clifton 9', 'Shoes', []],
  ['wetsuit', 'Orca Athlex Flow', 'Wetsuit', []], ['shoes', 'Nike Pegasus 39', 'Shoes', ['Inactive']],
]
const gearBadge = (b) => badge(b, b === 'Inactive' ? 'destructive' : b === 'Strava' ? 'warning' : 'info')
export const gears = shell('Gear', [
  pageHeader('Gear', { subtitle: 'Bikes, shoes and equipment you track activities with' }),
  row('Layout', { gap: 12, sw: 'fill', cross: 'min' },
    card('Controls', { w: 288, sw: 'fixed' }, button('Add gear', { sw: 'fill' }), input('Search by nickname', { placeholder: true, icon: 'search' })),
    F('List column', { dir: 'v', sw: 'fill' },
      card('List panel', { pad: 0, gap: 0 },
        F('Header', { dir: 'h', pad: [12, 16], main: 'max', sw: 'fill', stroke: '$border', sides: [0, 0, 1, 0] },
          F('Filters', { dir: 'h', gap: 8, h: 32, pad: [0, 12], radius: 8, cross: 'center', fill: '$background', stroke: '$border' }, T('Filters', 'button'), F('Count', { dir: 'h', w: 18, h: 18, radius: 9, fill: '$primary', main: 'center', cross: 'center' }, T('1', { size: 11, weight: 600, color: '$primary-foreground' })))),
        GEARS.map(([type, name, label, badges], i) => F(`Gear / ${name}`, { dir: 'h', gap: 12, pad: [12, 16], cross: 'center', sw: 'fill', stroke: '$border', sides: [0, 0, i === GEARS.length - 1 ? 0 : 1, 0] },
          row('Main', { gap: 12, sw: 'fill' }, gearIcon(type), col('Text', { gap: 2 }, T(name, { size: 15, weight: 600, color: '$foreground' }), row('Meta', { gap: 8 }, T(label, 'hint'), badges.map(gearBadge)))),
          row('Actions', { gap: 4 }, ghost('pencil'), ghost('trash-2')))),
        F('Footer', { dir: 'h', pad: 12, sw: 'fill', stroke: '$border', sides: [1, 0, 0, 0] }, pagination(1, 1))))),
])

const comp = (title, type, usage, pct, meta, inactive) => [
  row('Top', { sw: 'fill', cross: 'min' }, col('Text', { gap: 4, sw: 'fill' }, T(title, { size: 15, weight: 600, color: '$foreground' }), inactive && badge('Inactive', 'destructive'), T(type, 'hint')), row('Actions', { gap: 4 }, ghost('pencil'), ghost('trash-2'))),
  row('Usage', { sw: 'fill', main: 'between' }, T(usage, 'hint'), T(`${pct}%`, 'hint')),
  progress(pct / 100, { h: 6, track: '$muted', color: pct >= 100 ? C.hr : pct >= 80 ? C.effort : C.goal }),
  T(meta, 'hint'),
]
export const gearDetail = shell('Gear detail', [
  pageHeader('Canyon Grizl CF SL', { subtitle: 'Bicycle' }),
  row('Columns', { gap: 12, sw: 'fill', cross: 'min' },
    card('Info card', { pad: 0, gap: 0, sw: 'fill' },
      F('Head', { dir: 'h', pad: [12, 16], sw: 'fill', stroke: '$border', sides: [0, 0, 1, 0] }, T('Stats', 'cardHeading')),
      F('Body', { dir: 'v', gap: 12, pad: [12, 16], sw: 'fill', stroke: '$border', sides: [0, 0, 1, 0] },
        row('Badges', { gap: 8 }, badge('Strava', 'warning')),
        row('Pills', { gap: 12, sw: 'fill' }, metricPill('Distance', '4,812', 'km', C.brand), metricPill('Time', '212h', null, C.effort), metricPill('Components', '€ 486')),
        ...[['Brand', 'Canyon'], ['Model', 'Grizl CF SL 8 eTap'], ['Created at', 'Mar 14, 2024'], ['Purchase value', '€ 3,299.00'], ['Total cost', '€ 3,785.00']].map(([k, v]) => col(k, { gap: 2 }, T(k, 'hint'), T(v, 'body')))),
      F('Actions', { dir: 'h', gap: 8, pad: [12, 16], sw: 'fill' }, button('Edit gear', { variant: 'outline', icon: 'pencil', sw: 'fill' }), button('Delete gear', { variant: 'destructive', icon: 'trash-2', sw: 'fill' }))),
    listPanel('Components', {
      header: [T('Components', 'cardHeading', { sw: 'fill' }), F('Filters', { dir: 'h', h: 32, pad: [0, 12], radius: 8, cross: 'center', fill: '$background', stroke: '$border' }, T('Filters', 'button'))],
      rows: [comp('Shimano GRX chain', 'Chain', '2,140 km of 3,000 km', 71, 'Purchased Mar 2, 2026'), comp('Continental Terra Speed', 'Tyres', '3,820 km of 4,000 km', 95, 'Purchased Sep 9, 2025'),
        comp('SRAM Force cassette', 'Cassette', '4,812 km of 10,000 km', 48, 'Purchased Mar 14, 2024'), comp('Brake pads (front)', 'Brake pads', '1,010 km of 1,000 km', 100, 'Purchased Jun 1, 2026')],
      footer: button('Add component', { variant: 'outline', size: 'sm', sw: 'fill', icon: 'plus' }),
    }),
    listPanel('Activities', {
      header: [T('Activities', 'cardHeading')],
      rows: [['Sunday gravel loop over the Uetliberg', 'Oct 12, 2026'], ['Commute home', 'Oct 2, 2026'], ['Albis loop', 'Sep 27, 2026'], ['Commute home', 'Sep 25, 2026'], ['Zürichsee round', 'Sep 21, 2026'], ['Commute to work', 'Sep 19, 2026'], ['Gravel intervals', 'Sep 14, 2026']].map(([n, d]) => row('Row', { sw: 'fill', gap: 12 }, T(n, 'body', { sw: 'fill' }), T(d, 'hint'))),
      footer: pagination(1, 3),
    })),
])

// ---------------- Health ----------------
const HEALTH_NAV = [['Dashboard', 'layout-dashboard'], ['Sleep', 'moon'], ['Resting heart rate', 'heart-pulse'], ['Steps', 'footprints'], ['Weight', 'scale'], ['Fasting', 'utensils'], ['Water intake', 'droplet'], ['Bowel movements', 'toilet']]
const healthShell = (name, active, content) => shell(name, row('Layout', { gap: 12, sw: 'fill', cross: 'min' },
  F('Aside', { dir: 'v', gap: 12, w: 256 }, col('Header', { gap: 4, sw: 'fill' }, T('Health', 'pageTitle'), T('See all your health data in one place', 'body', { sw: 'fill' })), sideNav(HEALTH_NAV, active, { w: 256 })),
  F('Content', { dir: 'v', gap: 12, sw: 'fill' }, content)))
const subHeader = (title, subtitle) => col('Header', { gap: 4, sw: 'fill' }, T(title, 'pageTitle'), T(subtitle, 'body'))
const actionsBar = (primary, target = true, icon = 'plus') => row('Actions', { gap: 8, sw: 'fill' },
  primary && button(primary, { icon }), target && button('Set target', { variant: 'outline', icon: 'target' }), F('Spacer', { dir: 'h', sw: 'fill', h: 1 }), select('Last 30 days', { w: 144 }))
const chartCard = (title, color, chart, legend = []) => card(`Chart / ${title}`, {},
  row('Title', { gap: 8 }, F('Swatch', { w: 10, h: 10, radius: 5, fill: color }), T(title, 'cardHeading')), chart,
  legend.length > 0 && row('Legend', { gap: 16 }, legend.map(([l, c]) => row(l, { gap: 6 }, F('Dot', { w: 10, h: 10, radius: 2, fill: c }), T(l, 'hint')))))
const entry = (title, sub, extra) => [row('Top', { sw: 'fill', gap: 8 }, row('Title', { gap: 8, sw: 'fill' }, T(title, 'itemTitle'), extra), row('Actions', { gap: 4 }, ghost('chevron-down'), ghost('pencil'), ghost('trash-2'))), T(sub, 'hint')]
const days = (n, end = 14) => Array.from({ length: n }, (_, i) => { const d = end - n + 1 + i; return d > 0 ? `Oct ${d}` : `Sep ${30 + d}` })
const seq = (n, f) => Array.from({ length: n }, (_, i) => f(i))
const W = 956 // content column inner width

const dashTile = (title, value, sub, footer, icon) => card(`Tile / ${title}`, { gap: 8 },
  T(title, 'caption'), T(value, { size: 22, weight: 600, color: '$foreground' }), sub && T(sub, 'hint'),
  footer && row('Footer', { gap: 4 }, icon && I(icon, '$muted-foreground', 14), T(footer, 'hint')))
export const healthDashboard = healthShell('Health – Dashboard', 0, [
  subHeader('Dashboard', 'Your daily wellbeing at a glance'),
  ...[[['Sleep', '7h 42m', 'Score 84 · Good', '8h target', 'target'], ['Resting HR', '48 bpm', 'HRV 62 ms · Balanced', '7-day avg 49 bpm'], ['Skin temp. dev.', '+0.2 °C', 'vs. baseline', 'Last night']],
    [['Weight', '72.4 kg', 'BMI 22.3 · Normal weight', '70.0 kg', 'target'], ['Steps', '9,812', '81% of goal', '12,000 steps', 'target'], ['Fasting', '14h 20m', 'In progress', '16h', 'target']],
    [['Water intake', '1.8 L', '72% of goal', '2.5 L', 'target'], ['Bowel movements', '1', 'Today', '1 / day', 'target'], ['BMI', '22.3', 'Normal weight', 'Height 180 cm']]].map((r, i) =>
    row(`Row ${i + 1}`, { gap: 12, sw: 'fill', cross: 'min' }, r.map((t) => dashTile(...t)))),
])

const sleepBars = seq(14, (i) => [0.18 + 0.05 * Math.sin(i), 0.45 + 0.06 * Math.cos(i * 1.3), 0.2 + 0.04 * Math.sin(i * 2), 0.04 + 0.03 * Math.abs(Math.sin(i * 3))])
const stacked = (data, colors, { h = 200, labels = [] } = {}) => F('Stacked bars', { dir: 'v', gap: 6, sw: 'fill' },
  F('Plot', { dir: 'h', gap: 10, cross: 'max', sw: 'fill', h, sh: 'fixed', stroke: '$border', sides: [0, 0, 1, 0] },
    data.map((segs, i) => F(`Day ${i + 1}`, { dir: 'v', sw: 'fill', clip: true, radius: [3, 3, 0, 0] }, [...segs].reverse().map((v, j) => R('Seg', { sw: 'fill', h: v * (h - 10), fill: colors[segs.length - 1 - j] }))))),
  labels.length > 0 && F('Labels', { dir: 'h', gap: 10, sw: 'fill' }, labels.map((l) => T(l, 'micro', { sw: 'fill', align: 'center' }))))
export const healthSleep = healthShell('Health – Sleep', 1, [
  subHeader('Sleep', 'Track your sleep duration and quality over time'), actionsBar('Log sleep'),
  chartCard('Sleep stages', '#6366F1', stacked(sleepBars, ['#3730A3', '#818CF8', '#A78BFA', '#FCA5A5'], { labels: days(14) }), [['Deep', '#3730A3'], ['Light', '#818CF8'], ['REM', '#A78BFA'], ['Awake', '#FCA5A5']]),
  listPanel('Entries', { rows: [entry('7h 42m', 'Tue, Oct 14, 2026 · 23:10 – 06:52', T('Score 84', 'caption')), entry('6h 58m', 'Mon, Oct 13, 2026 · 23:45 – 06:43', T('Score 76', 'caption')), entry('8h 05m', 'Sun, Oct 12, 2026 · 22:50 – 06:55', T('Score 89', 'caption')), entry('7h 21m', 'Sat, Oct 11, 2026 · 23:30 – 06:51', T('Score 81', 'caption'))], footer: pagination(1, 4) }),
])
export const healthRhr = healthShell('Health – Resting heart rate', 2, [
  subHeader('Resting heart rate', 'Track your resting heart rate over time'), actionsBar(null, false),
  chartCard('Resting heart rate', C.hr, lineChart(seq(30, (i) => 0.5 + 0.18 * Math.sin(i / 4) + 0.06 * Math.cos(i * 1.7)), { w: W, h: 220, color: C.hr, labels: ['Sep 15', 'Sep 22', 'Sep 29', 'Oct 6', 'Oct 14'] })),
  listPanel('Entries', { rows: [['48 bpm', 'Tue, Oct 14, 2026'], ['49 bpm', 'Mon, Oct 13, 2026'], ['47 bpm', 'Sun, Oct 12, 2026'], ['50 bpm', 'Sat, Oct 11, 2026']].map(([a, b]) => [row('Top', { sw: 'fill' }, T(a, 'itemTitle', { sw: 'fill' }), T('Garmin Connect', 'hint')), T(b, 'hint')]), footer: pagination(1, 8) }),
])
const steps = seq(14, (i) => 0.45 + 0.3 * Math.abs(Math.sin(i * 0.9)) + 0.1 * Math.cos(i))
const withTarget = (chart, frac, h = 200, label = 'Target') => F('Chart with target', { dir: 'v', sw: 'fill' },
  F('Overlay', { sw: 'fill', h: h + 22, sh: 'fixed' }, F('Chart', { dir: 'v', x: 0, y: 0, w: W }, chart),
    P('Target line', `M0 0 L${W} 0`, { x: 0, y: Math.round(h - frac * (h - 4)), w: W, h: 1, stroke: C.goal, strokeW: 1.5 }),
    T(label, { size: 11, weight: 600, color: C.goal }, { x: W - 60, y: Math.round(h - frac * (h - 4)) - 16 })))
export const healthSteps = healthShell('Health – Steps', 3, [
  subHeader('Steps', 'Track your daily step count over time'), actionsBar('Log steps'),
  chartCard('Daily steps', C.brand, withTarget(barChart(steps, { h: 200, labels: days(14), gap: 10 }), 0.82, 200, '12,000'), [['Steps', C.brand], ['Target', C.goal]]),
  listPanel('Entries', { rows: [['9,812 steps', 'Tue, Oct 14, 2026'], ['12,430 steps', 'Mon, Oct 13, 2026'], ['7,205 steps', 'Sun, Oct 12, 2026'], ['14,118 steps', 'Sat, Oct 11, 2026']].map(([a, b]) => entry(a, b)), footer: pagination(1, 6) }),
])
export const healthWeight = healthShell('Health – Weight', 4, [
  subHeader('Weight', 'Track your weight and body composition over time'), actionsBar('Log weight'),
  chartCard('Weight', C.info, withTarget(lineChart(seq(30, (i) => 0.75 - i * 0.012 + 0.04 * Math.sin(i / 2)), { w: W, h: 200, color: C.info, labels: ['Sep 15', 'Sep 22', 'Sep 29', 'Oct 6', 'Oct 14'] }), 0.3, 200, '70.0 kg'), [['Weight', C.info], ['Target', C.goal]]),
  listPanel('Entries', { rows: [
    [...entry('72.4 kg', 'Tue, Oct 14, 2026 · 07:02'), row('Details', { gap: 32, pad: [8, 0, 0, 0] }, [['BMI', '22.3'], ['Body fat', '14.2%'], ['Body water', '61.0%'], ['Bone mass', '3.4 kg'], ['Muscle mass', '35.8 kg']].map(([k, v]) => col(k, { gap: 2 }, T(k, 'caption'), T(v, 'hint'))))],
    entry('72.6 kg', 'Mon, Oct 13, 2026 · 06:58'), entry('72.9 kg', 'Sun, Oct 12, 2026 · 08:15'), entry('73.1 kg', 'Fri, Oct 10, 2026 · 07:05')], footer: pagination(1, 5) }),
])
export const healthFasting = healthShell('Health – Fasting', 5, [
  subHeader('Fasting', 'Start a fast, track your progress, and review your history'),
  card('Active fast', {},
    row('Head', { sw: 'fill', main: 'between' }, T('Fast in progress', 'section'), badge('16:8', 'info')),
    col('Clock', { gap: 4, cross: 'center', sw: 'fill', pad: [8, 0] }, T('14:20:37', { size: 44, weight: 600, color: '$foreground' }), T('Started: Tue, Oct 14, 2026 · 20:00', 'hint')),
    col('Target', { gap: 4, sw: 'fill' }, row('Labels', { sw: 'fill', main: 'between' }, T('Target: 16h', 'hint'), T('90%', 'hint')), progress(0.9, { color: C.brandMid, track: '$muted' })),
    row('Buttons', { gap: 8 }, button('Complete'), button('Break fast', { variant: 'outline' }), button('Cancel', { variant: 'ghost' }))),
  row('Actions', { gap: 8, sw: 'fill' }, button('Set target', { variant: 'outline', icon: 'target' }), F('Spacer', { dir: 'h', sw: 'fill', h: 1 }), select('Last 30 days', { w: 144 })),
  ...[[['Total fasts', '42'], ['Current streak', '6 days'], ['Longest streak', '14 days']], [['Avg. duration', '16h 12m'], ['Total fasting time', '680h'], ['Completion rate', '88%']]].map((r, i) =>
    row(`Stats ${i + 1}`, { gap: 8, sw: 'fill' }, r.map(([l, v]) => card(`Stat / ${l}`, { pad: 12, gap: 4 }, T(l, 'caption'), T(v, 'metric'))))),
  listPanel('Entries', { rows: [['16h 05m', 'Mon, Oct 13 · 20:15 → Tue, Oct 14 · 12:20', badge('Completed', 'goal')], ['14h 40m', 'Sun, Oct 12 · 19:30 → Mon, Oct 13 · 10:10', badge('Broken', 'warning')], ['18h 02m', 'Sat, Oct 11 · 18:00 → Sun, Oct 12 · 12:02', badge('Completed', 'goal')]].map(([a, b, c]) => entry(a, b, c)), footer: pagination(1, 4) }),
])
export const healthWater = healthShell('Health – Water intake', 6, [
  subHeader('Water intake', 'Track your daily water intake over time'), actionsBar('Log water'),
  chartCard('Daily water intake', C.info, withTarget(barChart(seq(14, (i) => 0.5 + 0.25 * Math.abs(Math.cos(i * 0.8))), { h: 200, color: C.info, labels: days(14), gap: 10 }), 0.8, 200, '2.5 L'), [['Water', C.info], ['Target', C.goal]]),
  listPanel('Entries', { rows: [['1.8 L', 'Tue, Oct 14, 2026'], ['2.6 L', 'Mon, Oct 13, 2026'], ['2.1 L', 'Sun, Oct 12, 2026'], ['2.4 L', 'Sat, Oct 11, 2026']].map(([a, b]) => entry(a, b)), footer: pagination(1, 3) }),
])
export const healthPoop = healthShell('Health – Bowel movements', 7, [
  subHeader('Bowel movements', 'Track your bowel movements over time'), actionsBar('Log entry'),
  chartCard('Daily frequency', '#A16207', withTarget(barChart(seq(14, (i) => [0.33, 0.66, 0.33, 0.33, 1, 0.66, 0.33][i % 7]), { h: 160, color: '#A16207', labels: days(14), gap: 10 }), 0.33, 160, '1 / day'), [['Bowel movements', '#A16207'], ['Target', C.goal]]),
  listPanel('Entries', { rows: [['Tue, Oct 14, 2026 · 07:40', 'Bristol 4', 'Normal'], ['Mon, Oct 13, 2026 · 08:05', 'Bristol 3', 'Normal'], ['Mon, Oct 13, 2026 · 19:20', 'Bristol 5', 'Soft']].map(([a, b, c]) => entry(a, c, badge(b, 'secondary'))), footer: pagination(1, 2) }),
])

// ---------------- Search ----------------
const userResult = (initials, name, user, meta) => row(`User / ${name}`, { gap: 12, sw: 'fill' }, avatar(initials, 40), col('Text', { gap: 2, sw: 'fill' }, T(name, { size: 15, weight: 600, color: '$foreground' }), T(user, 'hint')), meta)
export const search = shell('Search', F('Centered', { dir: 'v', gap: 12, w: 672, sw: 'fixed' },
  pageHeader('Search', { subtitle: 'Find users, activities, and gear across Endurain.' }),
  card('Controls', {}, tabs(['Users', 'Activities', 'Gear'], 0, { icons: ['users', 'activity', 'bike'] }), input('ri', { icon: 'search', trailing: 'x' })),
  listPanel('Results', { rows: [
    [userResult('AR', 'Alex Rivera', '@alexr', badge('You', 'secondary'))], [userResult('RM', 'Rita Meier', '@rita.m', button('Follow', { variant: 'outline', size: 'sm' }))],
    [userResult('BR', 'Bruno Ricci', '@bricci', button('Following', { variant: 'secondary', size: 'sm' }))], [userResult('CR', 'Carla Rinaldi', '@carlar', button('Follow', { variant: 'outline', size: 'sm' }))]] }),
), { mainPad: [12, 384, 24, 384] })

// ---------------- Notifications ----------------
const NOTIFS = [
  ['user-plus', 'New follower request', 'Rita Meier (@rita.m) wants to follow you.', '5 minutes ago', true, true],
  ['activity', 'New activity', 'A new activity was added to your account.', '2 hours ago', true, false],
  ['copy', 'Possible duplicate activity', 'An activity with the same start time may already exist.', 'Yesterday', true, false],
  ['user-check', 'Follower request accepted', 'Bruno Ricci (@bricci) accepted your follower request.', '2 days ago', false, false],
  ['triangle-alert', 'Garmin Connect needs attention', 'Your Garmin Connect session expired. Reconnect it to keep syncing.', 'Oct 9, 2026', false, false],
  ['user-round-plus', 'New sign-up needs approval', 'Carla Rinaldi (@carlar) is waiting for account approval.', 'Oct 7, 2026', false, false],
]
export const notifications = shell('Notifications', [
  pageHeader('Notifications', { subtitle: 'Recent activity, requests and alerts', actions: [button('Mark all as read', { variant: 'outline', icon: 'check-check' })] }),
  card('List', { pad: 0, gap: 0 }, NOTIFS.map(([icon, title, body, time, unread, actions], i) => F(`Notification / ${title}`, {
    dir: 'h', gap: 12, pad: [12, 16], sw: 'fill', fill: unread ? '$secondary' : null, stroke: '$border', sides: [0, 0, i === NOTIFS.length - 1 ? 0 : 1, 0],
  }, F('Icon', { dir: 'h', pad: [2, 0, 0, 0] }, I(icon, '$muted-foreground', 20)),
    col('Text', { gap: 2, sw: 'fill' }, row('Title', { gap: 8 }, T(title, { size: 15, weight: 600, color: '$foreground' }), unread && F('Dot', { w: 8, h: 8, radius: 4, fill: C.brand })), T(body, 'body'), T(time, 'hint'),
      actions && row('Buttons', { gap: 8, pad: [6, 0, 0, 0] }, button('Accept', { size: 'sm' }), button('Decline', { variant: 'outline', size: 'sm' }))),
    unread && ghost('check')))),
  row('More', { sw: 'fill', main: 'center' }, button('Load more', { variant: 'ghost' })),
])
