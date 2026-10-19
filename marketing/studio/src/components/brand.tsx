import type { CSSProperties, ReactNode } from 'react'
import { AbsoluteFill, Img, OffthreadVideo, staticFile } from 'remotion'
import { color, font } from '../brand'
import { splitFinalDot, splitHighlight } from '../lib/text'
import type { Fondo } from '../schema'

export const resolveSrc = (src: string) => (/^https?:\/\//.test(src) ? src : staticFile(src))

/** Full-frame background: a video, a photo (cover-cropped) or a flat brand color field. */
export const Background = ({ fondo, dim = 0 }: { fondo: Fondo; dim?: number }) => {
  const base: CSSProperties = { width: '100%', height: '100%', objectFit: 'cover' }
  return (
    <AbsoluteFill style={{ backgroundColor: fondo.tipo === 'color' && fondo.color === 'verde' ? color.primary : color.night }}>
      {fondo.tipo === 'video' && <OffthreadVideo src={resolveSrc(fondo.src)} style={base} muted={false} />}
      {fondo.tipo === 'imagen' && <Img src={resolveSrc(fondo.src)} style={base} />}
      {dim > 0 && <AbsoluteFill style={{ backgroundColor: `rgba(7, 18, 14, ${dim})` }} />}
    </AbsoluteFill>
  )
}

/**
 * An absolutely positioned flex column placed by its insets. AbsoluteFill can't do this: it also sets
 * width/height 100%, so `left`/`right` would push it past the frame.
 */
export const Zone = ({ style, children }: { style: CSSProperties; children: ReactNode }) => (
  <div style={{ position: 'absolute', display: 'flex', flexDirection: 'column', ...style }}>{children}</div>
)

/** Condensed poster headline whose closing period is the yellow brand dot. */
export const PosterHeadline = ({ text, size, style }: { text: string; size: number; style?: CSSProperties }) => {
  const { body, dot } = splitFinalDot(text)
  return (
    <div
      style={{
        fontFamily: font.poster,
        fontWeight: 900,
        fontStretch: '68%',
        fontSize: size,
        lineHeight: 0.92,
        color: color.white,
        textTransform: 'uppercase',
        textWrap: 'balance',
        // A "\n" in the headline is a deliberate line break.
        whiteSpace: 'pre-line',
        ...style,
      }}
    >
      {body}
      {dot && <span style={{ color: color.accent }}>.</span>}
    </div>
  )
}

/** Body text with one phrase (a figure, usually) in the brand yellow. */
export const Highlighted = ({ text, highlight }: { text: string; highlight?: string }) => (
  <>
    {splitHighlight(text, highlight).map((part, i) =>
      part.highlight ? (
        <span key={i} style={{ color: color.accent }}>
          {part.text}
        </span>
      ) : (
        <span key={i}>{part.text}</span>
      ),
    )}
  </>
)

/** Subtitle line: bold white on a translucent ink box, readable over any footage. */
export const CaptionBox = ({ children }: { children: ReactNode }) => (
  <span
    style={{
      fontFamily: font.sans,
      fontWeight: 800,
      fontSize: 58,
      // Tall enough that a wrapped line's box doesn't cover the line above (¿, ñ, descenders).
      lineHeight: 1.65,
      color: color.white,
      backgroundColor: 'rgba(20, 32, 27, 0.72)',
      padding: '10px 22px',
      borderRadius: 18,
      boxDecorationBreak: 'clone',
      WebkitBoxDecorationBreak: 'clone',
    }}
  >
    {children}
  </span>
)

/** "kuulis." in the app's wordmark style: Plus Jakarta Sans 800, tight tracking, yellow dot. */
export const Wordmark = ({ size, dotStyle }: { size: number; dotStyle?: CSSProperties }) => (
  <span style={{ fontFamily: font.sans, fontWeight: 800, fontSize: size, letterSpacing: '-0.03em', lineHeight: 1, color: color.white }}>
    kuulis<span style={{ color: color.accent, display: 'inline-block', ...dotStyle }}>.</span>
  </span>
)
