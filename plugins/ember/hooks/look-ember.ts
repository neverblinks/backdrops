import { makeColors } from './make-colors.js'
import { SCENE } from './scene-ember.js'
import type { Theme } from './theme'

// Warm near-black surfaces, an orange accent; text lifted a touch so the glow behind it stays readable.
const colors = makeColors({
  label: 'Night Hearth',
  only: 'dark',
  codeTheme: { dark: 'ayu-dark' },
  roles: { accent: '#f07a32', danger: '#e85a4a', success: '#6cc48a', warning: '#e6b04e', pro: '#a98cf6' },
  dark: {
    gray: {
      anchors: {
        'surface-0': '#070504',
        'surface-1': '#100c0a',
        'surface-2': '#1a1512',
        'surface-3': '#221b18',
        'text-primary': '#cacaca',
        'text-secondary': '#b0b0b0',
        'text-muted': '#a1a1a1',
      },
    },
  },
})

export const EMBER_PROBLEMS = colors.problems

export const EMBER: Theme = {
  id: 'ember',
  title: 'Night Hearth',
  blurb: 'A warm glow breathes in the corner of a dark, grainy screen.',
  scene: SCENE,
  alt: 'A dark, finely grained screen with a warm orange glow rising from the bottom-right corner',
  look: {
    colors: colors.theme,
    backdrop: { scene: 'ember', glass: { blur: 0, tint: '#0a0603', opacity: 0.43 } },
    overrideColorScheme: 'dark',
  },
}
