import { expect, mock, test } from 'claude-code/testing'

import { parseLook } from '../hooks/register'
import { PHOTOS } from '../hooks/photos'
import { THEMES } from '../hooks/themes'

test('arguments mean what /backdrops list says they mean', async () => {
  expect(parseLook('')).toEqual({ kind: 'card' })
  expect(parseLook('list')).toEqual({ kind: 'list' })
  expect(parseLook('off')).toEqual({ kind: 'off', forSession: false })
  expect(parseLook('off session')).toEqual({ kind: 'off', forSession: true })
  expect(parseLook('bogus')).toEqual({ kind: 'unknown', name: 'bogus' })
  const night = parseLook('after hours session')
  expect(night.kind === 'apply' && night.theme.id).toBe('after-hours')
  expect(night.kind === 'apply' && night.forSession).toBe(true)
  // one Reaching in the picker: the classic version lives only in the single reaching plugin
  expect(parseLook('Reaching Classic')).toEqual({ kind: 'unknown', name: 'Reaching Classic' })
  expect(parseLook('music on')).toEqual({ kind: 'music', setting: 'on' })
})

test('every theme has a preview and a scene under the limits', async () => {
  for (const theme of THEMES) {
    expect(PHOTOS[theme.id]?.startsWith('data:image/webp;base64,')).toBe(true)
    expect(PHOTOS[theme.id]?.length ?? 0).toBeLessThan(16001)
    expect(theme.scene.length).toBeLessThan(131073)
  }
})

const CARD_ID = 'backdrops-card-1000'   // the mocked clock says 1000
const FIRST_PAGE = ['reaching', 'magenta-hour', 'after-hours', 'crossing-hour', 'promenade', 'coast-road', 'ocean-road']

type Engine = Parameters<Extract<Parameters<typeof test>[1], (...args: never[]) => unknown>>[0]
type On = Parameters<Extract<Parameters<typeof test>[1], (...args: never[]) => unknown>>[1]

const run = (args: string) => ({
  command: 'backdrops',
  args,
  origin: { kind: 'composer' as const },
  presentation: { isFullscreen: false, columns: 100 },
})

