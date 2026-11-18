import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import { PAINT_PROBLEMS, THEMES, themeNamed } from './themes'
import type { PickerTheme } from './themes'
import type { MusicView, PickerSession } from '../types'
import { PHOTOS } from './photos'

/**
 * /backdrops: every backdrop in this collection behind one command, with a preview of each.
 *
 *   /backdrops                   a card: one row of previews and None; a click tries one here
 *   /backdrops list              the themes by name
 *   /backdrops <name>            make it the default for every session
 *   /backdrops <name> session    this session only
 *   /backdrops off [session]     no theme
 *   /backdrops music on|off|10-100   music for the theme showing (off until turned on)
 *   /backdrops music add [file]      add a track to the theme showing (no file: opens its folder)
 *
 * The default lives in `$.store` (it outlasts sessions); a session's own pick
 * and the card's place live in `$.state` (they end with the session).
 */
const PLUGIN = 'backdrops'
const COMMAND = 'backdrops'
const CARD = 'backdrops-card'  // each /backdrops places `backdrops-card-<n>`: a new row at the transcript's end
const DEFAULT_KEY = 'default'
const FIRST_DEFAULT = 'reaching'

/** The theme this session shows (module memory; set where a theme is shown). */
let showing: PickerTheme | undefined

const session = atom({ plugin: 'backdrops', key: 'session' } as const, { cardInBand: false, cardAway: true }, {
  shape: 'session-2',
})

// >>> music: pasted from shared/music.snippet.ts by tools/build.py (edit that file)
/**
 * Background music for a theme. Pasted into each plugin's register module by tools/build.py
 * (the engine wants every use of $ inside the module that registers the hooks): edit shared/music.snippet.ts.
 *
 * A theme plays the person's own tracks when there are any in
 *   ~/.config/backdrops/music/<theme id>/      (e.g. music/reaching/, music/after-hours/)
 * in name order, else its built-in tracks (only Magenta Hour has some). Tracks play one after
 * another while the theme shows in a desktop window, and only one session plays at a time.
 * Each own track must be under 4 MB: the app reads a file whole, up to 4 MiB.
 */
type Track = { kind: 'asset'; path: string } | { kind: 'file'; path: string; mime: string }

const MIMES: Readonly<Record<string, string>> = {
  m4a: 'audio/mp4',
  mp4: 'audio/mp4',
  aac: 'audio/aac',
  mp3: 'audio/mpeg',
  wav: 'audio/wav',
  aif: 'audio/aiff',
  aiff: 'audio/aiff',
  caf: 'audio/x-caf',
}
const MAX_BYTES = 4 * 1024 * 1024
const OWNER_KEY = 'music-owner'
const NEXT_KEY = 'music-next'
const ME = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`   // this session's tag, not a secret

/** Where a theme's own tracks go, or undefined when HOME is unknown. */
async function musicFolder($: EngineInterface, themeId: string): Promise<string | undefined> {
  const home = await $.env.get('HOME')
  return home === undefined || home === '' ? undefined : `${home}/.config/backdrops/music/${themeId}`
}

/** The person's own tracks for a theme if the folder has any playable ones, else the built-in ones. */
async function tracksFor($: EngineInterface, themeId: string, builtIn: readonly string[]): Promise<Track[]> {
  const folder = await musicFolder($, themeId)
  if (folder !== undefined) {
    try {
      const own = (await $.fs.list(folder))
        .filter(entry => entry.kind === 'file' && entry.size > 0 && entry.size <= MAX_BYTES)
        .map(entry => ({ name: entry.name, mime: MIMES[entry.name.split('.').pop()?.toLowerCase() ?? ''] }))
        .filter((entry): entry is { name: string; mime: string } => entry.mime !== undefined)
        .sort((a, b) => a.name.localeCompare(b.name))
      if (own.length > 0) {
        return own.map(entry => ({ kind: 'file', path: `${folder}/${entry.name}`, mime: entry.mime }))
      }
    } catch {
      // no folder: the built-in tracks
    }
  }
  return builtIn.map(path => ({ kind: 'asset', path }))
}

/** Makes the theme's music folder and opens it in Finder, so tracks can be dragged in. */
async function openMusicFolder($: EngineInterface, themeId: string): Promise<string> {
  const folder = await musicFolder($, themeId)
  if (folder === undefined) {
    return 'Your home folder is unknown, so there is no music folder to open.'
  }
  await $.process.run(['mkdir', '-p', folder])
  const opened = await $.process.run(['open', folder])
  return opened.exitCode === 0
    ? `Opened ${folder} in Finder: drag your tracks in (m4a, mp3, wav, aiff; under 4 MB each).`
    : `Your music folder is ${folder}: put your tracks there (m4a, mp3, wav, aiff; under 4 MB each).`
}

/** Copies one audio file into the theme's music folder. Returns what happened, in a line. */
async function addTrack($: EngineInterface, themeId: string, path: string): Promise<string> {
  const folder = await musicFolder($, themeId)
  const source = path.trim().replace(/^['"]|['"]$/g, '').replace(/\\ /g, ' ')
  const name = source.split('/').pop() ?? ''
  const extension = name.split('.').pop()?.toLowerCase() ?? ''
  if (folder === undefined) {
    return 'Your home folder is unknown, so there is no music folder to copy into.'
  }
  if (MIMES[extension] === undefined) {
    return `"${name}" isn't a track this can play: use m4a, mp3, aac, wav or aiff.`
  }
  const size = await $.fs.stat(source).then(stat => stat.size).catch(() => -1)
  if (size < 0) {
    return `Couldn't find ${source}.`
  }
  if (size > MAX_BYTES) {
    return `${name} is ${(size / 1048576).toFixed(1)} MB; tracks must be under 4 MB (compress it, or use a shorter one).`
  }
  await $.process.run(['mkdir', '-p', folder])
  const copied = await $.process.run(['cp', source, `${folder}/${name}`])
  return copied.exitCode === 0 ? `Added ${name} to ${folder}.` : `Couldn't copy ${name}: ${copied.stderr.trim()}`
}

