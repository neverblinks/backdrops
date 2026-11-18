import { makeColors } from './make-colors.js'
import { SCENE } from './scene-after-hours.js'
import type { Theme } from './theme'

// Night-violet surfaces; accent the rooftop's cyan neon.
const colors = makeColors({
  label: 'After Hours',
  only: 'dark',
  codeTheme: { dark: 'catppuccin-mocha' },
  roles: { accent: '#4fd8ff', danger: '#ff5a78', success: '#4fe0b0', warning: '#ffc266', pro: '#c58cff' },
  dark: {
    gray: {
      anchors: {
        'surface-0': '#08071a',
        'surface-1': '#0d0b22',
        'surface-2': '#13102b',
        'surface-3': '#191535',
        'text-primary': '#eef0fb',
        'text-secondary': '#ced0eb',
        'text-muted': '#bec1e6',
      },
    },
  },
})

export const AFTER_HOURS_PROBLEMS = colors.problems

export const AFTER_HOURS: Theme = {
  id: 'after-hours',
  title: 'After Hours',
  blurb: 'A synthwave Miami night: the city lit up across the bay, seen from a rooftop.',
  scene: SCENE,
  alt: 'A city at night across a bay, seen from a rooftop: neon towers, a bridge with traffic, a yacht',
  look: {
    colors: colors.theme,
    backdrop: { scene: 'after-hours', glass: { blur: 0, tint: '#06050f', opacity: 0.57 } },
    overrideColorScheme: 'dark',
  },
}
