import { makeColors } from './make-colors.js'
import { SCENE } from './scene-fractal-glass.js'
import type { Theme } from './theme'

// Deep navy surfaces; accent the glow's blue.
const colors = makeColors({
  label: 'Fractal Glass',
  only: 'dark',
  codeTheme: { dark: 'catppuccin-mocha' },
  roles: { accent: '#5a9ef5', danger: '#f2777a', success: '#7fd1a0', warning: '#e8c170', pro: '#b39cf7' },
  dark: {
    gray: {
      anchors: {
        'surface-0': '#04070c',
        'surface-1': '#0a0f17',
        'surface-2': '#111824',
        'surface-3': '#182131',
        'text-primary': '#e6edf7',
        'text-secondary': '#b6c2d4',
        'text-muted': '#a0aec2',
      },
    },
  },
})

export const FRACTAL_GLASS_PROBLEMS = colors.problems

export const FRACTAL_GLASS: Theme = {
  id: 'fractal-glass',
  title: 'Fractal Glass',
  blurb: 'A blue glow drifts behind fluted glass.',
  scene: SCENE,
  alt: 'A soft blue glow drifting behind a pane of vertical fluted glass, on near black',
  look: {
    colors: colors.theme,
    backdrop: { scene: 'fractal-glass', glass: { blur: 0, tint: '#04070c', opacity: 0.63 } },
    overrideColorScheme: 'dark',
  },
}
