/** What /backdrops keeps for one session: its own pick, if any, and where the card stands. */
export type PickerSession = {
  /** A theme id, 'off' for none, or absent to follow the default. */
  choice?: string
  /** The card is drawn above the prompt (where the surface places no transcript rows). */
  cardInBand: boolean
  /** The card was closed. */
  cardAway: boolean
  /** The id of the card the last /backdrops placed; only that one draws. */
  cardId?: string
  /** The preview under the pointer, by id; absent when the pointer is elsewhere. */
  hover?: string
  /** The page of previews the card shows, from 0. */
  page?: number
  /** The confirmation the card shows for a moment after "make default", before it closes. */
  done?: string
}

/** The music setting (stored in $.store, for every session). */
export type MusicView = {
  on: boolean
  /** 10 to 100: percent of the files' mastered level. */
  volume: number
}

declare module 'claude-code' {
  interface PluginState {
    // Shaped: the atom carries a shape tag, so a reload that changes the idea of the value declines the old one
    backdrops: {
      session: Shaped<PickerSession>
    }
  }
}
