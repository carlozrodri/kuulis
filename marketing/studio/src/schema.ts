import { z } from 'zod'

// Props of every template and the "pieza" file the render script reads (data/ejemplos/*.json).
// Self-contained on purpose: scripts/render.ts imports it straight from Node, outside the bundler.

const seconds = z.number().nonnegative()

/** A file in public/ (relative path) or an http(s) URL, e.g. a presigned S3 link. */
export const src = z.string().min(1)

export const fondo = z.discriminatedUnion('tipo', [
  z.object({ tipo: z.literal('video'), src }),
  z.object({ tipo: z.literal('imagen'), src }),
  z.object({ tipo: z.literal('color'), color: z.enum(['noche', 'verde']) }),
])
export type Fondo = z.infer<typeof fondo>

export const cue = z
  .object({ desdeS: seconds, hastaS: seconds, texto: z.string().min(1) })
  .refine((c) => c.hastaS > c.desdeS, 'hastaS debe ser mayor que desdeS')

const textoEnPantalla = z
  .object({
    desdeS: seconds,
    hastaS: seconds,
    texto: z.string().min(1).max(60),
    destacado: z.string().optional(),
  })
  .refine((t) => t.hastaS > t.desdeS, 'hastaS debe ser mayor que desdeS')

export const subtitulosProps = z.object({
  fondo,
  gancho: z.object({ texto: z.string().min(1).max(70), duracionS: seconds.default(2.5) }),
  subtitulos: z.array(cue).default([]),
  /** Voice-over text to cut into cues automatically when `subtitulos` is empty. */
  voz: z.string().optional(),
  textos: z.array(textoEnPantalla).default([]),
  duracionS: z.number().positive().max(180),
  cierre: z.boolean().default(true),
})
export type SubtitulosProps = z.infer<typeof subtitulosProps>

export const datoProps = z.object({
  fondo: z.enum(['verde', 'noche']).default('verde'),
  pasos: z
    .array(
      z.object({
        cifra: z.string().max(12).optional(),
        texto: z.string().min(1).max(80),
        duracionS: z.number().positive().default(2.5),
      }),
    )
    .min(1)
    .max(8),
  cierre: z.boolean().default(true),
})
export type DatoProps = z.infer<typeof datoProps>

export const formato = z.enum(['vertical', 'feed'])

export const laminaProps = z.object({
  formato: formato.default('feed'),
  estilo: z.enum(['foto', 'verde', 'noche']).default('verde'),
  imagen: src.optional(),
  titulo: z.string().min(1).max(70),
  texto: z.string().max(160).optional(),
  destacado: z.string().optional(),
  indice: z.number().int().positive(),
  total: z.number().int().positive(),
})
export type LaminaProps = z.infer<typeof laminaProps>

export const portadaProps = z.object({
  formato: formato.default('vertical'),
  fondo,
  titulo: z.string().min(1).max(70),
})
export type PortadaProps = z.infer<typeof portadaProps>

export const cierreProps = z.object({
  cta: z.string().max(40).default('Android · link en la bio'),
})
export type CierreProps = z.infer<typeof cierreProps>

export const red = z.enum(['tiktok', 'instagram', 'youtube', 'whatsapp'])
export type Red = z.infer<typeof red>

const redes = z.array(red).min(1)

export const salida = z.discriminatedUnion('plantilla', [
  z.object({ plantilla: z.literal('Subtitulos'), redes, props: subtitulosProps }),
  z.object({ plantilla: z.literal('Dato'), redes, props: datoProps }),
  z.object({
    plantilla: z.literal('Carrusel'),
    redes,
    laminas: z.array(laminaProps.omit({ formato: true, indice: true, total: true })).min(2).max(10),
  }),
  z.object({ plantilla: z.literal('Portada'), redes, props: portadaProps.omit({ formato: true }) }),
  z.object({ plantilla: z.literal('Cierre'), redes, props: cierreProps }),
])
export type Salida = z.infer<typeof salida>

/** One file per piece: its code (it names the output folder) and what to render for which networks. */
export const pieza = z.object({
  codigo: z.string().regex(/^[A-Z0-9-]+$/, 'solo mayúsculas, números y guiones'),
  salidas: z.array(salida).min(1),
})
export type Pieza = z.infer<typeof pieza>
