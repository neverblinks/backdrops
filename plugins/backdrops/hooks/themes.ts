import { EMBER, EMBER_PROBLEMS } from './look-ember'
import { FRACTAL_GLASS, FRACTAL_GLASS_PROBLEMS } from './look-fractal-glass'
import { MAGENTA_HOUR, MAGENTA_HOUR_PROBLEMS } from './look-magenta-hour'
import { AFTER_HOURS, AFTER_HOURS_PROBLEMS } from './look-after-hours'
import { REACHING, REACHING_PROBLEMS } from './look-reaching'
import { CROSSING_HOUR, CROSSING_HOUR_PROBLEMS } from './look-crossing-hour'
import { PROMENADE, PROMENADE_PROBLEMS } from './look-promenade'
import { COAST_ROAD, COAST_ROAD_PROBLEMS } from './look-coast-road'
import { OCEAN_ROAD, OCEAN_ROAD_PROBLEMS } from './look-ocean-road'
import type { Theme } from './theme'

/** A theme as the picker shows it (its preview is in photos.ts, by id). */
export type PickerTheme = Theme

// Card order, one row: Reaching first (the collection's signature), the two Miami nights, the three bridges,
// the causeway, then blue glass and the warm glow. None follows them on the card.
export const THEMES: readonly PickerTheme[] = [REACHING, MAGENTA_HOUR, AFTER_HOURS, CROSSING_HOUR, PROMENADE, COAST_ROAD, OCEAN_ROAD, FRACTAL_GLASS, EMBER]

/** Lines the desktop won't paint, from any theme's palette: shown once at session start. */
export const PAINT_PROBLEMS: readonly string[] = [
  ...REACHING_PROBLEMS,
  ...MAGENTA_HOUR_PROBLEMS,
  ...AFTER_HOURS_PROBLEMS,
  ...EMBER_PROBLEMS,
  ...FRACTAL_GLASS_PROBLEMS,
  ...CROSSING_HOUR_PROBLEMS,
  ...PROMENADE_PROBLEMS,
  ...COAST_ROAD_PROBLEMS,
  ...OCEAN_ROAD_PROBLEMS,
].filter(line => line.startsWith("Desktop won't paint"))

/** A theme by id or title, any case, spaces or hyphens ("after hours", "After-Hours"). */
export function themeNamed(name: string): PickerTheme | undefined {
  const key = name.trim().toLowerCase().replace(/[\s_]+/g, '-')
  return THEMES.find(theme => theme.id === key || theme.title.toLowerCase().replace(/\s+/g, '-') === key)
}
