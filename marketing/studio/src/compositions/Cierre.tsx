import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion'
import { color, font } from '../brand'
import { Wordmark } from '../components/brand'
import type { CierreProps } from '../schema'

/** Brand close card: green field, the wordmark, and its yellow dot landing like the end of a route. */
export const Cierre = ({ cta }: CierreProps) => {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const land = spring({ frame, fps, config: { damping: 11, stiffness: 160 } })
  const dotY = interpolate(land, [0, 1], [-260, 0])
  const fade = interpolate(frame, [0, 6], [0, 1], { extrapolateRight: 'clamp' })
  const ctaIn = interpolate(frame, [8, 16], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
  return (
    <AbsoluteFill style={{ backgroundColor: color.primary, alignItems: 'center', justifyContent: 'center', opacity: fade }}>
      <Wordmark size={210} dotStyle={{ transform: `translateY(${dotY}px)` }} />
      <div
        style={{
          marginTop: 48,
          fontFamily: font.sans,
          fontWeight: 700,
          fontSize: 46,
          color: color.white,
          opacity: ctaIn,
        }}
      >
        {cta}
      </div>
    </AbsoluteFill>
  )
}
