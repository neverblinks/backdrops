import { makeColors } from './make-colors.js'
import { SCENE } from './scene-coast-road.js'
import type { Theme } from './theme'

// Dusk surfaces; the accent is the sunset's colour.
const colors = makeColors({
  label: 'Coast Road',
  only: 'dark',
  codeTheme: { dark: 'catppuccin-mocha' },
  roles: { accent: '#ffb877', danger: '#ff5a78', success: '#4fe0b0', warning: '#ffc266', pro: '#c58cff' },
  dark: {
    gray: {
      anchors: {
        'surface-0': '#0b0a1c',
        'surface-1': '#110f25',
        'surface-2': '#17142e',
        'surface-3': '#1e1a38',
        'text-primary': '#f3f5ff',
        'text-secondary': '#d4d7f2',
        'text-muted': '#c5c8ee',
      },
    },
  },
})

export const COAST_ROAD_PROBLEMS = colors.problems

export const COAST_ROAD: Theme = {
  id: 'coast-road',
  title: 'Coast Road',
  blurb: 'Bixby Creek Bridge, Big Sur, at sunset: a cyclist rides north toward the sun setting inside the arch, on a loop.',
  scene: SCENE,
  alt: 'Bixby Creek Bridge at sunset seen from inland: the open-spandrel arch over the canyon, the sun setting on the sea inside it, a cyclist on the deck',
  look: {
    colors: colors.theme,
    backdrop: { scene: 'coast-road', glass: { blur: 0, tint: '#171735', opacity: 0.58 } },
    overrideColorScheme: 'dark',
  },
}
