import type { CSSProperties, ReactNode } from 'react'
import { AbsoluteFill, Img, Sequence, interpolate, random, spring, staticFile, useCurrentFrame, useVideoConfig } from 'remotion'
import { color, font, safe } from '../brand'
import { Wordmark } from '../components/brand'
import { formatUsd } from '../lib/text'

export type Escena = {
  tipo: string
  texto: string
  from: number
  dur: number
  [k: string]: unknown
}
export type WowProps = { escenas: Escena[]; lista?: string[] }

// 100 BPM at 30 fps: one beat every 18 frames. The music track uses the same tempo.
const BEAT = 18
const clamp = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const

export const Wow = ({ escenas, lista = [] }: WowProps) => (
  <AbsoluteFill style={{ backgroundColor: color.night }}>
    <Fondo />
    {escenas.map((e, i) => (
      <Sequence key={i} from={e.from} durationInFrames={e.dur} name={`${i} ${e.tipo}`}>
        <Entrada>
          <EscenaView e={e} lista={lista} />
        </Entrada>
      </Sequence>
    ))}
    <Grano />
  </AbsoluteFill>
)

const EscenaView = ({ e, lista }: { e: Escena; lista: string[] }) => {
  switch (e.tipo) {
    case 'chat':
      return <Chat texto={e.texto} />
    case 'slam':
      return <Slam texto={e.texto} sub={e.sub as string | undefined} temblor={!!e.temblor} />
    case 'tachado':
      return <Tachado texto={e.texto} tachar={e.tachar as string} />
    case 'telefono':
      return <Telefono texto={e.texto} />
    case 'duo':
      return <Duo a={e.a as string} b={e.b as string} texto={e.texto} />
    case 'contador':
      return <Contador desde={e.desde as number} hasta={e.hasta as number} texto={e.texto} etiqueta={e.etiqueta as string | undefined} fiesta={!!e.fiesta} />
    case 'chip':
      return <Chips lista={lista} n={e.n as number} />
    case 'tarjeta':
      return <Tarjeta texto={e.texto} />
    case 'pin':
      return <Pin texto={e.texto} />
    case 'mapa':
      return <Mapa texto={e.texto} />
    case 'sos':
      return <Sos texto={e.texto} />
    case 'cierre':
      return <Cierre texto={e.texto} />
    default:
      return <Slam texto={e.texto} />
  }
}

/* ---------- ambience ---------- */

const Fondo = () => {
  const frame = useCurrentFrame()
  const pulse = Math.exp(-(frame % BEAT) / 5)
  const blob = (i: number, c: string, size: number): CSSProperties => {
    const x = 50 + 38 * Math.sin(frame / (70 + i * 23) + i * 2)
    const y = 45 + 35 * Math.cos(frame / (90 + i * 17) + i)
    return {
      position: 'absolute',
      left: `${x}%`,
      top: `${y}%`,
      width: size,
      height: size,
      marginLeft: -size / 2,
      marginTop: -size / 2,
      borderRadius: '50%',
      background: `radial-gradient(circle, ${c} 0%, transparent 65%)`,
      opacity: 0.55 + pulse * 0.15,
    }
  }
  return (
    <AbsoluteFill style={{ overflow: 'hidden' }}>
      <div style={blob(0, color.primary, 1500)} />
      <div style={blob(1, color.primaryDeep, 1300)} />
      <div style={{ ...blob(2, 'rgba(255,200,61,0.35)', 900) }} />
      <AbsoluteFill style={{ background: 'radial-gradient(ellipse at center, transparent 40%, rgba(0,0,0,0.65) 100%)' }} />
    </AbsoluteFill>
  )
}

const Grano = () => {
  const frame = useCurrentFrame()
  return (
    <AbsoluteFill style={{ opacity: 0.09, mixBlendMode: 'overlay', pointerEvents: 'none' }}>
      <svg width="1080" height="1920">
        <filter id="g">
          <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed={frame % 12} />
        </filter>
        <rect width="1080" height="1920" filter="url(#g)" />
      </svg>
    </AbsoluteFill>
  )
}

/** Every scene punches in: a quick zoom with a white flash on the cut. */
const Entrada = ({ children }: { children: ReactNode }) => {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const s = spring({ frame, fps, config: { damping: 14, stiffness: 220 } })
  const flash = interpolate(frame, [0, 4], [0.5, 0], clamp)
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ transform: `scale(${1.25 - 0.25 * s + 0.018 * Math.exp(-(frame % BEAT) / 3)})`, filter: `blur(${(1 - s) * 14}px)` }}>{children}</AbsoluteFill>
      <AbsoluteFill style={{ backgroundColor: color.white, opacity: flash }} />
    </AbsoluteFill>
  )
}

