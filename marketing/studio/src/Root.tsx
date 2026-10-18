import { Composition, Still } from 'remotion'
import { CIERRE_S, FPS, formats } from './brand'
import { Cierre } from './compositions/Cierre'
import { Dato } from './compositions/Dato'
import { Lamina } from './compositions/Lamina'
import { Portada } from './compositions/Portada'
import { Subtitulos } from './compositions/Subtitulos'
import './fonts'
import { datoDefault, laminaDefault, portadaDefault, subtitulosDefault } from './defaults'
import { cierreProps, datoProps, laminaProps, portadaProps, subtitulosProps } from './schema'

const vertical = formats.vertical

const seconds = (s: number) => Math.round(s * FPS)

export const Root = () => (
  <>
    <Composition
      id="Subtitulos"
      component={Subtitulos}
      schema={subtitulosProps}
      defaultProps={subtitulosDefault}
      fps={FPS}
      {...vertical}
      durationInFrames={seconds(10)}
      calculateMetadata={({ props }) => {
        const p = subtitulosProps.parse(props)
        return { durationInFrames: seconds(p.duracionS + (p.cierre ? CIERRE_S : 0)) }
      }}
    />
    <Composition
      id="Dato"
      component={Dato}
      schema={datoProps}
      defaultProps={datoDefault}
      fps={FPS}
      {...vertical}
      durationInFrames={seconds(10)}
      calculateMetadata={({ props }) => {
        const p = datoProps.parse(props)
        const steps = p.pasos.reduce((sum, step) => sum + seconds(step.duracionS), 0)
        return { durationInFrames: steps + (p.cierre ? seconds(CIERRE_S) : 0) }
      }}
    />
    <Composition
      id="Cierre"
      component={Cierre}
      schema={cierreProps}
      defaultProps={cierreProps.parse({})}
      fps={FPS}
      {...vertical}
      durationInFrames={seconds(CIERRE_S)}
    />
    <Still
      id="Lamina"
      component={Lamina}
      schema={laminaProps}
      defaultProps={laminaDefault}
      {...formats.feed}
      calculateMetadata={({ props }) => formats[props.formato]}
    />
    <Still
      id="Portada"
      component={Portada}
      schema={portadaProps}
      defaultProps={portadaDefault}
      {...vertical}
      calculateMetadata={({ props }) => formats[props.formato]}
    />
  </>
)
