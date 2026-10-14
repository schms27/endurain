// Endurain UI primitives expressed with the fc.mjs builder.
import { F, T, R, E, I, P, INST, IMG, C } from './fc.mjs'

export const PAGE_W = 1440
export const GUTTER = 92 // (1440 - max-w-7xl 1280) / 2 + px-3

/** Authenticated app shell: navbar, main content column, footer. */
export function shell(name, content, { mainPad = [12, GUTTER, 24, GUTTER], minH = 900 } = {}) {
  return F(name, { w: PAGE_W, dir: 'v', fill: '$background', sh: 'hug' },
    INST('Navbar', { sw: 'fill' }),
    F('Main', { dir: 'v', gap: 12, pad: mainPad, sw: 'fill', minH }, content),
    INST('Footer', { sw: 'fill' }),
  )
}
/** Bare shell (auth screens): centred content, no chrome. */
export function bare(name, content, { h = 900, pad = [48, GUTTER] } = {}) {
  return F(name, { w: PAGE_W, h, dir: 'v', fill: '$background', pad, main: 'center', cross: 'center' }, content)
}

export const card = (name, o = {}, ...kids) =>
  F(name, { dir: 'v', gap: 12, pad: 16, fill: '$card', stroke: '$border', radius: 12, sw: 'fill', ...o }, ...kids)

export const row = (name, o = {}, ...kids) => F(name, { dir: 'h', gap: 8, cross: 'center', ...o }, ...kids)
export const col = (name, o = {}, ...kids) => F(name, { dir: 'v', gap: 8, ...o }, ...kids)
export const spacer = () => F('Spacer', { dir: 'h', sw: 'fill', h: 1, sh: 'fixed' })

const BTN = {
  primary: { fill: '$primary', text: '$primary-foreground' },
  outline: { fill: '$background', stroke: '$border', text: '$foreground' },
  secondary: { fill: '$secondary', text: '$secondary-foreground' },
  ghost: { fill: null, text: '$foreground' },
  destructive: { fill: C.destructive, text: C.white },
  link: { fill: null, text: '$primary' },
}
export function button(label, { variant = 'primary', icon, iconRight, sw, size = 'md', name } = {}) {
  const v = BTN[variant]
  const h = size === 'sm' ? 32 : 36
  return F(name ?? `Button / ${label || icon}`, {
    dir: 'h', gap: 8, h, sh: 'fixed', pad: label ? [0, size === 'sm' ? 12 : 16] : [0, 0], w: label ? undefined : h, sw: sw ?? (label ? 'hug' : 'fixed'),
    main: 'center', cross: 'center', radius: 8, fill: v.fill, stroke: v.stroke,
  }, icon && I(icon, v.text, 16), label && T(label, { ...STY.button, color: v.text }), iconRight && I(iconRight, v.text, 16))
}
const STY = { button: { size: 14, weight: 600 } }

export function input(text, { placeholder = false, icon, trailing, sw = 'fill', w, name, h = 36 } = {}) {
  return F(name ?? `Input / ${text}`, { dir: 'h', gap: 8, h, sh: 'fixed', pad: [0, 12], cross: 'center', radius: 8, stroke: '$input', fill: '$card', sw: w ? 'fixed' : sw, w },
    icon && I(icon, '$muted-foreground', 16),
    T(text, placeholder ? 'body' : 'bodyFg'),
    spacer(),
    trailing && I(trailing, '$muted-foreground', 16),
  )
}
export const select = (value, o = {}) => input(value, { trailing: 'chevron-down', ...o, name: `Select / ${value}` })
export const textarea = (text, { h = 88, placeholder = true } = {}) =>
  F(`Textarea`, { dir: 'v', pad: [8, 12], radius: 8, stroke: '$input', fill: '$card', sw: 'fill', h, sh: 'fixed' }, T(text, placeholder ? 'body' : 'bodyFg', { sw: 'fill' }))

export function field(label, control, { hint, error, sw = 'fill' } = {}) {
  return F(`Field / ${label}`, { dir: 'v', gap: 6, sw }, T(label, 'label'), control, hint && T(hint, 'hint', { sw: 'fill' }), error && T(error, { size: 12, color: C.destructive }))
}
export const passwordInput = (o = {}) => input('••••••••••', { trailing: 'eye', ...o, name: 'PasswordInput' })