const Zone = ({ style, children }: { style?: CSSProperties; children: ReactNode }) => (
  <div
    style={{
      position: 'absolute',
      top: safe.top,
      bottom: safe.bottom,
      left: safe.left,
      right: safe.right,
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
      ...style,
    }}
  >
    {children}
  </div>
)

const poster = (size: number, extra?: CSSProperties): CSSProperties => ({
  fontFamily: font.poster,
  fontWeight: 900,
  fontStretch: '64%',
  fontSize: size,
  lineHeight: 0.9,
  color: color.white,
  textTransform: 'uppercase',
  ...extra,
})

const sans = (size: number, extra?: CSSProperties): CSSProperties => ({
  fontFamily: font.sans,
  fontWeight: 800,
  fontSize: size,
  lineHeight: 1.12,
  color: color.white,
  letterSpacing: '-0.01em',
  ...extra,
})

/** Headline whose final period is the yellow brand dot. */
const Titular = ({ texto, size = 92, style }: { texto: string; size?: number; style?: CSSProperties }) => {
  const frame = useCurrentFrame()
  const t = texto.trimEnd()
  const dot = t.endsWith('.') && !t.endsWith('..')
  const body = dot ? t.slice(0, -1) : t
  const words = body.split(' ')
  return (
    <div style={{ ...sans(size), textWrap: 'balance', ...style }}>
      {words.map((w, i) => {
        const k = interpolate(frame, [4 + i * 2, 10 + i * 2], [0, 1], clamp)
        return (
          <span key={i} style={{ display: 'inline-block', opacity: k, transform: `translateY(${(1 - k) * 40}px)`, marginRight: '0.24em' }}>
            {w}
            {dot && i === words.length - 1 && <span style={{ color: color.accent }}>.</span>}
          </span>
        )
      })}
    </div>
  )
}

const Etiqueta = ({ children, style }: { children: ReactNode; style?: CSSProperties }) => (
  <span
    style={{
      ...sans(34, { fontWeight: 700 }),
      alignSelf: 'flex-start',
      padding: '10px 22px',
      borderRadius: 999,
      background: 'rgba(255,255,255,0.12)',
      border: '2px solid rgba(255,255,255,0.25)',
      ...style,
    }}
  >
    {children}
  </span>
)

const shake = (frame: number, amount: number) => {
  const k = Math.max(0, 1 - frame / 14) * amount
  return `translate(${(random(`x${frame}`) - 0.5) * k}px, ${(random(`y${frame}`) - 0.5) * k}px)`
}

/* ---------- scenes ---------- */

const Chat = ({ texto }: { texto: string }) => {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const typing = frame < 12
  const s = spring({ frame: frame - 2, fps, config: { damping: 11, stiffness: 180 } })
  return (
    <Zone style={{ alignItems: 'flex-end' }}>
      <div style={{ ...sans(34, { fontWeight: 600, opacity: 0.7, marginBottom: 18 }) }}>Caracas, 7:42 p. m.</div>
      <div
        style={{
          transform: `scale(${s})`,
          transformOrigin: 'bottom right',
          background: color.white,
          color: color.ink,
          borderRadius: '56px 56px 12px 56px',
          padding: typing ? '40px 56px' : '44px 56px',
          boxShadow: '0 30px 80px rgba(0,0,0,0.45)',
          maxWidth: 820,
        }}
      >
        {typing ? (
          <div style={{ display: 'flex', gap: 18 }}>
            {[0, 1, 2].map((i) => (
              <div key={i} style={{ width: 28, height: 28, borderRadius: 14, background: color.ink, opacity: 0.3 + 0.7 * Math.abs(Math.sin((frame + i * 4) / 4)) }} />
            ))}
          </div>
        ) : (
          <div style={{ ...sans(96, { color: color.ink }) }}>{texto}</div>
        )}
      </div>
    </Zone>
  )
}

