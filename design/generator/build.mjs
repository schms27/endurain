// usage: node build.mjs out.json Page=module:export1,export2 ...
import { writeDoc } from './fc.mjs'
const [out, ...specs] = process.argv.slice(2)
const pages = {}
for (const s of specs) {
  const [page, rest] = s.split('=')
  const [mod, names] = rest.split(':')
  const m = await import('./' + mod + '.mjs')
  pages[page] = names.split(',').map((n) => { if (!m[n]) throw new Error('missing ' + n); return m[n] })
}
await writeDoc(out, pages)
console.log('wrote', out)
