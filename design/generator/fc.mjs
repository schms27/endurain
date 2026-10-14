// Tiny builder that compiles page specs into Figma-REST-style JSON that
// FigCraft's file.import understands, with colours bound to the Theme variables.
import fs from 'node:fs'
import { pathToFileURL } from 'node:url'

const LUCIDE = 'C:/Users/Simu/source/repos/endurain/frontend/node_modules/@lucide/vue/dist/esm/icons'

// Theme variables (ids from the document) with their Light values as fallbacks.
export const VARS = {
  background: [1, '#F1EFE8'], foreground: [2, '#2C2C2A'], card: [3, '#FFFFFF'],
  primary: [4, '#1D9E75'], 'primary-foreground': [5, '#FFFFFF'],
  secondary: [6, '#E1F5EE'], 'secondary-foreground': [7, '#0F6E56'],
  muted: [8, '#F1EFE8'], 'muted-foreground': [9, '#888780'],
  'muted-foreground-15': [10, '#88878026'], 'foreground-40': [11, '#2C2C2A66'],
  border: [12, '#00000014'], input: [13, '#00000026'],
  'map/land': [14, '#E7EDE4'], 'map/park': [15, '#D5E6C8'], 'map/water': [16, '#CBE0EC'], 'map/road': [17, '#FFFFFF'],
}
// Fixed (non-themed) brand / semantic colours, as in main.css @theme.
export const C = {
  brand: '#1D9E75', brandLight: '#E1F5EE', brandMid: '#0F6E56', effort: '#EF9F27', hr: '#E24B4A', info: '#378ADD',
  goal: '#639922', destructive: '#E24B4A', warning: '#D97706', white: '#FFFFFF', black: '#000000',
}

function rgba(hex) {
  const h = hex.replace('#', '')
  const n = (i) => parseInt(h.slice(i, i + 2), 16) / 255
  return { r: n(0), g: n(2), b: n(4), a: h.length >= 8 ? n(6) : 1 }
}
export function paint(c) {
  if (c == null) return null
  if (typeof c === 'object') return c
  if (c.startsWith('$')) {
    const [id, light] = VARS[c.slice(1)] ?? (() => { throw new Error('unknown var ' + c) })()
    const col = rgba(light.slice(0, 7))
    return { type: 'SOLID', color: col, boundVariables: { color: { type: 'VARIABLE_ALIAS', id: `VariableID:${id}` } } }
  }
  const col = rgba(c)
  const p = { type: 'SOLID', color: { ...col, a: 1 } }
  if (col.a < 1) p.opacity = col.a
  return p
}
const paints = (c) => (c == null ? [] : (Array.isArray(c) ? c : [c]).map(paint))