const Slam = ({ texto, sub, temblor }: { texto: string; sub?: string; temblor?: boolean }) => {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const lines = texto.split('\n')
  const longest = Math.max(...lines.map((l) => l.length))
  const size = Math.min(330, Math.round(1500 / Math.max(longest, 4)))
  return (
    <Zone style={{ transform: temblor ? shake(frame - 8, 50) : undefined }}>
      {lines.map((l, i) => {
        const s = spring({ frame: frame - i * 5, fps, config: { damping: 12, stiffness: 260 } })
        const dot = l.endsWith('.')
        const body = dot ? l.slice(0, -1) : l
        return (
          <div key={i} style={{ ...poster(size), opacity: Math.min(1, s * 2), transform: `scale(${2.4 - 1.4 * s})`, transformOrigin: 'left center' }}>
            {body.includes('%') || /^\d/.test(body) ? <span style={{ color: color.accent }}>{body}</span> : body}
            {dot && <span style={{ color: color.accent }}>.</span>}
          </div>
        )
      })}
      {sub && <Titular texto={sub} size={54} style={{ marginTop: 40, opacity: 0.85 }} />}
    </Zone>
  )
}

const Tachado = ({ texto, tachar }: { texto: string; tachar: string }) => {
  const frame = useCurrentFrame()
  const lines = texto.split('\n')
  const bar = interpolate(frame, [10, 18], [0, 1], clamp)
  return (
    <Zone>
      {lines.map((l, i) => (
        <div key={i} style={{ ...poster(250), position: 'relative', alignSelf: 'flex-start' }}>
          <span style={{ opacity: l === tachar ? 1 - bar * 0.55 : 1 }}>{l}</span>
          {l === tachar && (
            <div
              style={{
                position: 'absolute',
                left: -16,
                top: '42%',
                height: 34,
                width: `calc(${bar * 100}% + 32px)`,
                background: color.accent,
                transform: 'rotate(-4deg)',
                borderRadius: 8,
                boxShadow: '0 10px 30px rgba(0,0,0,0.4)',
              }}
            />
          )}
        </div>
      ))}
    </Zone>
  )
}

const Telefono = ({ texto }: { texto: string }) => {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const up = spring({ frame, fps, config: { damping: 15, stiffness: 120 } })
  const float = Math.sin(frame / 14) * 10
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', top: safe.top, left: safe.left, right: safe.right }}>
        <Titular texto={texto} size={90} />
      </div>
      <div
        style={{
          position: 'absolute',
          left: 160,
          top: 560,
          width: 760,
          height: 1400,
          transform: `translateY(${(1 - up) * 900 + float}px) rotate(${(1 - up) * 12}deg)`,
        }}
      >
        <div style={{ position: 'absolute', inset: 80, borderRadius: 120, background: color.accent, filter: 'blur(120px)', opacity: 0.35 }} />
        <Img src={staticFile('wow/telefono-cotizacion.png')} style={{ position: 'absolute', inset: 0, width: 760, height: 1400 }} />
      </div>
      <div style={{ position: 'absolute', right: safe.right + 10, top: 600, ...sans(26, { fontWeight: 600, opacity: 0.6 }) }}>Pantalla de ejemplo</div>
    </AbsoluteFill>
  )
}

const Duo = ({ a, b, texto }: { a: string; b: string; texto: string }) => {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const s = spring({ frame, fps, config: { damping: 10, stiffness: 160 } })
  const coin = (label: string, dir: number, bg: string, fg: string) => (
    <div
      style={{
        width: 380,
        height: 380,
        borderRadius: 190,
        background: bg,
        color: fg,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        ...poster(210, { color: fg, textTransform: 'none' }),
        boxShadow: '0 40px 90px rgba(0,0,0,0.5), inset 0 -16px 0 rgba(0,0,0,0.15)',
        transform: `translateX(${dir * (1 - s) * 700}px) rotate(${dir * (1 - s) * 90}deg)`,
      }}
    >
      {label}
    </div>
  )
  return (
    <Zone style={{ alignItems: 'center' }}>
      <div style={{ display: 'flex', gap: 30, alignItems: 'center' }}>
        {coin(a, -1, color.accent, color.ink)}
        <div style={{ ...poster(160), opacity: s }}>+</div>
        {coin(b, 1, color.white, color.primaryDeep)}
      </div>
      <Titular texto={texto} size={76} style={{ marginTop: 80, textAlign: 'center' }} />
    </Zone>
  )
}

