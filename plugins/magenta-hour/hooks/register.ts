import type { EngineInterface, Register, RenderElement } from 'claude-code'

import { MAGENTA_HOUR, MAGENTA_HOUR_PROBLEMS } from './look-magenta-hour'

/**
 * Magenta Hour alone, with its optional original music.
 *
 *   /magenta-hour              turns it on
 *   /magenta-hour off          no backdrop from this plugin
 *   /magenta-hour music on     its original music, quietly, while it shows (off by default)
 *   /magenta-hour music off
 *   /magenta-hour music add [file]   your own track instead of the built-in ones (no file: opens the folder)
 *
 * Choices are remembered for new sessions.
 */
const PLUGIN = 'magenta-hour'
const COMMAND = 'magenta-hour'
const CHOICE_KEY = 'choice'
const MUSIC_KEY = 'music'

export type Request =
  | { kind: 'on' }
  | { kind: 'off' }
  | { kind: 'music'; on?: boolean }
  | { kind: 'music-add'; path?: string }
  | { kind: 'unknown'; text: string }

export function parseRequest(args: string): Request {
  const add = args.trim().match(/^music\s+add(?:\s+(.+))?$/i)
  if (add !== null) {
    return add[1] === undefined ? { kind: 'music-add' } : { kind: 'music-add', path: add[1] }
  }
  const words = args.trim().toLowerCase().split(/\s+/).filter(word => word !== '')
  if (words.length === 0) {
    return { kind: 'on' }
  }
  if (words.length === 1 && words[0] === 'off') {
    return { kind: 'off' }
  }
  if (words[0] === 'music' && words.length <= 2) {
    if (words[1] === undefined) {
      return { kind: 'music' }
    }
    if (words[1] === 'on' || words[1] === 'off') {
      return { kind: 'music', on: words[1] === 'on' }
    }
  }
  return { kind: 'unknown', text: args.trim() }
}

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

// ------------------------------------------------------------------ music
// Three original tracks (synthesised in themes/magenta-hour/make-music.py), or the person's own from
// ~/.config/backdrops/music/magenta-hour/, played while Magenta Hour shows in a desktop window, and
// only if the person turned it on. The player (one session at a time) is the music block above.
const BUILT_IN = ['music/magenta-hour.m4a', 'music/magenta-hour-2.m4a', 'music/magenta-hour-3.m4a'] as const
let showing = false

async function syncMusic($: EngineInterface): Promise<void> {
  const tracks = showing ? await tracksFor($, MAGENTA_HOUR.id, BUILT_IN) : []
  await syncPlayer($, (await $.store.get(MUSIC_KEY)) === 'on', tracks, 0.25)
}

// ------------------------------------------------------------------ showing it

async function show($: EngineInterface, on: boolean): Promise<string | undefined> {
  showing = on
  let reason: string | undefined
  if (on) {
    const set = await $.theme.set(MAGENTA_HOUR.look)
    reason = set.isDrawn ? undefined : set.reason
  } else {
    await $.theme.clear()
  }
  await syncMusic($)
  return reason
}

async function answer($: EngineInterface, args: string): Promise<string> {
  const request = parseRequest(args)
  switch (request.kind) {
    case 'on': {
      await $.store.set(CHOICE_KEY, 'on')
      const why = await show($, true)
      const done = 'Magenta Hour is on, here and in new sessions. /magenta-hour off turns it off; /magenta-hour music on adds its music.'
      return why === undefined ? done : `${done} (Not drawn yet: ${why})`
    }
    case 'off':
      await $.store.set(CHOICE_KEY, 'off')
      await show($, false)
      return 'Magenta Hour is off. /magenta-hour brings it back.'
    case 'music-add': {
      if (request.path === undefined) {
        return await openMusicFolder($, MAGENTA_HOUR.id)
      }
      const added = await addTrack($, MAGENTA_HOUR.id, request.path)
      await syncMusic($)
      return `${added} Your tracks play instead of the built-in ones while music is on.`
    }
    case 'music': {
      if (request.on !== undefined) {
        await $.store.set(MUSIC_KEY, request.on ? 'on' : 'off')
        await syncMusic($)
      }
      const own = (await tracksFor($, MAGENTA_HOUR.id, [])).length
      const what = own > 0 ? `your ${own} track${own === 1 ? '' : 's'} from ${await musicFolder($, MAGENTA_HOUR.id)}` : 'three original tracks'
      return (await $.store.get(MUSIC_KEY)) === 'on'
        ? `Music is on: ${what}, quietly, while Magenta Hour shows. /magenta-hour music off stops it.`
        : `Music is off. /magenta-hour music on plays ${what} quietly while Magenta Hour shows.`
    }
    case 'unknown':
      return `Unknown "${request.text}". Use /magenta-hour, /magenta-hour off, /magenta-hour music on|off, or /magenta-hour music add [file].`
  }
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: COMMAND,
      description: 'Magenta Hour backdrop (a synthwave Miami dusk); off; music on|off',
      argumentHint: '[off | music on|off | music add [file]]',
    })
    const unpainted = MAGENTA_HOUR_PROBLEMS.find(line => line.startsWith("Desktop won't paint"))
    if (unpainted !== undefined) {
      $.ui.toast(unpainted)
    }
    // 'off' at start sets nothing: clearing here could wipe another plugin's theme.
    if ((await $.store.get(CHOICE_KEY)) !== 'off') {
      await show($, true)
    }
    return next(e)
  })

  // The music waits for a desktop window, and stops when it goes or the session ends.
  on('session.attach', async ($, e, next) => {
    await syncMusic($)
    return next(e)
  })
  on('session.detach', async ($, e, next) => {
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

  on('command.run', { command: COMMAND }, async ($, e) => {
    try {
      return { text: await answer($, e.args) }
    } catch (error) {
      return { text: `/magenta-hour failed: ${error instanceof Error ? error.message : String(error)}` }
    }
  })

  on('ui.render', { component: 'Backdrop' }, ($, e, next) => {
    if ((e.surface !== 'desktop' && e.surface !== 'mobile') || e.props.plugin !== PLUGIN || e.props.scene !== MAGENTA_HOUR.id) {
      return next(e)
    }
    const { Svg } = $.ui.resolve(e)
    return h(Svg, { source: MAGENTA_HOUR.scene, alt: MAGENTA_HOUR.alt }) as RenderElement
  })
}
