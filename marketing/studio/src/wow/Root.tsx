import { Composition } from 'remotion'
import { FPS, formats } from '../brand'
import '../fonts'
import { Wow, type WowProps } from './Wow'

const defaults: WowProps = { escenas: [{ tipo: 'slam', texto: 'KUULIS.', from: 0, dur: 60 }] }

export const WowRoot = () => (
  <Composition
    id="Wow"
    component={Wow}
    fps={FPS}
    {...formats.vertical}
    durationInFrames={60}
    defaultProps={defaults}
    calculateMetadata={({ props }) => {
      const last = props.escenas[props.escenas.length - 1]
      return { durationInFrames: last.from + last.dur }
    }}
  />
)
