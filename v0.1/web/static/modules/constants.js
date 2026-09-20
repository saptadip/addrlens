// constants.js — thin dispatcher; delegates to constants.<city>.js at boot.
// Reads document.body.dataset.city set by app.main._load_index_html SSR.
// Falls back to Berlin defaults when attr is absent (dev, tests, older browsers).
// Top-level await requires ES2022 modules (Chrome 89+, Firefox 89+, Safari 15+).
const _city = (typeof document !== 'undefined' && document.body?.dataset?.city === 'hamburg')
  ? 'hamburg' : 'berlin';
const _mod = await import(`./constants.${_city}.js`);

export const AMEN = _mod.AMEN;
export const AMEN_COLOR = _mod.AMEN_COLOR;
export const AMEN_TAB = _mod.AMEN_TAB;
export const tabOf = _mod.tabOf;
export const EDU_STYLE = _mod.EDU_STYLE;
export const NOISE_TIER_LABEL = _mod.NOISE_TIER_LABEL;
export const LM_STATE_KEY = _mod.LM_STATE_KEY;
export const LM_SEEN_KEY = _mod.LM_SEEN_KEY;
export const LM_PULSE_MS = _mod.LM_PULSE_MS;
export const LM_ACTIVE_KEY = _mod.LM_ACTIVE_KEY;
export const LM_DEFAULT_LENS = _mod.LM_DEFAULT_LENS;
export const LENS_TILE_EXPLANATIONS = _mod.LENS_TILE_EXPLANATIONS;
export const GLOSSARY = _mod.GLOSSARY;
export const TILE_GLOSSARY_KEYS = _mod.TILE_GLOSSARY_KEYS;
export const TIER_PIN_COLORS = _mod.TIER_PIN_COLORS;
export const LIFE_MODE_LENSES = _mod.LIFE_MODE_LENSES;
export const CARD_ORDER_KEY = _mod.CARD_ORDER_KEY;
export const CONN_META = _mod.CONN_META;
export const COMPARE_KEY = _mod.COMPARE_KEY;
export const COMPARE_MAX = _mod.COMPARE_MAX;
export const _TITLE_SMALL = _mod._TITLE_SMALL;
export const _LENS_WITH_AI = _mod._LENS_WITH_AI;
export const _ICON_DOWNLOAD = _mod._ICON_DOWNLOAD;