async function playOne($: EngineInterface, track: Track, gain: number, signal: AbortSignal): Promise<void> {
  if (track.kind === 'asset') {
    await $.audio.play({ asset: track.path }, { gain, signal })
    return
  }
  const { base64 } = await $.fs.read(track.path, { as: 'bytes' })
  await $.audio.play({ base64, mime: track.mime }, { gain, signal })
}

/** The player: plays a list round and round until told otherwise (one per plugin). */
let player: { key: string; stop: AbortController; check: { cancel: () => void } } | undefined

function stopPlayer(): void {
  player?.check.cancel()
  player?.stop.abort()
  player = undefined
}

async function playlist($: EngineInterface, tracks: readonly Track[], gain: number, abort: AbortController): Promise<void> {
  const held = await $.store.get(NEXT_KEY)
  let next = typeof held === 'number' && Number.isInteger(held) ? held : 0
  while (!abort.signal.aborted) {
    const i = ((next % tracks.length) + tracks.length) % tracks.length
    const track = tracks[i] ?? tracks[0]
    if (track === undefined) {
      return
    }
    const began = Date.now()
    await playOne($, track, gain, abort.signal)
    if (abort.signal.aborted) {
      return   // stopped: this track plays again next time, rather than skipping ahead
    }
    if (Date.now() - began < 2000) {
      throw new Error(`${track.path} ended at once`)   // didn't play: stop rather than spin
    }
    next = i + 1
    await $.store.set(NEXT_KEY, next % tracks.length)
  }
}

/** Plays `tracks` at `gain` (0-1) if `wanted` and a desktop window is attached; else stops. */
async function syncPlayer($: EngineInterface, wanted: boolean, tracks: readonly Track[], gain: number): Promise<void> {
  if (!wanted || tracks.length === 0 || !(await $.session.surfaces()).includes('desktop')) {
    stopPlayer()
    return
  }
  const key = `${gain}|${tracks.map(track => track.path).join('|')}`
  if (player?.key === key) {
    return
  }
  stopPlayer()   // a new list or volume starts the current track again
  const abort = new AbortController()
  await $.store.set(OWNER_KEY, ME)
  // Another session took the music over: this one goes quiet.
  const check = $.clock.every(2000, () => {
    void $.store.get(OWNER_KEY).then(owner => {
      if (owner !== ME && player?.stop === abort) {
        stopPlayer()
      }
    })
  })
  player = { key, stop: abort, check }
  // Never awaited: it runs until stopped.
  void playlist($, tracks, gain, abort).catch(() => {
    if (player?.stop === abort) {
      stopPlayer()
    }
  })
}
// <<< music

