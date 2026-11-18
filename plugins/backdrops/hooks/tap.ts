import type { ClientModule } from 'claude-code'

/**
 * An invisible click target laid over text the card draws itself (the page arrows, the make-default hint).
 * A press and release on it posts `message` to the card. One row tall: a region is as tall as what it draws.
 */
type TapProps = { message: { kind: 'page'; by: number } | { kind: 'keep' } }
type TapState = { listening: true }

const Tap: ClientModule<TapProps, TapState> = (props, surface) => {
  if (surface.state === undefined) {
    let pressed = false
    surface.onPointer(event => {
      if (event.type === 'down' && event.button === 'left') {
        pressed = true
      } else if (event.type === 'up') {
        if (pressed) {
          surface.post(props.message)
        }
        pressed = false
      } else if (event.type === 'leave') {
        pressed = false
      }
    })
    surface.setState({ listening: true })
  }
  const { Text } = surface.elements
  return Text({ children: ' ' })
}

export default Tap
