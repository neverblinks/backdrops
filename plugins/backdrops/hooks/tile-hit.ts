import type { ClientModule } from 'claude-code'

/**
 * One preview's click layer, laid over its preview and name. A click (press and release) tries the tile. On the
 * first and last tile, resting the pointer at the strip's outer edge for a third of a second turns the page
 * that way (one finger, no click); the timer runs only while the pointer is in that edge. Once a click has
 * given a tile the focus, left and right arrows turn the page too.
 *
 * Entering and leaving the tile tell the card, which frames the picture under the pointer in its colours. The region is as tall as what it draws, so it draws its rows out in full.
 */
type HitProps = { id: string; rows: number; edge: number; pages: number }
type HitState = { listening: true }

/** The edge zone, as a share of the tile's width, and the rest before the page turns, then the repeat. */
const EDGE = 0.3
const REST_MS = 330
const REPEAT_MS = 800

const TileHit: ClientModule<HitProps, HitState> = (props, surface) => {
  if (surface.state === undefined) {
    let pressed = false
    let stopTimer: (() => void) | undefined
    const stopEdge = () => {
      stopTimer?.()
      stopTimer = undefined
    }
    const startEdge = () => {
      if (stopTimer !== undefined) {
        return
      }
      let waited = 0
      let turned = false
      stopTimer = surface.every(110, () => {
        waited += 110
        if ((!turned && waited >= REST_MS) || (turned && waited >= REPEAT_MS)) {
          surface.post({ kind: 'page', by: props.edge })
          waited = 0
          turned = true
        }
      })
    }
    surface.onPointer(event => {
      if (event.type === 'enter') {
        surface.post({ kind: 'hover', id: props.id })
      }
      if (event.type === 'leave') {
        pressed = false
        stopEdge()
        surface.post({ kind: 'hover' })   // no id: the pointer left
        return
      }
      if (event.type === 'down' && event.button === 'left') {
        pressed = true
        stopEdge()
        return
      }
      if (event.type === 'up') {
        if (pressed) {
          surface.post({ kind: 'pick', id: props.id })
        }
        pressed = false
        return
      }
      const x = event.fine?.x ?? event.x + 0.5
      const share = x / Math.max(1, surface.columns)
      const inEdge = props.pages > 1 && ((props.edge < 0 && share <= EDGE) || (props.edge > 0 && share >= 1 - EDGE))
      if (inEdge && !pressed) {
        startEdge()
      } else {
        stopEdge()
      }
    })
    surface.onKey(event => {
      if (event.key === 'return') {
        surface.post({ kind: 'keep' })
      } else if (event.key === 'right') {
        surface.post({ kind: 'page', by: 1 })
      } else if (event.key === 'left') {
        surface.post({ kind: 'page', by: -1 })
      }
    })
    surface.setState({ listening: true })
  }
  const { Box, Text } = surface.elements
  const lines = Array.from({ length: props.rows }, () => Text({ children: ' ' }))

  return Box({ flexDirection: 'column', width: '100%', height: props.rows, children: lines })
}

export default TileHit