// ------------------------------------------------------------------ background music
// Every theme can have music: the person's own tracks in ~/.config/backdrops/music/<theme id>/, else its
// built-in ones (only Magenta Hour has some). One driver, syncMusic, decides from scratch each time
// something changes: the theme shown, the music setting (on/off, volume), a desktop window joining or
// leaving, the session ending. The player itself (one session at a time) is the music block above.
const BUILT_IN: Readonly<Record<string, readonly string[]>> = {
  // original, synthesised in themes/magenta-hour/make-music.py: nothing sampled
  'magenta-hour': ['music/magenta-hour.m4a', 'music/magenta-hour-2.m4a', 'music/magenta-hour-3.m4a'],
}
const MUSIC_KEY = 'music'               // $.store: 'on' plays it; off until the person turns it on
const VOLUME_KEY = 'music-volume'       // $.store: 10-100, percent of the files' level
const VOLUMES = [10, 25, 50, 75, 100] as const
const DEFAULT_VOLUME = 25               // a quiet bed under work

async function musicSetting($: EngineInterface): Promise<MusicView> {
  const stored = await $.store.get(VOLUME_KEY)
  const volume = typeof stored === 'number' && stored >= 10 && stored <= 100 ? Math.round(stored) : DEFAULT_VOLUME

  return { on: (await $.store.get(MUSIC_KEY)) === 'on', volume }
}

async function syncMusic($: EngineInterface): Promise<void> {
  const setting = await musicSetting($)
  const tracks = showing === undefined ? [] : await tracksFor($, showing.id, BUILT_IN[showing.id] ?? [])
  await syncPlayer($, setting.on, tracks, setting.volume / 100)
}

/** Stores a music change (on/off, volume) for every session and acts on it here at once. */
async function changeMusic($: EngineInterface, change: { on?: boolean; volume?: number }): Promise<void> {
  if (change.on !== undefined) {
    await $.store.set(MUSIC_KEY, change.on ? 'on' : 'off')
  }
  if (change.volume !== undefined) {
    await $.store.set(VOLUME_KEY, Math.min(100, Math.max(10, Math.round(change.volume))))
  }
  await syncMusic($)
}

function stepVolume(volume: number, direction: 1 | -1): number {
  const louder = VOLUMES.find(v => v > volume)
  const quieter = [...VOLUMES].reverse().find(v => v < volume)

  return (direction === 1 ? louder : quieter) ?? volume
}

/** What a /backdrops argument asks for. Exported for the tests. */
export type LookRequest =
  | { kind: 'card' }
  | { kind: 'list' }
  | { kind: 'off'; forSession: boolean }
  | { kind: 'apply'; theme: PickerTheme; forSession: boolean }
  | { kind: 'music'; setting?: 'on' | 'off'; volume?: number }
  | { kind: 'music-add'; path?: string }
  | { kind: 'unknown'; name: string }

export function parseLook(args: string): LookRequest {
  const add = args.trim().match(/^music\s+add(?:\s+(.+))?$/i)
  if (add !== null) {
    return add[1] === undefined ? { kind: 'music-add' } : { kind: 'music-add', path: add[1] }
  }
  const words = args.trim().split(/\s+/).filter(word => word !== '')
  const first = words[0]?.toLowerCase()
  if (first === 'music' && words.length <= 2) {
    const setting = words[1]?.toLowerCase()
    if (setting === undefined) {
      return { kind: 'music' }
    }
    if (setting === 'on' || setting === 'off') {
      return { kind: 'music', setting }
    }
    const volume = Number(setting.replace(/%$/, ''))
    if (Number.isInteger(volume) && volume >= 10 && volume <= 100) {
      return { kind: 'music', volume }
    }
  }
  const forSession = words.length > 1 && words.at(-1)?.toLowerCase() === 'session'
  const name = (forSession ? words.slice(0, -1) : words).join(' ')

  if (name === '') {
    return { kind: 'card' }
  }
  if (name.toLowerCase() === 'list') {
    return { kind: 'list' }
  }
  if (name.toLowerCase() === 'off') {
    return { kind: 'off', forSession }
  }
  const theme = themeNamed(name)

  return theme === undefined ? { kind: 'unknown', name } : { kind: 'apply', theme, forSession }
}

async function defaultChoice($: EngineInterface): Promise<string> {
  const stored = await $.store.get(DEFAULT_KEY)

  return typeof stored === 'string' ? stored : FIRST_DEFAULT
}

/** The theme this session shows: its own pick, else the default. 'off' for none. */
async function effectiveChoice($: EngineInterface, now?: PickerSession): Promise<string> {
  const state = now ?? (await read($, session))

  return state.choice ?? (await defaultChoice($))
}

/** Sets a theme on this session. Says why when no window draws it. */
async function show($: EngineInterface, theme: PickerTheme): Promise<string | undefined> {
  showing = theme
  const set = await $.theme.set(theme.look)
  await syncMusic($)

  return set.isDrawn ? undefined : set.reason
}

