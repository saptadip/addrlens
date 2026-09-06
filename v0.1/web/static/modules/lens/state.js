import { LIFE_MODE_LENSES, LM_ACTIVE_KEY } from '../constants.js';

// Shared lens state extracted here to break the lens/ai <-> lens/index cycle.
// Both siblings import from this leaf module instead of from each other.
export function getActiveLens() {
  const known = new Set(LIFE_MODE_LENSES.map(l => l.slug));
  try {
    const saved = localStorage.getItem(LM_ACTIVE_KEY);
    if (saved && known.has(saved)) return saved;
  } catch (e) {}
  return (LIFE_MODE_LENSES[0] && LIFE_MODE_LENSES[0].slug) || 'young_family';
}