export function tabs(items, active = 0, { sw = 'fill', icons = [], name = 'Tabs' } = {}) {
  return F(name, { dir: 'h', gap: 4, pad: 4, radius: 8, fill: '$background', stroke: '$border', sw },
    items.map((label, i) => F(`Tab / ${label}${i === active ? ' (active)' : ''}`, {
      dir: 'h', gap: 6, pad: [6, 12], radius: 8, main: 'center', cross: 'center', sw: sw === 'fill' ? 'fill' : 'hug',
      fill: i === active ? '$card' : null, shadow: i === active,
    }, icons[i] && I(icons[i], i === active ? '$foreground' : '$muted-foreground', 16), T(label, { size: 15, weight: 600, color: i === active ? '$foreground' : '$muted-foreground' }))),
  )
}

const BADGE = {
  secondary: ['$secondary', '$secondary-foreground'], outline: [null, '$foreground', '$input'],
  primary: ['$primary', '$primary-foreground'], destructive: [C.destructive + '1A', C.destructive, C.destructive + '33'],
  warning: [C.effort + '1A', C.effort, C.effort + '66'], info: [C.info + '1A', C.info, C.info + '66'],
  running: ['#FBE9E8', '#B42318'], cycling: ['#E9F4DC', '#466E15'], swimming: ['#E6F1FB', '#185FA5'],
  hiking: ['#FAEEDA', '#854F0B'], other: ['#F1EFE8', '#5F5E5A'], goal: [C.goal + '1A', C.goal, C.goal + '66'],
}
export const SPORT_ICON = { running: 'footprints', cycling: 'bike', swimming: 'waves', hiking: 'mountain-snow', other: 'activity' }
export function badge(text, kind = 'secondary', { icon, pill } = {}) {
  const [bg, fg, border] = BADGE[kind]
  return F(`Badge / ${text}`, { dir: 'h', gap: 4, pad: [2, 8], cross: 'center', radius: pill ? 20 : 4, fill: bg, stroke: border },
    icon && I(icon, fg, 14), T(text, { size: 12, weight: 600, color: fg }))
}
export const sportBadge = (kind, label) => badge(label, kind, { icon: SPORT_ICON[kind] })

export function avatar(initials = 'AR', size = 32) {
  return F(`Avatar ${initials}`, { dir: 'h', w: size, h: size, radius: size / 2, fill: '$secondary', main: 'center', cross: 'center' },
    T(initials, { size: Math.round(size * 0.36), weight: 600, color: '$secondary-foreground' }))
}

export function progress(pct, { color = C.brand, track = '$muted-foreground-15', w = 273, h = 8 } = {}) {
  return F('Progress', { w, h, radius: h / 2, fill: track, clip: true, sw: 'fill', sh: 'fixed' },
    R('Fill', { w: Math.max(0, Math.min(1, pct)) * w, h, radius: h / 2, fill: color }))
}

export function switchToggle(on = true) {
  return F(`Switch ${on ? 'on' : 'off'}`, { w: 44, h: 24, radius: 12, fill: on ? C.brand : '$muted-foreground-15' },
    E('Thumb', { x: on ? 22 : 2, y: 2, w: 20, h: 20, fill: C.white }))
}
export function checkbox(on = false) {
  return F('Checkbox', { dir: 'h', w: 16, h: 16, radius: 4, fill: on ? '$primary' : null, stroke: on ? null : '$input', main: 'center', cross: 'center' },
    on && I('check', '$primary-foreground', 12))
}

/** Page header: title + optional subtitle and right-aligned actions. */
export function pageHeader(title, { subtitle, actions = [], name = 'Page header' } = {}) {
  return F(name, { dir: 'h', gap: 12, cross: 'center', sw: 'fill' },
    F('Titles', { dir: 'v', gap: 4, sw: 'fill' }, T(title, 'pageTitle'), subtitle && T(subtitle, 'body', { sw: 'fill' })),
    actions.length > 0 && F('Actions', { dir: 'h', gap: 8, cross: 'center' }, actions),
  )
}
export const cardHeader = (title, { subtitle, actions = [] } = {}) =>
  F('Header', { dir: 'h', gap: 12, cross: 'center', sw: 'fill' },
    F('Titles', { dir: 'v', gap: 2, sw: 'fill' }, T(title, 'section'), subtitle && T(subtitle, 'hint', { sw: 'fill' })),
    actions.length > 0 && F('Actions', { dir: 'h', gap: 8, cross: 'center' }, actions))

export function metricPill(label, value, unit, color) {
  return F(`Metric / ${label}`, { dir: 'v', gap: 4, sw: 'fill' }, T(label, 'caption'),
    F('Value', { dir: 'h', gap: 4, cross: 'baseline' }, T(value, { size: 22, weight: 600, color: color ?? '$foreground' }), unit && T(unit, 'hint')))
}
export const metricsGrid = (items, cols = 3) => {
  const rows = []
  for (let i = 0; i < items.length; i += cols) rows.push(F('Row', { dir: 'h', gap: 12, sw: 'fill' }, items.slice(i, i + cols).map((m) => metricPill(...m)), ...Array(cols - Math.min(cols, items.length - i)).fill(0).map(() => F('Empty', { dir: 'v', sw: 'fill' }))))
  return F('Metrics grid', { dir: 'v', gap: 12, sw: 'fill' }, rows)
}

