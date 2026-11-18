import { ALT, colors } from './look-reaching'
import { SCENE as CLASSIC } from './scene-reaching-classic.js'
import type { Theme } from './theme'

/**
 * Reaching's second version, only in the single `reaching` plugin (/reaching classic), not in the
 * picker: a lighter band plus the app's glass tint over the chat area, calmer on large monitors.
 */
export const REACHING_CLASSIC: Theme = {
  id: 'reaching-classic',
  title: 'Reaching Classic',
  version: 'classic',
  blurb: 'Reaching with a tint behind the chat: calmer for long reading on big screens.',
  scene: CLASSIC,
  alt: ALT,
  look: {
    colors: colors.theme,
    backdrop: { scene: 'reaching-classic', glass: { blur: 0, tint: '#000000', opacity: 0.65 } },
    overrideColorScheme: 'dark',
  },
}
