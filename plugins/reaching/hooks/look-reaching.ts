import { makeColors } from './make-colors.js'
import { SCENE as CLEAR } from './scene-reaching.js'
import type { Theme } from './theme'

// Black and white like a dot-matrix sign; colour shows only where it means something.
export const colors = makeColors({
  label: 'Reaching',
  only: 'dark',
  codeTheme: { dark: 'vesper' },
  roles: { accent: '#d8dde6', danger: '#e0675e', success: '#7fbf8e', warning: '#d6ad62', pro: '#9aa8c4' },
  dark: {
    gray: {
      anchors: {
        'surface-0': '#000000',
        'surface-1': '#0a0a0a',
        'surface-2': '#111111',
        'surface-3': '#171717',
        'text-primary': '#f4f4f4',
        'text-secondary': '#c9c9c9',
        'text-muted': '#ababab',
      },
    },
  },
})

export const REACHING_PROBLEMS = colors.problems
export const ALT = 'Two hands reaching toward each other, drawn in dots that turn to ASCII as a wave passes'

/** The default: the picture is drawn once; the app's glass (black, 0.72, no blur) dims the chat column and follows it. */
export const REACHING: Theme = {
  id: 'reaching',
  title: 'Reaching',
  version: 'clear',
  blurb: 'Two hands in dots; a wave turns them to ASCII. Artwork by @samdape.',
  scene: CLEAR,
  alt: ALT,
  look: {
    colors: colors.theme,
    backdrop: { scene: 'reaching', glass: { blur: 0, tint: '#000000', opacity: 0.72 } },
    overrideColorScheme: 'dark',
  },
}