const Contador = ({ desde, hasta, texto, etiqueta, fiesta }: { desde: number; hasta: number; texto: string; etiqueta?: string; fiesta?: boolean }) => {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const k = interpolate(frame, [8, 26], [0, 1], { ...clamp, easing: (t) => 1 - Math.pow(1 - t, 3) })
  const value = desde + (hasta - desde) * k
  const shown = Math.round(value * 10) / 10
  const down = hasta < desde
  const cut = spring({ frame: frame - 4, fps, config: { damping: 12, stiffness: 200 } })
  return (
    <Zone>
      <Etiqueta>Ejemplo</Etiqueta>
      <div
        style={{
          ...poster(520, { color: fiesta ? color.accent : color.white, letterSpacing: '-0.02em' }),
          marginTop: 30,
          transform: down && k > 0 && k < 1 ? shake(frame, 18) : undefined,
          textShadow: fiesta ? `0 0 ${60 + Math.sin(frame / 3) * 20}px rgba(255,200,61,0.55)` : undefined,
        }}
      >
        {formatUsd(k >= 1 ? hasta : shown)}
      </div>
      {etiqueta && (
        <div style={{ ...poster(150, { color: color.ink }), alignSelf: 'flex-start', background: color.white, padding: '6px 28px', borderRadius: 18, transform: `rotate(-6deg) scale(${cut})`, marginTop: -10 }}>
          {etiqueta}
        </div>
      )}
      <Titular texto={texto} size={72} style={{ marginTop: 50 }} />
      {fiesta && <Confeti />}
    </Zone>
  )
}

const Confeti = () => {
  const frame = useCurrentFrame()
  const colors = [color.accent, color.white, color.primary, color.accent]
  return (
    <AbsoluteFill style={{ position: 'absolute', left: -safe.left, top: -safe.top, width: 1080, height: 1920, pointerEvents: 'none' }}>
      {Array.from({ length: 70 }).map((_, i) => {
        const t = Math.max(0, frame - 6) / 30
        const angle = random(`a${i}`) * Math.PI * 2
        const speed = 700 + random(`s${i}`) * 900
        const x = 540 + Math.cos(angle) * speed * t
        const y = 820 + Math.sin(angle) * speed * t + 900 * t * t
        const r = random(`r${i}`) * 720 * t * 3
        return (
          <div
            key={i}
            style={{
              position: 'absolute',
              left: x,
              top: y,
              width: 18 + random(`w${i}`) * 16,
              height: 30 + random(`h${i}`) * 20,
              background: colors[i % colors.length],
              transform: `rotate(${r}deg)`,
              opacity: frame < 6 ? 0 : 1,
              borderRadius: 4,
            }}
          />
        )
      })}
    </AbsoluteFill>
  )
}

const Chips = ({ lista, n }: { lista: string[]; n: number }) => {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  return (
    <Zone>
      <Etiqueta style={{ marginBottom: 40 }}>¿Cómo pagas?</Etiqueta>
      {lista.slice(0, n + 1).map((item, i) => {
        const current = i === n
        const s = current ? spring({ frame, fps, config: { damping: 11, stiffness: 240 } }) : 1
        return (
          <div
            key={item}
            style={{
              ...poster(current ? 170 : 96, { color: current ? color.ink : color.white, textTransform: 'none', whiteSpace: 'nowrap' }),
              alignSelf: 'flex-start',
              background: current ? color.accent : 'rgba(255,255,255,0.12)',
              padding: current ? '16px 44px 6px' : '10px 30px 2px',
              borderRadius: current ? 36 : 22,
              marginTop: 18,
              transform: `translateX(${(1 - s) * -900}px) rotate(${current ? (1 - s) * -10 - 2 : 0}deg)`,
              boxShadow: current ? '0 30px 70px rgba(0,0,0,0.45)' : undefined,
            }}
          >
            {item}
          </div>
        )
      })}
    </Zone>
  )
}

const Check = ({ on }: { on: number }) => (
  <svg width="64" height="64" viewBox="0 0 64 64">
    <circle cx="32" cy="32" r="30" fill={color.accent} opacity={on} />
    <path d="M18 33 l9 9 l19 -20" stroke={color.ink} strokeWidth="7" fill="none" strokeLinecap="round" strokeLinejoin="round" strokeDasharray="60" strokeDashoffset={60 * (1 - on)} />
  </svg>
)