// ---------- Lucide → absolute M/L/C/Z path data scaled to `size` ----------
const iconCache = {}
let aliasMap = null
// Resolve renamed icons (e.g. trash-2 → trash) through the package index, as the app's imports do.
function resolveIcon(name) {
  if (fs.existsSync(`${LUCIDE}/${name}.mjs`)) return name
  if (!aliasMap) {
    aliasMap = {}
    const idx = fs.readFileSync(`${LUCIDE}/../lucide-vue.mjs`, 'utf8')
    for (const m of idx.matchAll(/export \{([^}]+)\} from '\.\/icons\/([^']+)\.mjs'/g))
      for (const a of m[1].matchAll(/as (\w+)/g)) aliasMap[a[1]] = m[2]
  }
  const pascal = name.split('-').map((s) => s[0].toUpperCase() + s.slice(1)).join('')
  const hit = aliasMap[pascal]
  if (!hit) throw new Error('unknown lucide icon ' + name)
  return hit
}
async function lucideNodes(name) {
  if (!iconCache[name]) iconCache[name] = (await import(pathToFileURL(`${LUCIDE}/${resolveIcon(name)}.mjs`).href)).__iconData.node
  return iconCache[name]
}
function tokenize(d) {
  const out = []
  const re = /([MmLlHhVvCcSsQqTtAaZz])|(-?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?)/g
  let m
  while ((m = re.exec(d))) out.push(m[1] ?? parseFloat(m[2]))
  return out
}
// Arc flags may be packed ("0 01"): re-split numbers after an arc command.
function tokenizeArcs(d) {
  const toks = []
  const re = /[MmLlHhVvCcSsQqTtAaZz]|-?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?/g
  let cmd = null, argi = 0, m
  let i = 0
  while (i < d.length) {
    const ch = d[i]
    if (/[MmLlHhVvCcSsQqTtAaZz]/.test(ch)) { toks.push(ch); cmd = ch; argi = 0; i++; continue }
    if (/[\s,]/.test(ch)) { i++; continue }
    if ((cmd === 'a' || cmd === 'A') && (argi % 7 === 3 || argi % 7 === 4)) { toks.push(+ch); argi++; i++; continue }
    re.lastIndex = i
    m = re.exec(d)
    toks.push(parseFloat(m[0])); argi++; i = m.index + m[0].length
  }
  return toks
}
function arcToCubics(x1, y1, rx, ry, phi, fa, fs_, x2, y2) {
  // SVG arc → cubic beziers (W3C implementation notes F.6).
  if (rx === 0 || ry === 0) return [[x1, y1, x2, y2, x2, y2]]
  const rad = (phi * Math.PI) / 180, cos = Math.cos(rad), sin = Math.sin(rad)
  const dx = (x1 - x2) / 2, dy = (y1 - y2) / 2
  const x1p = cos * dx + sin * dy, y1p = -sin * dx + cos * dy
  rx = Math.abs(rx); ry = Math.abs(ry)
  const lam = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
  if (lam > 1) { rx *= Math.sqrt(lam); ry *= Math.sqrt(lam) }
  const sign = fa === fs_ ? -1 : 1
  const num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
  const coef = sign * Math.sqrt(Math.max(0, num / (rx * rx * y1p * y1p + ry * ry * x1p * x1p)))
  const cxp = (coef * rx * y1p) / ry, cyp = (-coef * ry * x1p) / rx
  const cx = cos * cxp - sin * cyp + (x1 + x2) / 2, cy = sin * cxp + cos * cyp + (y1 + y2) / 2
  const ang = (ux, uy, vx, vy) => {
    const a = Math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
    return a
  }
  let t1 = ang(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
  let dt = ang((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry)
  if (!fs_ && dt > 0) dt -= 2 * Math.PI
  if (fs_ && dt < 0) dt += 2 * Math.PI
  const segs = Math.ceil(Math.abs(dt) / (Math.PI / 2))
  const res = []
  const d = dt / segs
  const k = (4 / 3) * Math.tan(d / 4)
  for (let s = 0; s < segs; s++) {
    const a1 = t1 + s * d, a2 = a1 + d
    const p = (a) => [cx + rx * Math.cos(a) * cos - ry * Math.sin(a) * sin, cy + rx * Math.cos(a) * sin + ry * Math.sin(a) * cos]
    const dp = (a) => [-rx * Math.sin(a) * cos - ry * Math.cos(a) * sin, -rx * Math.sin(a) * sin + ry * Math.cos(a) * cos]
    const [p1x, p1y] = p(a1), [p2x, p2y] = p(a2), [d1x, d1y] = dp(a1), [d2x, d2y] = dp(a2)
    res.push([p1x + k * d1x, p1y + k * d1y, p2x - k * d2x, p2y - k * d2y, p2x, p2y])
  }
  return res
}
// Convert any SVG path to absolute M/L/C/Z segments.
export function normalizePath(d) {
  const t = tokenizeArcs(d)
  const out = []
  let i = 0, cmd = null, x = 0, y = 0, sx = 0, sy = 0, lcx = null, lcy = null, lqx = null, lqy = null
  const num = () => t[i++]
  while (i < t.length) {
    if (typeof t[i] === 'string') cmd = t[i++]
    else if (cmd === 'M') cmd = 'L'
    else if (cmd === 'm') cmd = 'l'
    const rel = cmd === cmd.toLowerCase(), C_ = cmd.toUpperCase()
    const ox = rel ? x : 0, oy = rel ? y : 0
    let isC = false, isQ = false
    switch (C_) {
      case 'M': x = ox + num(); y = oy + num(); sx = x; sy = y; out.push(['M', x, y]); break
      case 'L': x = ox + num(); y = oy + num(); out.push(['L', x, y]); break
      case 'H': x = (rel ? x : 0) + num(); out.push(['L', x, y]); break
      case 'V': y = (rel ? y : 0) + num(); out.push(['L', x, y]); break
      case 'C': { const a = [ox + num(), oy + num(), ox + num(), oy + num(), ox + num(), oy + num()]; out.push(['C', ...a]); lcx = a[2]; lcy = a[3]; x = a[4]; y = a[5]; isC = true; break }
      case 'S': { const c1x = lcx != null ? 2 * x - lcx : x, c1y = lcy != null ? 2 * y - lcy : y; const a = [ox + num(), oy + num(), ox + num(), oy + num()]; out.push(['C', c1x, c1y, ...a]); lcx = a[0]; lcy = a[1]; x = a[2]; y = a[3]; isC = true; break }
      case 'Q': { const qx = ox + num(), qy = oy + num(), ex = ox + num(), ey = oy + num(); out.push(['C', x + (2 / 3) * (qx - x), y + (2 / 3) * (qy - y), ex + (2 / 3) * (qx - ex), ey + (2 / 3) * (qy - ey), ex, ey]); lqx = qx; lqy = qy; x = ex; y = ey; isQ = true; break }
      case 'T': { const qx = lqx != null ? 2 * x - lqx : x, qy = lqy != null ? 2 * y - lqy : y, ex = ox + num(), ey = oy + num(); out.push(['C', x + (2 / 3) * (qx - x), y + (2 / 3) * (qy - y), ex + (2 / 3) * (qx - ex), ey + (2 / 3) * (qy - ey), ex, ey]); lqx = qx; lqy = qy; x = ex; y = ey; isQ = true; break }
      case 'A': { const rx = num(), ry = num(), ph = num(), fa = num(), fsw = num(), ex = ox + num(), ey = oy + num(); for (const c of arcToCubics(x, y, rx, ry, ph, fa, fsw, ex, ey)) out.push(['C', ...c]); x = ex; y = ey; break }
      case 'Z': out.push(['Z']); x = sx; y = sy; break
      default: throw new Error('bad path cmd ' + cmd)
    }
    if (!isC) { lcx = null; lcy = null }
    if (!isQ) { lqx = null; lqy = null }
  }
  return out
}
const circlePath = (cx, cy, r) => `M${cx - r} ${cy} A${r} ${r} 0 1 0 ${cx + r} ${cy} A${r} ${r} 0 1 0 ${cx - r} ${cy} Z`
function elementToPath(tag, a) {
  const n = (k, d = 0) => (a[k] != null ? parseFloat(a[k]) : d)
  switch (tag) {
    case 'path': return a.d
    case 'circle': return circlePath(n('cx'), n('cy'), n('r'))
    case 'ellipse': { const cx = n('cx'), cy = n('cy'), rx = n('rx'), ry = n('ry'); return `M${cx - rx} ${cy} A${rx} ${ry} 0 1 0 ${cx + rx} ${cy} A${rx} ${ry} 0 1 0 ${cx - rx} ${cy} Z` }
    case 'line': return `M${n('x1')} ${n('y1')} L${n('x2')} ${n('y2')}`
    case 'polyline': case 'polygon': { const p = a.points.trim().split(/[\s,]+/).map(Number); let s = `M${p[0]} ${p[1]}`; for (let i = 2; i < p.length; i += 2) s += ` L${p[i]} ${p[i + 1]}`; return tag === 'polygon' ? s + ' Z' : s }
    case 'rect': {
      const x = n('x'), y = n('y'), w = n('width'), h = n('height'); let rx = a.rx != null ? n('rx') : n('ry'), ry = a.ry != null ? n('ry') : rx
      if (!rx) return `M${x} ${y} L${x + w} ${y} L${x + w} ${y + h} L${x} ${y + h} Z`
      return `M${x + rx} ${y} L${x + w - rx} ${y} A${rx} ${ry} 0 0 1 ${x + w} ${y + ry} L${x + w} ${y + h - ry} A${rx} ${ry} 0 0 1 ${x + w - rx} ${y + h} L${x + rx} ${y + h} A${rx} ${ry} 0 0 1 ${x} ${y + h - ry} L${x} ${y + ry} A${rx} ${ry} 0 0 1 ${x + rx} ${y} Z`
    }
    default: throw new Error('unknown svg element ' + tag)
  }
}
const fmt = (v) => +v.toFixed(3)
export function scalePath(d, s, dx = 0, dy = 0) {
  return normalizePath(d).map(([c, ...a]) => c + a.map((v, i) => fmt(i % 2 === 0 ? v * s + dx : v * s + dy)).join(' ')).join(' ')
}
async function iconPath(name, size) {
  const nodes = await lucideNodes(name)
  return nodes.map(([tag, a]) => scalePath(elementToPath(tag, a), size / 24)).join(' ')
}

// ---------------- Node constructors ----------------
// F(name, opts, ...children): frame. Children may be nested arrays / falsy (skipped).
export const F = (name, o = {}, ...kids) => ({ k: 'frame', name, o, kids: kids.flat(Infinity).filter(Boolean) })
export const T = (text, style = 'body', o = {}) => ({ k: 'text', text: String(text), style, o })
export const R = (name, o = {}) => ({ k: 'rect', name, o })
export const E = (name, o = {}) => ({ k: 'ellipse', name, o })
export const I = (name, color = '$muted-foreground', size = 16, o = {}) => ({ k: 'icon', icon: name, color, size, o })
export const P = (name, d, o = {}) => ({ k: 'path', name, d, o })
// Placeholders resolved after import: shared component instances and images.
export const INST = (key, o = {}) => F(`inst:${key}`, { dir: 'v', ...o })
export const IMG = (key, o = {}, ...kids) => F(`Image / ${key}`, { fill: '$muted', ...o }, F(`img-slot:${key}`, { x: 0, y: 0, w: o.w ?? 100, h: o.h ?? 100 }), ...kids)

export const STYLES = {
  display: { size: 44, weight: 600, color: '$foreground' },
  pageTitle: { size: 26, weight: 600, color: '$foreground' },
  cardHeading: { size: 22, weight: 600, color: '$foreground' },
  section: { size: 18, weight: 600, color: '$foreground' },
  itemTitle: { size: 15, weight: 600, color: '$foreground' },
  body: { size: 14, weight: 400, color: '$muted-foreground' },
  bodyFg: { size: 14, weight: 400, color: '$foreground' },
  label: { size: 13, weight: 600, color: '$foreground' },
  caption: { size: 11, weight: 600, color: '$muted-foreground', upper: true, ls: 0.3 },
  hint: { size: 12, weight: 400, color: '$muted-foreground' },
  metric: { size: 22, weight: 400, color: '$foreground' },
  metricBold: { size: 22, weight: 600, color: '$foreground' },
  meta: { size: 13, weight: 400, color: '$muted-foreground' },
  micro: { size: 11, weight: 400, color: '$muted-foreground' },
  button: { size: 14, weight: 600, color: '$foreground' },
  badge: { size: 12, weight: 600, color: '$foreground' },
  nav: { size: 14, weight: 400, color: '$muted-foreground' },
}

// ---------------- Compiler ----------------
let seq = 0
const nid = () => `9:${++seq}`
const ALIGN = { min: 'MIN', center: 'CENTER', max: 'MAX', between: 'SPACE_BETWEEN', baseline: 'BASELINE' }
function pad(p) {
  if (p == null) return [0, 0, 0, 0]
  if (typeof p === 'number') return [p, p, p, p]
  if (p.length === 2) return [p[0], p[1], p[0], p[1]]
  return p
}
function estimateText(text, st, o) {
  const lines = text.split('\n')
  const w = Math.max(...lines.map((l) => l.length)) * st.size * 0.56 + 2
  return { w: o.w ?? Math.min(w, 2000), h: Math.ceil(st.size * (st.lh ? st.lh / 100 : 1.22)) * lines.length }
}

async function compile(node, pabs, parentDir) {
  const o = node.o ?? {}
  const x = pabs.x + (o.x ?? 0), y = pabs.y + (o.y ?? 0)
  const base = { id: nid(), name: node.name ?? '', visible: o.visible ?? true }
  if (o.opacity != null) base.opacity = o.opacity
  // Sizing relative to the parent auto layout.
  const sizing = (axis, explicit, dflt) => {
    const v = explicit ?? dflt
    return v
  }
  const applyChildSizing = (n, sw, sh) => {
    n.layoutSizingHorizontal = sw.toUpperCase()
    n.layoutSizingVertical = sh.toUpperCase()
    if (parentDir === 'h') { n.layoutGrow = sw === 'fill' ? 1 : 0; if (sh === 'fill') n.layoutAlign = 'STRETCH' }
    else if (parentDir === 'v') { n.layoutGrow = sh === 'fill' ? 1 : 0; if (sw === 'fill') n.layoutAlign = 'STRETCH' }
    if (o.absolute) n.layoutPositioning = 'ABSOLUTE'
  }
  if (node.k === 'text') {
    const st = { ...(typeof node.style === 'string' ? STYLES[node.style] : node.style), ...(o.style ?? {}) }
    if (o.color) st.color = o.color
    const est = estimateText(node.text, st, o)
    const wrap = o.sw === 'fill' || o.w != null
    const n = {
      ...base, type: 'TEXT', characters: node.text, name: node.name ?? node.text.slice(0, 40),
      absoluteBoundingBox: { x, y, width: est.w, height: est.h },
      style: {
        fontFamily: 'Inter', fontWeight: st.weight ?? 400, fontSize: st.size, letterSpacing: st.ls ?? 0,
        textAlignHorizontal: (o.align ?? 'left').toUpperCase(), textAutoResize: wrap ? 'HEIGHT' : 'WIDTH_AND_HEIGHT',
        ...(st.upper ? { textCase: 'UPPER' } : {}),
        ...(st.lh ? { lineHeightUnit: 'FONT_SIZE_%', lineHeightPercentFontSize: st.lh } : {}),
        ...(o.underline ? { textDecoration: 'UNDERLINE' } : {}),
      },
      fills: paints(st.color),
    }
    applyChildSizing(n, o.sw ?? (o.w != null ? 'fixed' : 'hug'), 'hug')
    return n
  }
  if (node.k === 'rect' || node.k === 'ellipse') {
    const n = { ...base, type: node.k === 'rect' ? 'RECTANGLE' : 'ELLIPSE', absoluteBoundingBox: { x, y, width: o.w ?? 10, height: o.h ?? 10 }, fills: paints(o.fill), strokes: paints(o.stroke), strokeWeight: o.strokeW ?? 1, strokeAlign: (o.strokeAlign ?? 'inside').toUpperCase() }
    if (o.radius != null) Array.isArray(o.radius) ? (n.rectangleCornerRadii = o.radius) : (n.cornerRadius = o.radius)
    applyChildSizing(n, o.sw ?? 'fixed', o.sh ?? 'fixed')
    return n
  }
  if (node.k === 'icon' || node.k === 'path') {
    const size = node.size ?? 16
    const d = node.k === 'icon' ? await iconPath(node.icon, size) : node.d
    const w = o.w ?? size, h = o.h ?? size
    const n = {
      ...base, type: 'VECTOR', name: node.k === 'icon' ? `icon/${node.icon}` : node.name,
      absoluteBoundingBox: { x, y, width: w, height: h }, fills: paints(o.fill ?? null),
      strokes: paints(node.k === 'icon' ? node.color : o.stroke), strokeWeight: node.k === 'icon' ? (2 * size) / 24 : o.strokeW ?? 2,
      strokeCap: 'ROUND', strokeJoin: 'ROUND', fillGeometry: [{ path: d, windingRule: 'NONZERO' }],
    }
    applyChildSizing(n, 'fixed', 'fixed')
    return n
  }
  // frame
  const dir = o.dir ?? null
  const hasW = o.w != null, hasH = o.h != null
  const sw = o.sw ?? (hasW ? 'fixed' : dir ? 'hug' : 'fixed')
  const sh = o.sh ?? (hasH ? 'fixed' : dir ? 'hug' : 'fixed')
  const n = {
    ...base, type: 'FRAME', absoluteBoundingBox: { x, y, width: o.w ?? 100, height: o.h ?? 40 },
    fills: paints(o.fill), strokes: paints(o.stroke), strokeWeight: o.strokeW ?? 1, strokeAlign: 'INSIDE',
    clipsContent: o.clip ?? false, children: [],
  }
  if (o.sides) { const [t, r, b, l] = o.sides; n.individualStrokeWeights = { top: t, right: r, bottom: b, left: l } }
  if (o.radius != null) Array.isArray(o.radius) ? (n.rectangleCornerRadii = o.radius) : (n.cornerRadius = o.radius)
  if (o.shadow) n.effects = [{ type: 'DROP_SHADOW', visible: true, blendMode: 'NORMAL', color: { r: 0, g: 0, b: 0, a: 0.06 }, offset: { x: 0, y: 1 }, radius: 3, spread: 0 }]
  if (dir) {
    const [pt, pr, pb, pl] = pad(o.pad)
    Object.assign(n, {
      layoutMode: dir === 'h' ? 'HORIZONTAL' : 'VERTICAL', itemSpacing: o.gap ?? 0,
      paddingTop: pt, paddingRight: pr, paddingBottom: pb, paddingLeft: pl,
      primaryAxisAlignItems: ALIGN[o.main ?? 'min'], counterAxisAlignItems: ALIGN[o.cross ?? 'min'],
      primaryAxisSizingMode: (dir === 'h' ? sw : sh) === 'hug' ? 'AUTO' : 'FIXED',
      counterAxisSizingMode: (dir === 'h' ? sh : sw) === 'hug' ? 'AUTO' : 'FIXED',
    })
    if (o.wrap) { n.layoutWrap = 'WRAP'; n.counterAxisSpacing = o.rowGap ?? o.gap ?? 0 }
  }
  applyChildSizing(n, sw, sh)
  for (const kid of node.kids) n.children.push(await compile(kid, { x, y }, dir))
  return n
}

/** Builds a REST document from {pageName: [rootFrames]} and writes it. Root frames are laid out left→right. */
export async function writeDoc(file, pages) {
  const canvases = []
  let p = 0
  for (const [name, roots] of Object.entries(pages)) {
    const kids = []
    let cx = 0
    for (const r of roots) {
      const w = r.o?.w ?? 1440
      kids.push(await compile({ ...r, o: { ...r.o, x: cx, y: 0 } }, { x: 0, y: 0 }, null))
      cx += w + 160
    }
    canvases.push({ id: `8:${++p}`, type: 'CANVAS', name, backgroundColor: { r: 0.96, g: 0.96, b: 0.96, a: 1 }, children: kids })
  }
  fs.writeFileSync(file, JSON.stringify({ name: 'pages', document: { id: '0:0', type: 'DOCUMENT', name: 'Document', children: canvases } }))
  return file
}
