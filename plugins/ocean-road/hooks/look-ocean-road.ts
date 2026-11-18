import { makeColors } from './make-colors.js'
import { SCENE } from './scene-ocean-road.js'
import type { Theme } from './theme'

// Dusk surfaces; the accent is the sunset's colour.
const colors = makeColors({
  label: 'Ocean Road',
  only: 'dark',
  codeTheme: { dark: 'catppuccin-mocha' },
  roles: { accent: '#f2c79a', danger: '#ff5a78', success: '#4fe0b0', warning: '#ffc266', pro: '#c58cff' },
  dark: {
    gray: {
      anchors: {
        'surface-0': '#071019',
        'surface-1': '#0b1621',
        'surface-2': '#101d2a',
        'surface-3': '#162534',
        'text-primary': '#f5f6ff',
        'text-secondary': '#d6d8f3',
        'text-muted': '#c6c9ef',
      },
    },
  },
})

export const OCEAN_ROAD_PROBLEMS = colors.problems

export const OCEAN_ROAD: Theme = {
  id: 'ocean-road',
  title: 'Ocean Road',
  blurb: "The Atlantic Ocean Road in Norway at dusk: a cyclist rides the long curve and over Storseisundet's hump, on a loop.",
  scene: SCENE,
  alt: "The Atlantic Ocean Road at dusk: a causeway curving across the sea from the foreground to Storseisundet bridge's steep hump against the afterglow, a cyclist on the road",
  look: {
    colors: colors.theme,
    backdrop: { scene: 'ocean-road', glass: { blur: 0, tint: '#0b1626', opacity: 0.52 } },
    overrideColorScheme: 'dark',
  },
}
