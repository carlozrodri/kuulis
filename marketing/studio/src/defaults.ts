import { datoProps, laminaProps, portadaProps, subtitulosProps } from './schema'
import type { DatoProps, LaminaProps, PortadaProps, SubtitulosProps } from './schema'

// Default props: what the Studio shows. Remotion merges them shallowly under every render's props, so they
// must not set a top-level optional key (voz, imagen, texto, destacado): a piece that leaves it out would
// inherit the sample. tests/schema.test.ts checks this.
export const subtitulosDefault: SubtitulosProps = subtitulosProps.parse({
  fondo: { tipo: 'color', color: 'noche' },
  gancho: { texto: 'Soy una IA y vengo a hablarte de plata.' },
  subtitulos: [{ desdeS: 3, hastaS: 7, texto: 'Si ganaste $150 y la app te quita el 20 %, se te fueron $30.' }],
  textos: [{ desdeS: 3, hastaS: 7, texto: '$150 → −20 % = −$30', destacado: '−$30' }],
  duracionS: 8,
})

export const datoDefault: DatoProps = datoProps.parse({
  pasos: [
    { cifra: '$0', texto: 'si ganaste $100 o menos en el mes' },
    { cifra: '$30', texto: 'lo máximo que pagas, ganes lo que ganes' },
    { cifra: '3', texto: 'meses sin cuota al empezar' },
  ],
})

export const laminaDefault: LaminaProps = laminaProps.parse({
  titulo: 'Carrera de $3. ¿Cuánto es tuyo?',
  indice: 1,
  total: 6,
})

export const portadaDefault: PortadaProps = portadaProps.parse({
  fondo: { tipo: 'color', color: 'verde' },
  titulo: 'Lo que cobras es tuyo.',
})
