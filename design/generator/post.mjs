// usage: node post.mjs dump.json  → prints batch commands for placeholders in the dumped page(s)
import fs from 'node:fs'
const raw = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const root = Array.isArray(raw) ? JSON.parse(raw[0].text) : raw
const COMP = { Navbar: 11, Footer: 13, Logo: 525 }
const IMGS = { login: 'C:/Users/Simu/source/repos/endurain/frontend/src/assets/login.png' }
const cmds = []
;(function walk(n) {
  const m = /^inst:(.+)$/.exec(n.name ?? '')
  if (m && !(n.children ?? []).length && n.childCount !== 1) cmds.push({ command: 'instance.create', params: { component: COMP[m[1]], parent: n.id } })
  const im = /^img-slot:(.+)$/.exec(n.name ?? '')
  if (im && !(n.children ?? []).length && !n.childCount) cmds.push({ command: 'image.place', params: { path: IMGS[im[1]], parent: n.id, x: 0, y: 0, width: n.width, height: n.height, mode: 'fill' } })
  ;(n.children ?? []).forEach(walk)
})(root)
console.log(JSON.stringify(cmds))
console.error('roots:', (root.children ?? []).map((c) => `${c.id}=${c.name}`).join(', '))
