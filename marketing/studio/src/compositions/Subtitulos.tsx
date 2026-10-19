import { AbsoluteFill, Sequence, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion'
import { CIERRE_S, color, font, safe } from '../brand'
import { Background, CaptionBox, Highlighted, PosterHeadline, Zone } from '../components/brand'
import { chunkCaptions, keepTogether } from '../lib/text'
import type { SubtitulosProps } from '../schema'
import { Cierre } from './Cierre'

/**
 * The workhorse: any footage (Higgsfield, Buzzy, a screen recording) or a brand color, with the hook on
 * screen from frame 1, on-screen figures in the top third, burned-in subtitles and the brand close card.
 */
export const Subtitulos = (props: SubtitulosProps) => {
  const { fps } = useVideoConfig()
  const cues = props.subtitulos.length > 0 ? props.subtitulos : props.voz ? chunkCaptions(props.voz, 0, props.duracionS) : []
  const at = (s: number) => Math.round(s * fps)
  return (
    <AbsoluteFill style={{ backgroundColor: color.night }}>
      <Sequence durationInFrames={at(props.duracionS)} name="Pieza">
        <Background fondo={props.fondo} />
        <Sequence durationInFrames={at(props.gancho.duracionS)} name="Gancho">
          <Hook text={props.gancho.texto} />
        </Sequence>
        {props.textos.map((t, i) => (
          <Sequence key={i} from={at(t.desdeS)} durationInFrames={at(t.hastaS - t.desdeS)} name={`Texto ${i + 1}`}>
            <Callout text={t.texto} highlight={t.destacado} />
          </Sequence>
        ))}
        {cues.map((c, i) => (
          <Sequence key={i} from={at(c.desdeS)} durationInFrames={Math.max(1, at(c.hastaS - c.desdeS))} name={`Subtítulo ${i + 1}`}>
            <Zone style={{ top: 1150, bottom: safe.bottom, left: safe.left, right: safe.right, alignItems: 'center' }}>
              <div style={{ width: '100%', textAlign: 'center' }}>
                <CaptionBox>{keepTogether(c.texto)}</CaptionBox>
              </div>
            </Zone>
          </Sequence>
        ))}
      </Sequence>
      {props.cierre && (
        <Sequence from={at(props.duracionS)} durationInFrames={at(CIERRE_S)} name="Cierre">
          <Cierre cta="Android · link en la bio" />
        </Sequence>
      )}
    </AbsoluteFill>
  )
}

const HOOK_START_SCALE = 1.06
const HOOK_EXTRA_RIGHT = Math.ceil((1080 - safe.left - safe.right) * (1 - 1 / HOOK_START_SCALE))

/** The hook sits in the safe zone's upper third, already visible on frame 0, with a small push-in. */
const Hook = ({ text }: { text: string }) => {
  const frame = useCurrentFrame()
  const scale = interpolate(frame, [0, 20], [HOOK_START_SCALE, 1], { extrapolateRight: 'clamp' })
  return (
    // The push-in starts 6 % larger: narrow the box so the first frame still fits the safe zone.
    <Zone style={{ top: 250, left: safe.left, right: safe.right + HOOK_EXTRA_RIGHT, height: 520 }}>
      <PosterHeadline
        text={text}
        size={128}
        style={{ transform: `scale(${scale})`, transformOrigin: 'left top', textShadow: '0 4px 24px rgba(7,18,14,0.55)' }}
      />
    </Zone>
  )
}

const Callout = ({ text, highlight }: { text: string; highlight?: string }) => {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const pop = spring({ frame, fps, config: { damping: 14 } })
  return (
    <Zone style={{ top: 300, left: safe.left, right: safe.right, height: 400, justifyContent: 'flex-start' }}>
      <div
        style={{
          alignSelf: 'flex-start',
          fontFamily: font.sans,
          fontWeight: 800,
          fontSize: 76,
          lineHeight: 1.1,
          color: color.white,
          backgroundColor: 'rgba(20, 32, 27, 0.78)',
          padding: '18px 28px',
          borderRadius: 24,
          transform: `scale(${0.9 + pop * 0.1})`,
          opacity: pop,
          transformOrigin: 'left top',
        }}
      >
        <Highlighted text={text} highlight={highlight} />
      </div>
    </Zone>
  )
}
