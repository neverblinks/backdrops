import type { ThemeSetArgs } from 'claude-code'

/** One backdrop theme: what the picker and the single-theme plugins both need. */
export type Theme = {
  /** The id people type (/backdrops reaching-classic) and the backdrop's scene name. */
  id: string
  title: string
  /** For a theme with versions (Reaching: clear, classic): this version's word. */
  version?: string
  blurb: string
  /** The animated SVG. */
  scene: string
  /** What the picture shows, for screen readers. */
  alt: string
  look: ThemeSetArgs
}