const Tarjeta = ({ texto }: { texto: string }) => {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const up = spring({ frame, fps, config: { damping: 14, stiffness: 140 } })
  const items = ['Nombre', 'Foto', 'Moto', 'Placa']
  return (
    <Zone>
      <Titular texto={texto} size={96} />
      <div
        style={{
          marginTop: 60,
          background: color.white,
          borderRadius: 48,
          padding: 48,
          boxShadow: '0 40px 100px rgba(0,0,0,0.5)',
          transform: `translateY(${(1 - up) * 600}px) rotate(${(1 - up) * -8}deg)`,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 32 }}>
          <div style={{ width: 150, height: 150, borderRadius: 75, background: color.primary, display: 'flex', alignItems: 'flex-end', justifyContent: 'center', overflow: 'hidden' }}>
            <svg width="120" height="120" viewBox="0 0 120 120">
              <circle cx="60" cy="44" r="26" fill="rgba(255,255,255,0.85)" />
              <path d="M14 120 c0-30 20-46 46-46 s46 16 46 46z" fill="rgba(255,255,255,0.85)" />
            </svg>
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ height: 34, width: '70%', borderRadius: 17, background: '#DDE7E2' }} />
            <div style={{ height: 26, width: '45%', borderRadius: 13, background: '#EEF3F0', marginTop: 18 }} />
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 26, marginTop: 44 }}>
          {items.map((it, i) => {
            const on = interpolate(frame, [26 + i * 9, 32 + i * 9], [0, 1], clamp)
            return (
              <div key={it} style={{ display: 'flex', alignItems: 'center', gap: 18, ...sans(48, { color: color.ink, opacity: 0.35 + on * 0.65 }) }}>
                <Check on={on} />
                {it}
              </div>
            )
          })}
        </div>
      </div>
    </Zone>
  )
}

const Pin = ({ texto }: { texto: string }) => {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const typed = Math.min(4, Math.floor(Math.max(0, frame - 6) / 6))
  const ok = spring({ frame: frame - 34, fps, config: { damping: 10, stiffness: 200 } })
  return (
    <Zone>
      <Titular texto={texto} size={96} />
      <div style={{ display: 'flex', gap: 28, marginTop: 80 }}>
        {[0, 1, 2, 3].map((i) => {
          const filled = i < typed
          return (
            <div
              key={i}
              style={{
                width: 170,
                height: 210,
                borderRadius: 36,
                background: ok > 0.5 ? color.accent : 'rgba(255,255,255,0.1)',
                border: `5px solid ${filled ? color.accent : 'rgba(255,255,255,0.3)'}`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transform: `scale(${filled && i === typed - 1 && ok < 0.1 ? 1.08 : 1})`,
              }}
            >
              {filled && <div style={{ width: 54, height: 54, borderRadius: 27, background: ok > 0.5 ? color.ink : color.white }} />}
            </div>
          )
        })}
      </div>
      <div style={{ ...poster(150, { color: color.accent }), marginTop: 70, opacity: ok, transform: `scale(${0.6 + 0.4 * ok})`, transformOrigin: 'left center' }}>¡Arrancamos!</div>
    </Zone>
  )
}

const Mapa = ({ texto }: { texto: string }) => {
  const frame = useCurrentFrame()
  const route = 'M140 1300 C 260 1120, 520 1220, 560 1020 S 820 800, 900 640'
  const len = 1400
  const draw = interpolate(frame, [4, 40], [0, 1], clamp)
  const live = 0.5 + 0.5 * Math.sin(frame / 4)
  return (
    <AbsoluteFill>
      <svg width="1080" height="1920" style={{ position: 'absolute' }}>
        {Array.from({ length: 9 }).map((_, i) => (
          <line key={`h${i}`} x1="0" x2="1080" y1={520 + i * 140} y2={470 + i * 150} stroke="rgba(255,255,255,0.07)" strokeWidth="18" />
        ))}
        {Array.from({ length: 7 }).map((_, i) => (
          <line key={`v${i}`} y1="400" y2="1920" x1={80 + i * 170} x2={140 + i * 160} stroke="rgba(255,255,255,0.07)" strokeWidth="18" />
        ))}
        <path d={route} stroke={color.accent} strokeWidth="16" fill="none" strokeLinecap="round" strokeDasharray={len} strokeDashoffset={len * (1 - draw)} />
        <circle cx="140" cy="1300" r="22" fill={color.white} />
        <MovingDot route={route} k={draw} />
      </svg>
      <div style={{ position: 'absolute', top: safe.top, left: safe.left, right: safe.right }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 26 }}>
          <div style={{ width: 26, height: 26, borderRadius: 13, background: color.accent, opacity: live }} />
          <span style={{ ...sans(40, { letterSpacing: '0.12em' }) }}>EN VIVO</span>
        </div>
        <Titular texto={texto} size={96} />
      </div>
      <div style={{ position: 'absolute', left: safe.left, bottom: safe.bottom + 20 }}>
        <Etiqueta style={{ background: color.white, color: color.ink, border: 'none' }}>Enlace del viaje enviado</Etiqueta>
      </div>
    </AbsoluteFill>
  )
}

