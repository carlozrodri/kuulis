import { AbsoluteFill } from 'remotion'
import { safe } from '../brand'
import { Background, PosterHeadline, Wordmark, Zone } from '../components/brand'
import type { PortadaProps } from '../schema'

/**
 * Cover image. On Instagram the grid crops a vertical cover to its central 4:5 (1080×1350), so the
 * headline stays inside that band on the vertical format; it also keeps clear of TikTok's buttons
 * (right) and caption (bottom), so it ends at the safe zone, not at the bottom of the 4:5 band.
 */
export const Portada = ({ formato, fondo, titulo }: PortadaProps) => (
  <AbsoluteFill>
    <Background fondo={fondo} dim={fondo.tipo === 'color' ? 0 : 0.3} />
    <Zone
      style={{
        top: formato === 'vertical' ? 285 + 80 : 80,
        left: safe.left + 20,
        right: formato === 'vertical' ? safe.right : safe.left + 20,
        height: formato === 'vertical' ? 1920 - (285 + 80) - safe.bottom : 1350 - 160,
        justifyContent: 'space-between',
      }}
    >
      <PosterHeadline text={titulo} size={formato === 'vertical' ? 150 : 170} style={{ textShadow: '0 4px 28px rgba(7,18,14,0.55)' }} />
      <Wordmark size={64} />
    </Zone>
  </AbsoluteFill>
)
