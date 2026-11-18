import { makeColors } from './make-colors.js'
import { SCENE } from './scene-magenta-hour.js'
import type { Theme } from './theme'

// Deep violet surfaces from the bay at dusk; accent the coral of the sunset; pastel code colours.
const colors = makeColors({
  label: 'Magenta Hour',
  only: 'dark',
  codeTheme: { dark: 'catppuccin-macchiato' },
  roles: { accent: '#ff7a93', danger: '#ff5d63', success: '#5fd9a8', warning: '#ffb35c', pro: '#a98bff' },
  dark: {
    gray: {
      anchors: {
        'surface-0': '#0d0a1c',
        'surface-1': '#141029',
        'surface-2': '#1a1533',
        'surface-3': '#211a3e',
        'text-primary': '#f6eefa',
        'text-secondary': '#dccce9',
        'text-muted': '#cdbde1',
      },
    },
  },
})

export const MAGENTA_HOUR_PROBLEMS = colors.problems

export const MAGENTA_HOUR: Theme = {
  id: 'magenta-hour',
  title: 'Magenta Hour',
  blurb: 'A synthwave Miami dusk: palms, a causeway, the sun going down over a violet bay.',
  scene: SCENE,
  alt: 'A sunset over a violet bay: palms, a causeway with traffic, a skyline with deco neon',
  look: {
    colors: colors.theme,
    backdrop: { scene: 'magenta-hour', glass: { blur: 0, tint: '#0c0720', opacity: 0.58 } },
    overrideColorScheme: 'dark',
  },
}