/** Applies a pick: stores it (default or session) and shows it now. Returns the line to print. */
async function pick($: EngineInterface, id: string, forSession: boolean): Promise<string> {
  if (forSession) {
    await update($, session, was => ({ ...was, choice: id }))
  } else {
    await $.store.set(DEFAULT_KEY, id)
    // A session that had its own pick drops it, so the default shows here too.
    await update($, session, was => ({ ...was, choice: undefined }))
  }

  if (id === 'off') {
    // Clears whichever theme stands, any plugin's: only ever on an explicit pick.
    showing = undefined
    await $.theme.clear()
    await syncMusic($)

    return forSession ? 'No theme in this session.' : 'No theme, in this session and new ones.'
  }

  const theme = THEMES.find(one => one.id === id)

  if (theme === undefined) {
    return `No theme with the id "${id}".`
  }
  const reason = await show($, theme)
  const scope = forSession ? 'for this session' : 'as your default for every session'
  const note = reason === undefined ? '' : ` (Not drawn here: ${reason})`

  return `${theme.title} ${scope}.${note}`
}

function listText(current: string, fallback: string): string {
  const lines = THEMES.map(theme => {
    const marks = [theme.id === current ? 'showing' : '', theme.id === fallback ? 'default' : ''].filter(Boolean)

    return `  ${theme.id}: ${theme.title}. ${theme.blurb}${marks.length > 0 ? ` (${marks.join(', ')})` : ''}`
  })

  const musicLine = [
    '  music on | off | 10-100: background music for the theme showing (Magenta Hour has its own)',
    '  music add [file]: add your own track to the theme showing (no file: opens its music folder in Finder)',
  ]

  return ['Backdrops:', ...lines, '  off: no theme', ...musicLine, 'Use /backdrops <name>, or /backdrops <name> session for this session only.'].join('\n')
}

/** /backdrops music [on | off | 10-100]: changes the setting for every session, or says where it stands. */
async function setMusic($: EngineInterface, request: { setting?: 'on' | 'off'; volume?: number }): Promise<string> {
  if (request.setting !== undefined || request.volume !== undefined) {
    // a volume on its own also turns the music on
    await changeMusic($, { on: request.setting === undefined ? true : request.setting === 'on', volume: request.volume })
  }
  const { on, volume } = await musicSetting($)
  const folder = showing === undefined ? undefined : await musicFolder($, showing.id)
  const tracks = showing === undefined ? [] : await tracksFor($, showing.id, BUILT_IN[showing.id] ?? [])
  const where = showing === undefined
    ? ''
    : tracks.length === 0
      ? ` ${showing.title} has no music yet: put audio files (under 4 MB each) in ${folder ?? '~/.config/backdrops/music/' + showing.id}.`
      : tracks[0]?.kind === 'file'
        ? ` ${showing.title} plays your ${tracks.length} track${tracks.length === 1 ? '' : 's'} from ${folder}.`
        : ''

  return `Background music is ${on ? `on at ${volume}%` : 'off'}, in every session.${where}${on ? ' /backdrops music off to silence it, /backdrops music 10-100 for the volume.' : ' /backdrops music on to play it.'}`
}

