import { AbsoluteFill } from 'remotion'
import { color, font } from '../brand'
import { Background, Highlighted, PosterHeadline, Wordmark } from '../components/brand'
import type { LaminaProps } from '../schema'

/** One carousel slide (F-CARRUSEL). The text is always set by the template, never by the image model. */
export const Lamina = ({ formato, estilo, imagen, titulo, texto, destacado, indice, total }: LaminaProps) => {
  const pad = 80
  const fondoColor = estilo === 'verde' ? color.primary : color.night
  return (
    <AbsoluteFill style={{ backgroundColor: fondoColor }}>
      {estilo === 'foto' && imagen && <Background fondo={{ tipo: 'imagen', src: imagen }} dim={0.35} />}
      <AbsoluteFill
        style={{
          padding: pad,
          paddingTop: formato === 'vertical' ? 260 : pad,
          paddingBottom: formato === 'vertical' ? 520 : 170,
          justifyContent: 'center',
        }}
      >
        <PosterHeadline text={titulo} size={formato === 'vertical' ? 176 : 164} style={{ textShadow: '0 4px 24px rgba(7,18,14,0.5)' }} />
        {texto && (
          <div
            style={{
              marginTop: 40,
              fontFamily: font.sans,
              fontWeight: 700,
              fontSize: 64,
              lineHeight: 1.25,
              color: color.white,
              maxWidth: 880,
              textWrap: 'pretty',
            }}
          >
            <Highlighted text={texto} highlight={destacado} />
          </div>
        )}
      </AbsoluteFill>
      <AbsoluteFill
        style={{
          top: 'auto',
          height: formato === 'vertical' ? 520 : 150,
          padding: `0 ${pad}px`,
          flexDirection: 'row',
          alignItems: formato === 'vertical' ? 'flex-start' : 'center',
          justifyContent: 'space-between',
        }}
      >
        <Wordmark size={52} />
        <span style={{ fontFamily: font.sans, fontWeight: 700, fontSize: 36, color: 'rgba(255,255,255,0.8)' }}>
          {indice}/{total}
        </span>
      </AbsoluteFill>
    </AbsoluteFill>
  )
}
