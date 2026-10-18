// Renders every output of a "pieza" file for the networks it lists.
//
//   pnpm render data/ejemplos/prueba-01.json [--out out/PRUEBA-01]
//
// Writes one file per network (TikTok, Reels and Shorts get the same clean 1080×1920 master, WhatsApp a
// 720×1280 copy) plus manifest.json, which the registry (MK5) will use to upload everything to S3.
// REMOTION_BROWSER_EXECUTABLE points at a local Chrome when Remotion cannot download its own.
import { copyFile, mkdir, readFile, rm, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { bundle } from '@remotion/bundler'
import { renderMedia, renderStill, selectComposition } from '@remotion/renderer'
import { pieza as piezaSchema, type Red, type Salida } from '../src/schema.ts'

type Output = { red: Red; plantilla: Salida['plantilla']; archivo: string; ancho: number; alto: number }

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const browserExecutable = process.env.REMOTION_BROWSER_EXECUTABLE || null

const args = process.argv.slice(2)
const file = args.find((a) => !a.startsWith('--'))
if (!file) {
  console.error('Uso: pnpm render <pieza.json> [--out <carpeta>]')
  process.exit(1)
}
const outFlag = args.indexOf('--out')

const parsed = piezaSchema.safeParse(JSON.parse(await readFile(path.resolve(file), 'utf8')))
if (!parsed.success) {
  console.error(`${file} no es una pieza válida:\n${parsed.error.issues.map((i) => `  ${i.path.join('.')}: ${i.message}`).join('\n')}`)
  process.exit(1)
}
const pieza = parsed.data
const outDir = path.resolve(outFlag !== -1 ? args[outFlag + 1] : path.join(root, 'out', pieza.codigo))
await mkdir(outDir, { recursive: true })

console.log(`Empaquetando plantillas…`)
const serveUrl = await bundle({ entryPoint: path.join(root, 'src/index.ts'), publicDir: path.join(root, 'public') })

const outputs: Output[] = []

const video = async (id: string, inputProps: Record<string, unknown>, name: string, redes: Red[], plantilla: Salida['plantilla']) => {
  const composition = await selectComposition({ serveUrl, id, inputProps, browserExecutable })
  const master = path.join(outDir, `${name}.master.mp4`)
  const full = redes.filter((r) => r !== 'whatsapp')
  if (full.length > 0) {
    console.log(`  ${name}.mp4 (${composition.durationInFrames / composition.fps} s)`)
    await renderMedia({ serveUrl, composition, inputProps, codec: 'h264', outputLocation: master, browserExecutable })
    for (const red of full) {
      const archivo = `${name}-${red}.mp4`
      await copyFile(master, path.join(outDir, archivo))
      outputs.push({ red, plantilla, archivo, ancho: composition.width, alto: composition.height })
    }
    await rm(master)
  }
  if (redes.includes('whatsapp')) {
    if (composition.durationInFrames / composition.fps > 30) console.warn(`  Aviso: ${name} pasa de 30 s; WhatsApp lo corta.`)
    const archivo = `${name}-whatsapp.mp4`
    console.log(`  ${archivo}`)
    await renderMedia({ serveUrl, composition, inputProps, codec: 'h264', scale: 2 / 3, outputLocation: path.join(outDir, archivo), browserExecutable })
    outputs.push({ red: 'whatsapp', plantilla, archivo, ancho: 720, alto: 1280 })
  }
}

const still = async (id: string, inputProps: Record<string, unknown>, archivo: string, red: Red, plantilla: Salida['plantilla']) => {
  const composition = await selectComposition({ serveUrl, id, inputProps, browserExecutable })
  console.log(`  ${archivo}`)
  await renderStill({ serveUrl, composition, inputProps, output: path.join(outDir, archivo), imageFormat: 'jpeg', jpegQuality: 92, browserExecutable })
  outputs.push({ red, plantilla, archivo, ancho: composition.width, alto: composition.height })
}

for (const [i, salida] of pieza.salidas.entries()) {
  const name = `${String(i + 1).padStart(2, '0')}-${salida.plantilla.toLowerCase()}`
  switch (salida.plantilla) {
    case 'Subtitulos':
    case 'Dato':
    case 'Cierre':
      await video(salida.plantilla, salida.props, name, salida.redes, salida.plantilla)
      break
    case 'Carrusel':
      for (const red of salida.redes) {
        // Instagram shows carousels at 4:5; TikTok's photo mode fills the screen.
        const formato = red === 'instagram' ? 'feed' : red === 'tiktok' ? 'vertical' : null
        if (!formato) {
          console.warn(`  Aviso: ${red} no publica carruseles; se omite.`)
          continue
        }
        for (const [n, lamina] of salida.laminas.entries()) {
          const props = { ...lamina, formato, indice: n + 1, total: salida.laminas.length }
          await still('Lamina', props, `${name}-${n + 1}-${red}.jpg`, red, salida.plantilla)
        }
      }
      break
    case 'Portada':
      for (const red of salida.redes) {
        await still('Portada', { ...salida.props, formato: 'vertical' }, `${name}-${red}.jpg`, red, salida.plantilla)
      }
      break
  }
}

await writeFile(
  path.join(outDir, 'manifest.json'),
  `${JSON.stringify({ codigo: pieza.codigo, generado: new Date().toISOString(), archivos: outputs }, null, 2)}\n`,
)
console.log(`Listo: ${outputs.length} archivos en ${path.relative(process.cwd(), outDir) || '.'}`)