/** Simple table: column widths (number or 'fill'), header labels, rows of cells (strings or nodes). */
export function table(cols, headers, rows, { name = 'Table', rowH = 48 } = {}) {
  const cell = (c, w, head) => F(`Cell`, { dir: 'h', gap: 8, cross: 'center', pad: [0, 12], h: head ? 40 : rowH, sh: 'fixed', ...(w === 'fill' ? { sw: 'fill' } : { w, sw: 'fixed' }) },
    typeof c === 'string' || typeof c === 'number' ? T(String(c), head ? 'caption' : 'bodyFg') : c)
  return F(name, { dir: 'v', sw: 'fill' },
    F('Head', { dir: 'h', sw: 'fill', stroke: '$border', sides: [0, 0, 1, 0] }, headers.map((h, i) => cell(h, cols[i], true))),
    rows.map((r, ri) => F(`Row ${ri + 1}`, { dir: 'h', sw: 'fill', stroke: '$border', sides: [0, 0, ri === rows.length - 1 ? 0 : 1, 0] }, r.map((c, i) => cell(c, cols[i], false)))),
  )
}

/** Vertical bar chart with optional x labels; values 0..1 relative heights. */
export function barChart(values, { h = 160, color = C.brand, labels = [], gap = 6, name = 'Bar chart', highlight = -1 } = {}) {
  return F(name, { dir: 'v', gap: 6, sw: 'fill' },
    F('Plot', { dir: 'h', gap, cross: 'max', sw: 'fill', h, sh: 'fixed', stroke: '$border', sides: [0, 0, 1, 0] },
      values.map((v, i) => R(`Bar ${i + 1}`, { sw: 'fill', h: Math.max(2, v * (h - 4)), radius: [3, 3, 0, 0], fill: i === highlight ? C.brandMid : color }))),
    labels.length > 0 && F('Labels', { dir: 'h', gap, sw: 'fill' }, labels.map((l) => T(l, { size: 11, color: '$muted-foreground' }, { sw: 'fill', align: 'center' }))),
  )
}
/** Line chart from values (0..1) in a fixed box, with light grid lines. */
export function lineChart(values, { w = 600, h = 180, color = C.brand, name = 'Line chart', fillArea = true, labels = [], yLabels = [] } = {}) {
  const step = w / (values.length - 1)
  const pts = values.map((v, i) => [i * step, h - 8 - v * (h - 16)])
  let d = `M${pts[0][0]} ${pts[0][1]}`
  for (let i = 1; i < pts.length; i++) {
    const [x0, y0] = pts[i - 1], [x1, y1] = pts[i], cx = (x0 + x1) / 2
    d += ` C${cx} ${y0} ${cx} ${y1} ${x1} ${y1}`
  }
  const grid = [0.25, 0.5, 0.75].map((f, i) => P(`Grid ${i + 1}`, `M0 0 L${w} 0`, { x: 0, y: Math.round(h * f), w, h: 1, stroke: '$border', strokeW: 1 }))
  return F(name, { dir: 'v', gap: 6, sw: 'fill' },
    F('Plot', { w, h, sh: 'fixed', clip: false, stroke: '$border', sides: [0, 0, 1, 0] },
      grid,
      fillArea && P('Area', d + ` L${w} ${h} L0 ${h} Z`, { x: 0, y: 0, w, h, fill: color + '1F', stroke: null }),
      P('Line', d, { x: 0, y: 0, w, h, stroke: color, strokeW: 2.5 }),
      E('Last point', { x: pts.at(-1)[0] - 5, y: pts.at(-1)[1] - 5, w: 10, h: 10, fill: color, stroke: '$card', strokeW: 2, strokeAlign: 'outside' }),
    ),
    labels.length > 0 && F('Labels', { dir: 'h', main: 'between', w, sw: 'fixed' }, labels.map((l) => T(l, 'micro'))),
  )
}