function stub(on: On) {
  const clock = mock.clock(on, { now: 1000 })
  mock.store(on, { default: 'reaching' })
  mock.env(on, {})
  on('command.register', () => ({ value: { command: 'backdrops' } }))
  on('ui.place', () => ({ value: { isPlaced: true, requestId: CARD_ID } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('theme.set', () => ({ value: { isDrawn: true, requestId: 'r1' } }))
  on('theme.clear', () => ({ value: { isDrawn: true, requestId: 'r2' } }))
  return clock
}

/** Opens the card at `columns` wide (absent: the surface hasn't measured) and lays out its click layers. */
async function open($: Engine, columns?: number) {
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  await $.command.run(run(''))
  const ui = await $.ui.mount({ plugin: 'backdrops', surface: 'desktop', component: 'Placed', requestId: CARD_ID,
    props: { plugin: 'backdrops', id: CARD_ID }, ...(columns === undefined ? {} : { viewport: { columns, rows: 40 } }) })
  await layOut(ui, FIRST_PAGE.slice(0, columns !== undefined && columns < 80 ? 4 : 7))
  return ui
}

/** Each preview's click layer is keyed by its theme, so a new page brings new layers to lay out. */
async function layOut(ui: Awaited<ReturnType<typeof open>>, ids: readonly string[]) {
  for (const id of ids) {
    await ui.resize({ columns: 10, rows: 5, in: `hit-${id}` })
  }
}

async function click(ui: Awaited<ReturnType<typeof open>>, target: string) {
  await ui.pointer({ type: 'down', x: 1, y: 0, button: 'left', in: target })
  await ui.pointer({ type: 'up', x: 1, y: 0, button: 'left', in: target })
}

test('seven a page: a click tries a theme, Enter makes it the default and says so', async ($, on) => {
  const clock = stub(on)
  const ui = await open($)
  for (const id of FIRST_PAGE) {
    expect(await ui.find({ key: `tile-${id}` })).toBeDefined()
  }
  expect(await ui.find({ key: 'tile-fractal-glass' })).toBeUndefined()
  expect(await ui.find({ type: 'Text', text: /make default/ })).toBeUndefined()

  // a click on the third preview (After Hours) tries it in this session
  await click(ui, 'hit-after-hours')
  expect(await ui.find({ type: 'Text', text: /this session only/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /make default/ })).toBeDefined()

  // Enter makes it the default; the card says so for a moment, then closes
  await ui.key({ key: 'return', in: 'hit-after-hours' })
  expect(await ui.find({ type: 'Text', text: /After Hours is your default/ })).toBeDefined()
  await clock.advance(1600)
  expect(await ui.find({ key: 'close' })).toBeUndefined()
  const listed = await $.command.run(run('list'))
  expect(JSON.stringify(listed)).toMatch(/after-hours: After Hours[^\\]*default/)
  await ui.unmount()
})

test('a click on "make default" keeps the theme tried', async ($, on) => {
  const clock = stub(on)
  const ui = await open($)
  await click(ui, 'hit-promenade')
  await click(ui, 'tap-keep')
  await clock.advance(1600)
  expect(await ui.find({ key: 'close' })).toBeUndefined()
  const listed = await $.command.run(run('list'))
  expect(JSON.stringify(listed)).toMatch(/promenade: Promenade[^\\]*default/)
  await ui.unmount()
})

test('two pages: turned by the arrows, the arrow keys and resting at an edge', async ($, on) => {
  stub(on)
  const ui = await open($)
  const page = async () => ((await ui.find({ key: 'tile-reaching' })) !== undefined ? 1 : 2)
  expect(await page()).toBe(1)
  // no back arrow on the first page
  expect(await ui.find({ key: 'tap-back' })).toBeUndefined()
  await click(ui, 'tap-on')
  expect(await page()).toBe(2)
  await click(ui, 'tap-back')
  expect(await page()).toBe(1)
  await ui.key({ key: 'right', in: 'hit-reaching' })
  expect(await page()).toBe(2)
  await layOut(ui, ['fractal-glass', 'ember', 'off'])
  await ui.key({ key: 'left', in: 'hit-ember' })
  expect(await page()).toBe(1)
  // resting the pointer at the last preview's outer edge turns the page
  await layOut(ui, FIRST_PAGE)
  await ui.pointer({ type: 'move', x: 9, y: 2, in: 'hit-ocean-road' })
  await ui.advance(400)
  expect(await page()).toBe(2)
  await ui.unmount()
})

test('None is the last preview, and Enter after it stores no backdrop as the default', async ($, on) => {
  const clock = stub(on)
  const ui = await open($)
  await ui.key({ key: 'right', in: 'hit-reaching' })
  // page two: Fractal Glass, Ember, None
  expect(await ui.find({ key: 'tile-off' })).toBeDefined()
  await layOut(ui, ['fractal-glass', 'ember', 'off'])
  await click(ui, 'hit-off')
  await ui.key({ key: 'return', in: 'hit-off' })
  expect(await ui.find({ type: 'Text', text: /No backdrop is your default/ })).toBeDefined()
  await clock.advance(1600)
  expect(await ui.find({ key: 'close' })).toBeUndefined()
  await ui.unmount()
})

test('a narrow card keeps the action and drops the status', async ($, on) => {
  stub(on)
  const ui = await open($, 46)
  await click(ui, 'hit-magenta-hour')
  expect(await ui.find({ type: 'Text', text: /make default/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /this session only/ })).toBeUndefined()
  await ui.unmount()
})

test('the terminal gets buttons: one per theme and None, and Make default once one is tried', async ($, on) => {
  stub(on)
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  await $.command.run(run(''))
  const ui = await $.ui.mount({ plugin: 'backdrops', surface: 'terminal', component: 'Placed', requestId: CARD_ID,
    props: { plugin: 'backdrops', id: CARD_ID } })
  expect(await ui.find({ key: 'try-off' })).toBeDefined()
  expect(await ui.find({ key: 'keep-button' })).toBeUndefined()
  await ui.press({ key: 'try-ember' })
  expect(await ui.find({ key: 'keep-button' })).toBeDefined()
  await ui.unmount()
})

test('every app surface accepts the card', async ($, on) => {
  stub(on)
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  await $.command.run(run(''))
  for (const surface of ['desktop', 'vscode', 'mobile', 'terminal'] as const) {
    const ui = await $.ui.mount({ plugin: 'backdrops', surface, component: 'Placed', requestId: CARD_ID,
      props: { plugin: 'backdrops', id: CARD_ID } })
    // a tree a surface refuses draws nothing: the close button is the card's one constant
    expect(await ui.find({ key: 'close' })).toBeDefined()
    await ui.unmount()
  }
})

test('the backdrop draws one picture for each theme', async ($) => {
  for (const theme of THEMES) {
    const ui = await $.ui.mount({
      plugin: 'backdrops',
      component: 'Backdrop',
      requestId: `bd-${theme.id}`,
      props: { scene: theme.id, plugin: 'backdrops', glass: { blur: 0, opacity: 0 } },
      surface: 'desktop',
    })
    expect((await ui.findAll({ type: 'Svg' })).length).toBe(1)
    await ui.unmount()
  }
})

test('the previews keep one fixed order: Reaching first, whatever the default', async () => {
  // the default is marked on its preview, not moved, so every preview stays where it was last time
  expect(THEMES.map(theme => theme.id)).toEqual(['reaching', 'magenta-hour', 'after-hours', 'crossing-hour', 'promenade', 'coast-road', 'ocean-road', 'fractal-glass', 'ember'])
})
