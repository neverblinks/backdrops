import { makeColors } from './make-colors.js'
import { SCENE } from './scene-promenade.js'
import type { Theme } from './theme'

// Dusk surfaces; the accent is the sunset's colour.
const colors = makeColors({
  label: 'Promenade',
  only: 'dark',
  codeTheme: { dark: 'catppuccin-mocha' },
  roles: { accent: '#ff9a86', danger: '#ff5a78', success: '#4fe0b0', warning: '#ffc266', pro: '#c58cff' },
  dark: {
    gray: {
      anchors: {
        'surface-0': '#0d0a1c',
        'surface-1': '#130f25',
        'surface-2': '#1a142e',
        'surface-3': '#211a38',
        'text-primary': '#f2f4ff',
        'text-secondary': '#d3d6f1',
        'text-muted': '#c4c7ed',
      },
    },
  },
})

export const PROMENADE_PROBLEMS = colors.problems

export const PROMENADE: Theme = {
  id: 'promenade',
  title: 'Promenade',
  blurb: 'The Brooklyn Bridge at dusk: a cyclist rides the promenade toward the sun, on a loop.',
  scene: SCENE,
  alt: 'The Brooklyn Bridge at dusk: the stone tower with its pointed arches, the cable web, Lower Manhattan and the setting sun, a cyclist on the promenade',
  look: {
    colors: colors.theme,
    backdrop: { scene: 'promenade', glass: { blur: 0, tint: '#1d1a36', opacity: 0.61 } },
    overrideColorScheme: 'dark',
  },
}
