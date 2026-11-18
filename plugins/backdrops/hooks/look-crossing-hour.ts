import { makeColors } from './make-colors.js'
import { SCENE } from './scene-crossing-hour.js'
import type { Theme } from './theme'

// Dusk surfaces; the accent is the sunset's colour.
const colors = makeColors({
  label: 'Crossing Hour',
  only: 'dark',
  codeTheme: { dark: 'catppuccin-mocha' },
  roles: { accent: '#ffad6e', danger: '#ff5a78', success: '#4fe0b0', warning: '#ffc266', pro: '#c58cff' },
  dark: {
    gray: {
      anchors: {
        'surface-0': '#09091c',
        'surface-1': '#0e0e25',
        'surface-2': '#14142e',
        'surface-3': '#1b1a38',
        'text-primary': '#eef0fb',
        'text-secondary': '#cfd1ec',
        'text-muted': '#bfc2e8',
      },
    },
  },
})

export const CROSSING_HOUR_PROBLEMS = colors.problems

export const CROSSING_HOUR: Theme = {
  id: 'crossing-hour',
  title: 'Crossing Hour',
  blurb: 'Tower Bridge at sunset: a cyclist rides out of the sun and across, on a loop.',
  scene: SCENE,
  alt: 'Tower Bridge at sunset, seen side-on from downstream: a floodlit tower, the sun beside the Shard, a cyclist crossing',
  look: {
    colors: colors.theme,
    backdrop: { scene: 'crossing-hour', glass: { blur: 0, tint: '#141634', opacity: 0.61 } },
    overrideColorScheme: 'dark',
  },
}
