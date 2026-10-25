import { AbsoluteFill, Sequence, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion'
import { CIERRE_S, color, font, safe } from '../brand'
import { Zone } from '../components/brand'
import type { DatoProps } from '../schema'
import { Cierre } from './Cierre'

/** Animated figures (F-DATO): one step per screen, a huge yellow figure and one short line under it. */
export const Dato = ({ fondo, pasos, cierre }: DatoProps) => {
  const { fps } = useVideoConfig()
  let at = 0
  const steps = pasos.map((p) => {
    const from = at
    at += Math.round(p.duracionS * fps)
    return { ...p, from, frames: Math.round(p.duracionS * fps) }
  })
  return (
    <AbsoluteFill style={{ backgroundColor: fondo === 'verde' ? color.primary : color.night }}>
      {steps.map((s, i) => (
        <Sequence key={i} from={s.from} durationInFrames={s.frames} name={`Paso ${i + 1}`}>
          <Step cifra={s.cifra} texto={s.texto} gancho={i === 0} />
        </Sequence>
      ))}
      {cierre && (
        <Sequence from={at} durationInFrames={Math.round(CIERRE_S * fps)} name="Cierre">
          <Cierre cta="Android · link en la bio" />
        </Sequence>
      )}
    </AbsoluteFill>
  )
}

/** The first step is the hook: its line is readable from frame 1 (only the slide moves). */
const Step = ({ cifra, texto, gancho = false }: { cifra?: string; texto: string; gancho?: boolean }) => {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const pop = spring({ frame, fps, config: { damping: 12, stiffness: 140 } })
  const lineIn = interpolate(frame, gancho ? [0, 10] : [6, 14], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
  return (
    <Zone style={{ top: safe.top + 200, left: safe.left, right: safe.right, bottom: safe.bottom, justifyContent: 'center' }}>
      {cifra && (
        <div
          style={{
            fontFamily: font.poster,
            fontWeight: 900,
            fontStretch: '62%',
            fontSize: cifra.length > 5 ? 300 : 420,
            lineHeight: 0.9,
            color: color.accent,
            transform: `scale(${0.7 + pop * 0.3})`,
            transformOrigin: 'left bottom',
            opacity: pop,
          }}
        >
          {cifra}
        </div>
      )}
      <div
        style={{
          marginTop: 36,
          fontFamily: font.sans,
          fontWeight: 800,
          fontSize: 72,
          lineHeight: 1.15,
          color: color.white,
          opacity: gancho ? 1 : lineIn,
          transform: `translateY(${(1 - lineIn) * 30}px)`,
          textWrap: 'balance',
        }}
      >
        {texto}
      </div>
    </Zone>
  )
}
