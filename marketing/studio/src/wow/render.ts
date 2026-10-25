// node src/wow/render.ts <props.json> <out.mp4>  (silent video; audio is muxed afterwards)
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { bundle } from '@remotion/bundler'
import { renderMedia, selectComposition } from '@remotion/renderer'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const browserExecutable = process.env.REMOTION_BROWSER_EXECUTABLE || null
const jobs = process.argv.slice(2)
const serveUrl = await bundle({ entryPoint: path.join(root, 'src/wow/index.ts'), publicDir: path.join(root, 'public') })
for (let i = 0; i < jobs.length; i += 2) {
  const inputProps = JSON.parse(await readFile(jobs[i], 'utf8'))
  const composition = await selectComposition({ serveUrl, id: 'Wow', inputProps, browserExecutable })
  console.log(jobs[i + 1], composition.durationInFrames / composition.fps, 's')
  await renderMedia({ serveUrl, composition, inputProps, codec: 'h264', muted: true, outputLocation: jobs[i + 1], browserExecutable, concurrency: 4 })
}