/** Dot that rides the drawn route: sampled from the path so it sits exactly on the line. */
const MovingDot = ({ route, k }: { route: string; k: number }) => {
  const frame = useCurrentFrame()
  if (typeof document === 'undefined') return null
  const p = document.createElementNS('http://www.w3.org/2000/svg', 'path')
  p.setAttribute('d', route)
  const pt = p.getPointAtLength(p.getTotalLength() * k)
  const ring = (frame % 24) / 24
  return (
    <g>
      <circle cx={pt.x} cy={pt.y} r={30 + ring * 60} fill="none" stroke={color.accent} strokeWidth="6" opacity={1 - ring} />
      <circle cx={pt.x} cy={pt.y} r="30" fill={color.accent} stroke={color.ink} strokeWidth="8" />
    </g>
  )
}

const Sos = ({ texto }: { texto: string }) => {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const tap = spring({ frame: frame - 14, fps, config: { damping: 8, stiffness: 300 } })
  const press = frame >= 14 && frame < 20 ? 0.9 : 1
  const out = spring({ frame: frame - 22, fps, config: { damping: 12, stiffness: 160 } })
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', top: safe.top, left: safe.left, right: safe.right }}>
        <Titular texto={texto} size={88} />
      </div>
      <div style={{ position: 'absolute', left: 540 - 220, top: 900, width: 440, height: 440 }}>
        {[0, 1, 2].map((i) => {
          const r = ((frame + i * 10) % 30) / 30
          return <div key={i} style={{ position: 'absolute', inset: -r * 220, borderRadius: '50%', border: `6px solid ${color.accent}`, opacity: (1 - r) * Math.min(1, tap) }} />
        })}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            borderRadius: '50%',
            background: color.accent,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            ...poster(190, { color: color.ink }),
            transform: `scale(${press})`,
            boxShadow: '0 40px 100px rgba(0,0,0,0.5), inset 0 -18px 0 rgba(0,0,0,0.15)',
          }}
        >
          SOS
        </div>
      </div>
      <div style={{ position: 'absolute', top: 1390, left: 0, right: 0, display: 'flex', justifyContent: 'center', gap: 24 }}>
        {['Emergencias', 'Tus contactos'].map((t, i) => (
          <div
            key={t}
            style={{
              ...sans(44, { color: color.ink }),
              background: color.white,
              padding: '18px 30px',
              borderRadius: 999,
              opacity: out,
              transform: `translate(${(1 - out) * (i === 0 ? 200 : -200)}px, ${(1 - out) * -300}px) scale(${out})`,
            }}
          >
            {t}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  )
}

const Cierre = ({ texto }: { texto: string }) => {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const land = spring({ frame: frame - 4, fps, config: { damping: 9, stiffness: 170 } })
  const bg = spring({ frame, fps, config: { damping: 20, stiffness: 120 } })
  const cta = interpolate(frame, [14, 22], [0, 1], clamp)
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ background: color.primary, clipPath: `circle(${bg * 140}% at 50% 50%)` }} />
      <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', paddingBottom: 120 }}>
        <div style={{ transform: `scale(${0.6 + 0.4 * land})` }}>
          <Wordmark size={230} dotStyle={{ transform: `translateY(${interpolate(land, [0, 1], [-320, 0])}px)` }} />
        </div>
        <div style={{ ...sans(56), marginTop: 50, opacity: cta, transform: `translateY(${(1 - cta) * 30}px)` }}>{texto}</div>
        <div style={{ ...sans(38, { fontWeight: 600 }), marginTop: 22, opacity: cta * 0.85 }}>En la web de Kuulis · En Caracas</div>
        <div
          style={{
            marginTop: 60,
            opacity: cta,
            ...sans(44, { color: color.ink }),
            background: color.accent,
            padding: '22px 46px',
            borderRadius: 999,
            transform: `scale(${1 + 0.04 * Math.exp(-(frame % BEAT) / 4)})`,
          }}
        >
          Link en la bio
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  )
}