async function runLook($: EngineInterface, args: string): Promise<{ text: string }> {
  if (args.trim() === '') {
    // a new card opens on its first page
    await update($, session, was => ({ ...was, page: 0, hover: undefined }))
  }
  const request = parseLook(args)

  switch (request.kind) {
    case 'card': {
      // Where the surface places transcript rows the card scrolls with the chat; else it sits above the prompt.
      // A new id each time: placing an id that stands redraws that row, which may be far up the transcript.
      const cardId = `${CARD}-${Math.round(await $.clock.now())}`
      const placed = await $.ui.place({ id: cardId })
      await update($, session, was => ({ ...was, cardId, cardInBand: !placed.isPlaced, cardAway: false, done: undefined }))

      return { text: 'Pick a theme on the card.' }
    }
    case 'list':
      return { text: listText(await effectiveChoice($), await defaultChoice($)) }
    case 'off':
      return { text: await pick($, 'off', request.forSession) }
    case 'apply':
      return { text: await pick($, request.theme.id, request.forSession) }
    case 'music':
      return { text: await setMusic($, request) }
    case 'music-add': {
      const theme = showing ?? THEMES[0]
      if (theme === undefined) {
        return { text: 'No theme to add music to.' }
      }
      if (request.path === undefined) {
        return { text: await openMusicFolder($, theme.id) }
      }
      const added = await addTrack($, theme.id, request.path)
      await syncMusic($)
      return { text: `${added} It plays with ${theme.title} while music is on.` }
    }
    case 'unknown':
      return { text: `No theme named "${request.name}". /backdrops list names them.` }
  }
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: COMMAND,
      description: 'Pick a backdrop: a card of previews, or /backdrops <name> [session]',
      argumentHint: '[name | list | off | music on|off|10-100] [session]',
    })

    if (PAINT_PROBLEMS.length > 0) {
      $.ui.toast(PAINT_PROBLEMS[0] ?? '')
    }

    const choice = await effectiveChoice($)
    const theme = THEMES.find(one => one.id === choice)

    // 'off' at start sets nothing: clearing here could wipe another plugin's theme.
    // No status line when it isn't drawn yet: at session start the app's window
    // usually hasn't connected, and it draws the theme once it does.
    if (theme !== undefined) {
      await show($, theme)
    }

    return next(e)
  })

  on('session.attach', async ($, e, next) => {
    // The music waits for a desktop window (at session start none has connected yet).
    await syncMusic($)
    return next(e)
  })
  on('session.detach', async ($, e, next) => {
    // Window gone (or the session ending under it): stop unless another desktop window remains.
    // (A session stays attached while the person looks at another session.)
    if (e.reason === 'end') {
      stopPlayer()
    } else {
      await syncMusic($)
    }
    return next(e)
  })
  on('session.end', ($, e, next) => {
    stopPlayer()
    return next(e)
  })
  // While the card is open it is the band's only row, so the band fits it and nothing slides under the pointer.
  on('ui.render', { component: 'AbovePromptList' }, async ($, e, next) => {
    const now = await read($, session)
    const mine = e.props.rows.filter(row => row.plugin === PLUGIN)
    if (now.cardAway || !now.cardInBand || mine.length === 0) {
      return next(e)
    }
    return next({ ...e, props: { ...e.props, rows: mine } })
  })

  on('ui.message', async ($, e, next) => {
    if (!e.module.endsWith('tile-hit.ts') && !e.module.endsWith('tap.ts')) {
      return next(e)
    }
    await onStrip($, e.data)
    return {}
  })

  on('command.run', { command: COMMAND }, async ($, e) => {
    try {
      return await runLook($, e.args)
    } catch (error) {
      return { text: `/backdrops failed: ${error instanceof Error ? error.message : String(error)}` }
    }
  })

  // The backdrop: only this mod's own scenes.
  on('ui.render', { component: 'Backdrop' }, async ($, e, next) => {
    if (e.props.plugin !== PLUGIN || (e.surface !== 'desktop' && e.surface !== 'mobile')) {
      return next(e)
    }
    const theme = THEMES.find(one => one.id === e.props.scene)

    if (theme === undefined) {
      return next(e)
    }
    const { Svg } = $.ui.resolve(e)

    return <Svg source={theme.scene} alt={theme.alt} />
  })

  on('ui.render', { component: 'Placed' }, async ($, e, next) => {
    if (e.props.plugin !== PLUGIN || !e.props.id.startsWith(CARD)) {
      return next(e)
    }
    const now = await read($, session)

    // Only the newest card draws; older rows go blank.
    return now.cardAway || e.props.id !== now.cardId ? next(e) : card($, $.ui.resolve(e), now, await defaultChoice($), e.surface, e.viewport?.columns)
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const now = await read($, session)

    if (!now.cardInBand || now.cardAway) {
      return next(e)
    }

    return card($, $.ui.resolve(e), now, await defaultChoice($), e.surface, e.props.bodyColumns)
  })
}

type CardElements = ReturnType<EngineInterface['ui']['resolve']>

/**
 * The card is a strip: one row of previews under a one-line header. Previews per page: seven, the most whose
 * names and check marks fit on one line at the app's caption size (the longest, "Magenta Hour ✓", needs about
 * 125 pt; the strip follows the message box, about 960 pt on a laptop and a monitor alike). More become pages.
 */
const PER_PAGE = 7
/** Cells one tile needs (its preview, the longest name and check mark, a gap): about 135 pt. */
const CELLS_PER_TILE = 11.4
/** Cells the header needs with the status shown: title, pager, status, action and close. */
const HEADER_CELLS = 66
/** Rows each tile's click layer covers: its preview and its name. */
const LAYER_ROWS = 3
/** A preview, in CSS pixels: 16:9, drawn at about three times in its 288 x 162 viewBox. */
const THUMB_W = 92
const THUMB_H = 52
/** The card's panel where it draws its own (in the transcript): near-black and a touch see-through. */
const PANEL = '#101414d4'
/** How long the card shows its confirmation before it closes. */
const CONFIRM_MS = 1500
/** No backdrop: the last tile, a choice like any theme (this session, or "make default"). */
const NONE_ID = 'off'

