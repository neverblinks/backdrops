import { expect, test } from 'claude-code/testing'

import { parseRequest } from '../hooks/register'

test('arguments mean what /magenta-hour says they mean', async () => {
  expect(parseRequest('')).toEqual({ kind: 'on' })
  expect(parseRequest('off')).toEqual({ kind: 'off' })
  expect(parseRequest('music')).toEqual({ kind: 'music' })
  expect(parseRequest('Music On')).toEqual({ kind: 'music', on: true })
  expect(parseRequest('music off')).toEqual({ kind: 'music', on: false })
  expect(parseRequest('neon')).toEqual({ kind: 'unknown', text: 'neon' })
})

test('the backdrop draws one picture', async ($) => {
  const ui = await $.ui.mount({
    plugin: 'magenta-hour',
    component: 'Backdrop',
    requestId: 'bd',
    props: { scene: 'magenta-hour', plugin: 'magenta-hour', glass: { blur: 0, opacity: 0 } },
    surface: 'desktop',
  })
  expect((await ui.findAll({ type: 'Svg' })).length).toBe(1)
  await ui.unmount()
})