/** Stylised map thumbnail with a route, in theme-aware map colours. */
export function mapThumb({ w = 590, h = 260, route = 'loop', water = true, name = 'Map' } = {}) {
  const routes = {
    loop: 'M150 210 C160 170 200 140 250 128 C300 116 320 100 330 70 C338 46 352 30 372 34 C392 38 394 70 386 100 C376 140 400 170 430 200 C450 220 430 236 400 228 C360 218 330 236 290 230 C240 222 190 236 150 210 Z',
    ride: 'M60 210 C90 160 110 120 160 100 C210 80 250 60 300 50 C360 38 420 50 470 80 C520 110 540 160 500 195 C460 228 400 214 350 220 C290 228 250 240 190 236 C130 232 90 236 60 210 Z',
    out: 'M40 220 C120 200 160 150 220 140 C280 130 300 90 360 80 C420 70 470 60 540 40',
  }
  const sx = w / 590, sy = h / 260
  const sc = (d) => d.replace(/(-?\d+\.?\d*) (-?\d+\.?\d*)/g, (_, a, b) => `${+(a * sx).toFixed(1)} ${+(b * sy).toFixed(1)}`)
  return F(name, { w, h, radius: 8, clip: true, fill: '$map/land', sw: 'fill', sh: 'fixed' },
    water && P('Lake', sc('M330 0 L590 0 L590 260 L470 260 C440 220 420 190 400 150 C380 110 350 60 330 0 Z'), { x: 0, y: 0, w, h, fill: '$map/water', stroke: null }),
    R('Park', { x: 40 * sx, y: 150 * sy, w: 140 * sx, h: 80 * sy, radius: 18, fill: '$map/park' }),
    R('Park 2', { x: 200 * sx, y: 20 * sy, w: 90 * sx, h: 60 * sy, radius: 14, fill: '$map/park' }),
    P('Road', sc('M0 110 L330 90'), { x: 0, y: 0, w, h, stroke: '$map/road', strokeW: 6 }),
    P('Road 2', sc('M120 0 L170 260'), { x: 0, y: 0, w, h, stroke: '$map/road', strokeW: 5 }),
    P('Road 3', sc('M0 200 L250 175 L380 230'), { x: 0, y: 0, w, h, stroke: '$map/road', strokeW: 4 }),
    P('Route', sc(routes[route]), { x: 0, y: 0, w, h, stroke: C.brand, strokeW: 4 }),
  )
}

/** Left settings-style nav list (used by Settings and Health). */
export function sideNav(items, active, { w = 240, title } = {}) {
  return card('Side nav', { w, sw: 'fixed', pad: 8, gap: 2 },
    title && F('Title', { dir: 'h', pad: [8, 8, 4, 8], sw: 'fill' }, T(title, 'caption')),
    items.map(([label, icon], i) => F(`Nav / ${label}${i === active ? ' (active)' : ''}`, {
      dir: 'h', gap: 10, pad: [8, 10], radius: 8, cross: 'center', sw: 'fill', fill: i === active ? '$secondary' : null,
    }, I(icon, i === active ? '$secondary-foreground' : '$muted-foreground', 16), T(label, { size: 14, weight: i === active ? 600 : 400, color: i === active ? '$secondary-foreground' : '$foreground' }))),
  )
}

export const divider = () => R('Divider', { h: 1, sw: 'fill', fill: '$border' })
export function emptyState(title, desc, icon = 'inbox', action) {
  return F('Empty state', { dir: 'v', gap: 12, pad: [48, 16], cross: 'center', sw: 'fill' },
    I(icon, '$muted-foreground', 32), T(title, 'itemTitle'), T(desc, 'body', { align: 'center' }), action)
}
export function statTile(label, value, unit, { icon, color, sub } = {}) {
  return card(`Stat / ${label}`, { gap: 6 },
    row('Label', { gap: 6 }, icon && I(icon, '$muted-foreground', 16), T(label, 'caption')),
    F('Value', { dir: 'h', gap: 4, cross: 'baseline' }, T(value, { size: 26, weight: 600, color: color ?? '$foreground' }), unit && T(unit, 'hint')),
    sub && T(sub, 'hint'))
}
export const pagination = (page = 1, pages = 5) =>
  row('Pagination', { gap: 4, main: 'center', sw: 'fill' }, button('', { variant: 'ghost', icon: 'chevron-left', size: 'sm' }),
    Array.from({ length: pages }, (_, i) => F(`Page ${i + 1}`, { dir: 'h', w: 32, h: 32, radius: 8, main: 'center', cross: 'center', fill: i + 1 === page ? '$primary' : null, stroke: i + 1 === page ? null : '$border' }, T(String(i + 1), { size: 14, weight: 600, color: i + 1 === page ? '$primary-foreground' : '$foreground' }))),
    button('', { variant: 'ghost', icon: 'chevron-right', size: 'sm' }))

export { F, T, R, E, I, P, INST, IMG, C }