/** Previews per page as last drawn: seven at full width, fewer when a narrow window narrows the card. */
let perPage = PER_PAGE

function perPageFor(columns: number | undefined): number {
  return columns === undefined || columns <= 0 ? PER_PAGE : Math.max(4, Math.min(PER_PAGE, Math.floor(columns / CELLS_PER_TILE)))
}

type Tile = { id: string; title: string }

const TILES: readonly Tile[] = [
  ...THEMES.map(theme => ({ id: theme.id, title: theme.title })),
  { id: NONE_ID, title: 'None' },
]

function pagesOf(): number {
  return Math.max(1, Math.ceil(TILES.length / perPage))
}

function pageOf(now: PickerSession): number {
  return Math.max(0, Math.min(pagesOf() - 1, now.page ?? 0))
}

/** Mixes a #rrggbb colour toward white by `amount` (0 to 1). */
function lighter(hex: string, amount: number): string {
  const n = Number.parseInt(hex.slice(1), 16)
  const mix = (c: number) => Math.round(c + (255 - c) * amount).toString(16).padStart(2, '0')
  return `#${mix((n >> 16) & 255)}${mix((n >> 8) & 255)}${mix(n & 255)}`
}

/**
 * Each scene's signature colours, picked from its own picture: the frame of the chosen or hovered preview runs
 * from the first to the second; its check mark takes the first.
 */
const SIGNATURES: Readonly<Record<string, readonly [string, string]>> = {
  'magenta-hour': ['#ff6fae', '#9b6bff'],
  reaching: ['#ffffff', '#2a2a2a'],
  'after-hours': ['#c3a4ff', '#8a5cf0'],
  'crossing-hour': ['#ffcf8a', '#ff8f5a'],
  promenade: ['#ff9a7a', '#a77cff'],
  'coast-road': ['#ffb06a', '#8a6fd6'],
  'ocean-road': ['#3fd1b5', '#2f86c8'],
  'fractal-glass': ['#8ccaff', '#2f6cf0'],
  ember: ['#ffc06a', '#e8541e'],
  [NONE_ID]: ['#c9ced6', '#6b7480'],   // a cool neutral, not Reaching's white-to-black
}

function accentOf(id: string): string {
  return (SIGNATURES[id] ?? ['#ffffff'])[0]
}

/**
 * The None tile's picture: an empty tile (the panel shows through a 4% veil) with a centred ⊘ drawn as shapes, so
 * it reads as nothing and never as Reaching's black.
 */
const NONE_PICTURE = '<rect width="288" height="162" fill="#ffffff" fill-opacity=".04"/>' +
  '<g fill="none" stroke="#ffffff" stroke-opacity=".47" stroke-width="5">' +
  '<circle cx="144" cy="81" r="30"/><line x1="122.8" y1="102.2" x2="165.2" y2="59.8"/></g>'

/**
 * A preview: the theme's still (tools/make-photos.py), rounded by painting it as the fill of a rounded rectangle,
 * with a faint outline, or, when chosen (full) or under the pointer (lighter), a ring in its scene's colours. Ids are
 * unique per tile: the app draws every preview into one page.
 */
function previewOf(id: string, on: boolean, hovered: boolean): string {
  const picture = id === NONE_ID ? NONE_PICTURE : `<image href="${PHOTOS[id] ?? ''}" width="288" height="162"/>`
  const [from, to] = SIGNATURES[id] ?? ['#ffffff', '#ffffff']
  const ringed = on || hovered
  const gradient = ringed
    ? `<linearGradient id="g-${id}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${from}"/>` +
      `<stop offset="1" stop-color="${to}"/></linearGradient>`
    : ''
  const ring = ringed
    ? `<rect x="3.5" y="3.5" width="281" height="155" rx="17" fill="none" stroke="url(#g-${id})" stroke-width="7" ` +
      `stroke-opacity="${on ? 1 : 0.7}"/>`
    : '<rect x="1" y="1" width="286" height="160" rx="19" fill="none" stroke="#ffffff" stroke-opacity=".16" stroke-width="2"/>'
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 288 162"><defs><pattern id="p-${id}" ` +
    `patternUnits="userSpaceOnUse" width="288" height="162">${picture}</pattern>${gradient}</defs>` +
    `<rect width="288" height="162" rx="20" fill="url(#p-${id})"/>${ring}</svg>`
}

