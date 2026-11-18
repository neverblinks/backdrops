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
