import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'
import { z } from 'zod'
import { datoDefault, laminaDefault, portadaDefault, subtitulosDefault } from '../src/defaults'
import { laminaProps, pieza, portadaProps, subtitulosProps } from '../src/schema'

const dir = path.join(__dirname, '../data/ejemplos')

describe('example pieces', () => {
  for (const file of readdirSync(dir).filter((f) => f.endsWith('.json'))) {
    it(`${file} is a valid pieza`, () => {
      const result = pieza.safeParse(JSON.parse(readFileSync(path.join(dir, file), 'utf8')))
      expect(result.success ? '' : JSON.stringify(result.error.issues)).toBe('')
    })
  }
})

describe('schema rules', () => {
  it('rejects a cue that ends before it starts', () => {
    const bad = { ...subtitulosDefault, subtitulos: [{ desdeS: 3, hastaS: 2, texto: 'x' }] }
    expect(subtitulosProps.safeParse(bad).success).toBe(false)
  })
  it('rejects lowercase piece codes', () => {
    expect(pieza.safeParse({ codigo: 'prueba-1', salidas: [] }).success).toBe(false)
  })
})

// Remotion spreads defaultProps under every render's props, so a default for an optional key would leak
// into pieces that leave it out (a carousel slide getting the sample's body text, for example).
describe('studio defaults', () => {
  const optionalKeys = (shape: Record<string, z.ZodTypeAny>, defaults: Record<string, unknown>) =>
    Object.keys(shape).filter((k) => shape[k] instanceof z.ZodOptional && defaults[k] !== undefined)

  it('set no optional keys without a schema default', () => {
    expect(optionalKeys(subtitulosProps.shape, subtitulosDefault)).toEqual([])
    expect(optionalKeys(laminaProps.shape, laminaDefault)).toEqual([])
    expect(optionalKeys(portadaProps.shape, portadaDefault)).toEqual([])
    expect(datoDefault.pasos.length).toBeGreaterThan(0)
  })
})