/**
 * What the card's click layers report (tile-hit.ts over each preview, tap.ts over the arrows and the action). A
 * preview reports its theme's id, not its place: one session can show the card in two windows of different widths.
 */
type StripEvent = { kind: 'pick'; id: string } | { kind: 'page'; by: number } | { kind: 'hover'; id?: string } | { kind: 'keep' }

function isStripEvent(data: unknown): data is StripEvent {
  return typeof data === 'object' && data !== null && 'kind' in data
}

/** Turns the page by one either way; false when there is no page that way. */
async function turnPage($: EngineInterface, by: number): Promise<boolean> {
  const now = await read($, session)
  const next = Math.max(0, Math.min(pagesOf() - 1, pageOf(now) + Math.sign(by)))
  if (next === pageOf(now)) {
    return false
  }
  await update($, session, was => ({ ...was, page: next }))
  return true
}

/** Makes what this session shows the default, says so in the card for a moment, then puts the card away. */
async function keepIt($: EngineInterface): Promise<void> {
  const was = await read($, session)
  if (was.choice !== undefined && was.choice !== (await defaultChoice($))) {
    // The confirmation goes where the person is looking: a toast lands in the app's main window, which may be
    // another window than this session's.
    const id = was.choice
    await pick($, id, false)
    const title = id === NONE_ID ? 'No backdrop' : THEMES.find(one => one.id === id)?.title ?? id
    const done = `✓ ${title} is your default`
    await update($, session, it => ({ ...it, done }))
    await $.clock.sleep(CONFIRM_MS)
    // Close only the card that said it: a new /backdrops or a click in the meantime keeps its card open.
    const after = await read($, session)
    if (after.done !== done || after.cardId !== was.cardId) {
      return
    }
  }
  await update($, session, it => ({ ...it, cardAway: true, done: undefined }))
}

/** What a click layer reported: try a preview, turn the page, frame the preview under the pointer, or keep. */
export async function onStrip($: EngineInterface, data: unknown): Promise<void> {
  if (!isStripEvent(data)) {
    return
  }
  if (data.kind === 'keep') {
    await keepIt($)
    return
  }
  if (data.kind === 'page') {
    await turnPage($, data.by)
    return
  }
  const now = await read($, session)
  if (data.kind === 'hover') {
    if (data.id !== now.hover) {
      await update($, session, was => ({ ...was, hover: data.id }))
    }
    return
  }
  const tile = TILES.find(one => one.id === data.id)
  if (tile !== undefined) {
    // a click during the confirmation keeps the card open for the new try
    await update($, session, was => ({ ...was, done: undefined }))
    await pick($, tile.id, true)
  }
}

/**
 * The card: a one-line header (/backdrops, the pager when there are pages, and once a preview is tried, "this
 * session only · ↵ make default", then ✕) over one row of previews. A click on a preview tries it in this session;
 * Enter or a click on "make default" keeps it for every session and closes the card. Where there are no pictures
 * or no click layers (the terminal), buttons stand in.
 */
function card(
  $: EngineInterface,
  elements: CardElements,
  now: PickerSession,
  fallback: string,
  surface: string,
  columns: number | undefined,
) {
  perPage = perPageFor(columns)
  const slotPercent = Math.floor(100 / perPage)
  const { Box, Text, Button, Markdown } = elements
  const Svg = 'Svg' in elements ? elements.Svg : undefined
  const Client = 'Client' in elements ? elements.Client : undefined
  const current = now.choice ?? fallback
  const close = () => update($, session, was => ({ ...was, cardAway: true }))
  const keep = now.choice !== undefined && now.choice !== fallback
  const pages = pagesOf()
  const page = pageOf(now)
  const shown = TILES.slice(page * perPage, page * perPage + perPage)
  const strip = Svg !== undefined && Client !== undefined && surface !== 'terminal'
  // room for the status beside the action
  const wide = columns === undefined || columns >= HEADER_CELLS

  return (
    // Above the prompt the app draws its own rounded panel round every mod's row: the card draws none of its own
    // there, so there is one layer, not a card inside a panel. In the transcript it draws its own.
    <Box flexDirection="column" paddingX={1} gap={1}
      {...(now.cardInBand ? {} : { borderStyle: 'round', borderColor: PANEL, backgroundColor: PANEL })}>
      <Box flexDirection="row" gap={1} alignItems="center">
        <Markdown text="`/backdrops`" />
        {strip && pages > 1 ? (
          // The pager sits by the title, where reading starts and above the first picture, and far from the
          // make-default action, so a missed arrow can't change the default. Each arrow has its own click target.
          <Box key="pages" flexDirection="row" alignItems="center" gap={1} flexShrink={0}>
            {[-1, 1].map(by => {
              const can = by < 0 ? page > 0 : page < pages - 1
              // body size: caption was too small to see or hit, heading outranked the title
              const arrow = <Text size="body" weight="medium" dimColor={!can}>{by < 0 ? '‹' : '›'}</Text>
              return (
                // two cells: the light patch under the pointer stays round the chevron, clear of the count
                <Box key={by < 0 ? 'back' : 'on'} position="relative" width={2} justifyContent="center" alignItems="center"
                  flexShrink={0} {...(can ? { hover: { backgroundColor: '#ffffff1f' } } : {})}>
                  {arrow}
                  {can && Client !== undefined ? (
                    <Box position="absolute" top={0} left={0} right={0} height={1}>
                      <Client key={by < 0 ? 'tap-back' : 'tap-on'} module="./tap.ts"
                        props={{ message: { kind: 'page', by } }} width="100%" height={1} />
                    </Box>
                  ) : null}
                </Box>
              )
            }).flatMap((arrowBox, i) => i === 0
              ? [arrowBox, <Text key="count" size="caption" mono dimColor>{`${page + 1} / ${pages}`}</Text>]
              : [arrowBox])}
          </Box>
        ) : null}
        <Box flexGrow={1} />
        {now.done !== undefined ? (
          <Text key="done" size="caption" mono color={lighter(accentOf(fallback), 0.4)}>{now.done}</Text>
        ) : keep && strip ? (
          // A click already shows the theme here, so the hint says what is true and offers the one step left, which
          // takes a click as well as Enter. The status goes when the card is narrow; the action always stays.
          <Box key="keep-row" flexDirection="row" flexShrink={0}>
            {wide ? <Text size="caption" mono>this session only · </Text> : null}
            {/* Only the action takes the click. It rests in the theme's colour lifted toward white, so it reads on
                every panel (at least 6.6:1 measured), and underlines under the pointer. */}
            <Box key="keep" position="relative" flexShrink={0}>
              <Text size="caption" mono color={lighter(accentOf(current), 0.4)} hover={{ underline: true }}>↵ make default</Text>
              {Client !== undefined ? (
                <Box position="absolute" top={0} left={0} right={0} height={1}>
                  <Client key="tap-keep" module="./tap.ts" props={{ message: { kind: 'keep' } }} width="100%" height={1} />
                </Box>
              ) : null}
            </Box>
          </Box>
        ) : null}
        <Button key="close" variant="secondary" label="✕" role="dismiss" onPress={close} />
      </Box>
      {strip ? (
        <Box key="strip" flexDirection="row" width="100%">
          {shown.map((tile, slot) => {
            const on = tile.id === current
            const edge = slot === 0 ? -1 : slot === shown.length - 1 ? 1 : 0
            return (
              <Box key={`tile-${tile.id}`} position="relative" flexDirection="column" width={`${slotPercent}%`} flexShrink={0}>
                <Svg source={previewOf(tile.id, on, tile.id === now.hover)} alt={on ? `${tile.title}, showing` : tile.title}
                  width={THUMB_W} height={THUMB_H} />
                {/* The surface wraps text by counted characters, not measured width; every name with its check mark
                    measures under the slot, so the name's box is made wide in cells and the line never breaks. */}
                <Box width={18} flexShrink={0}>
                  <Text size="caption" weight="medium" wrap="truncate">
                    {tile.title}
                    {on ? <Text color={accentOf(tile.id)}>{' ✓'}</Text> : null}
                  </Text>
                </Box>
                {/* keyed by theme: a layer keeps the props it was first drawn with, so a new page needs new layers */}
                <Box position="absolute" top={0} left={0} right={0} height={LAYER_ROWS}>
                  <Client key={`hit-${tile.id}`} module="./tile-hit.ts" props={{ id: tile.id, rows: LAYER_ROWS, edge, pages }}
                    width="100%" height={LAYER_ROWS} />
                </Box>
              </Box>
            )
          })}
        </Box>
      ) : (
        <Box flexDirection="row" flexWrap="wrap" gap={1}>
          {TILES.map(tile => (
            <Button key={`try-${tile.id}`} label={tile.id === current ? `${tile.title} ✓` : tile.title}
              onPress={() => pick($, tile.id, true)} />
          ))}
          {keep ? <Button key="keep-button" variant="primary" label="Make default" onPress={() => keepIt($)} /> : null}
        </Box>
      )}
    </Box>
  )
}
