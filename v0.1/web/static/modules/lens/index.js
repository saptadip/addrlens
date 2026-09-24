import { ico } from '../icons.js';
import { LM_STATE_KEY, LM_ACTIVE_KEY, LM_PULSE_MS, LM_SEEN_KEY,
         LIFE_MODE_LENSES, LENS_TILE_EXPLANATIONS, GLOSSARY,
         TILE_GLOSSARY_KEYS } from '../constants.js';
import { S } from '../state.js';
import { esc, escapeHtml, labelWithGlossHtml, toTitleCase,
         dropOrphanTooltips, _track } from '../dom.js';
import { initLensMap, _updateLensMapPins } from '../maps.js';
import { _hasLensAI, renderLensAIIdle, hydrateLensAIPanel } from './ai.js';
import { getActiveLens } from './state.js';
export { getActiveLens };

export function setActiveLens(slug) {
  const known = new Set(LIFE_MODE_LENSES.map(l => l.slug));
  if (!known.has(slug)) return;
  try { localStorage.setItem(LM_ACTIVE_KEY, slug); } catch (e) {}
  _track('lens_switch', { lens: slug });
  document.querySelectorAll('.lens-picker [data-lens]').forEach(btn => {
    const on = btn.dataset.lens === slug;
    btn.classList.toggle('active', on);
    btn.setAttribute('aria-selected', on ? 'true' : 'false');
  });
  const modal = document.getElementById('lens-modal');
  if (modal && !modal.hidden) closeLensModal();
  dropOrphanTooltips();
  renderAllPanels();
  if (location.hash === '#compare') {
    // Late import to avoid circular dep: compare.js imports from this file.
    import('../compare.js').then(m => m.renderCompare());
  }
}

export function renderLensPicker(activeSlug) {
  const active = activeSlug || getActiveLens();
  const tabs = LIFE_MODE_LENSES.map(lens => {
    const on = lens.slug === active;
    return `<button class="lens-tab${on ? ' active' : ''}"
                    role="tab" aria-selected="${on ? 'true' : 'false'}"
                    data-lens="${escapeHtml(lens.slug)}"
                    type="button">${lens.icon}${escapeHtml(lens.label)}</button>`;
  }).join('');
  return `<div class="lens-picker" role="tablist" aria-label="Choose a lens">${tabs}</div>`;
}

export function isAnyLensAvailable(addr) {
  const lens = (addr && addr.lens) || {};
  return LIFE_MODE_LENSES.some(l => lens[l.slug] && !lens[l.slug].error);
}

export function renderLensTile(tile, lensSlug) {
  const iconSVG = (typeof ico !== 'undefined' && ico[tile.icon]) || '';
  const tier    = tile.tier || 'unknown';
  const badge   = tier === 'unknown' ? 'N/A' : tier.toUpperCase();
  const aria    = `${tile.label}, tier ${tier}: ${tile.rule}`;
  const numeric = tile.numeric
    ? `<div class="tile-numeric">${escapeHtml(tile.numeric)}</div>`
    : '';
  const gesixClass = '';
  return `
    <button class="cell lens-tile lens-tile-face${gesixClass} tier-${escapeHtml(tier)}"
            data-tile-key="${escapeHtml(tile.key)}"
            aria-label="${escapeHtml(aria)}"
            type="button">
      <div class="tile-row tile-head">
        <span class="tile-icon" aria-hidden="true">${iconSVG}</span>
        <span class="tile-label">${escapeHtml(toTitleCase(tile.label))}</span>
      </div>
      <div class="tile-row tile-foot">
        <div class="tile-indicator" role="img"
             aria-label="Tier: ${escapeHtml(tier)}">
          <span class="tile-dot" aria-hidden="true"></span>
          <span class="sr-only">Tier: ${escapeHtml(badge)}</span>
        </div>
        <div class="tile-rule">${escapeHtml(tile.rule)}</div>
      </div>
    </button>
  `;
}

// 3-segment tier donut for the Colour Scale panel.
export function renderTierDonut(tile) {
  const tier = tile && tile.tier;
  if (!['green', 'amber', 'red'].includes(tier)) return '';
  // Note: for 2-tier tiles (e.g. parkzone) the donut still renders
  // its 3-arc spectrum with a dim red arc, matching the visual
  // pattern of every other card. The 2-row legend below the donut
  // is the semantic source of truth — users understand the donut as
  // the tier-scale reference, not as a promise that all three tiers
  // fire for this signal.
  const iconSVG = ico[tile.icon] || '';
  const activeIdx = { green: 0, amber: 1, red: 2 }[tier];
  const cx = 100, cy = 100, r = 74, sw = 22;
  const C = 2 * Math.PI * r;
  const segLen = C / 3;
  const restLen = C - segLen;
  const colors = ['#22C55E', '#F59E0B', '#EF4444'];
  const gap = 3;
  const segs = colors.map((color, i) => {
    const rot = -90 + (i * 120);
    const isActive = i === activeIdx;
    const op = isActive ? 1 : 0.22;
    return `<circle cx="${cx}" cy="${cy}" r="${r}"
              fill="none" stroke="${color}" stroke-width="${sw}"
              stroke-dasharray="${segLen - gap} ${restLen + gap}"
              opacity="${op}"
              transform="rotate(${rot} ${cx} ${cy})"/>`;
  }).join('');
  return `
    <div class="tier-donut" aria-hidden="true">
      <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
        ${segs}
      </svg>
      <div class="tier-donut-icon tier-donut-icon--${escapeHtml(tier)}">${iconSVG}</div>
    </div>`;
}

export function renderModalLegend(legend, currentTier, tile) {
  if (!Array.isArray(legend) || legend.length === 0) return '';
  const rows = legend.map(l => {
    const isCurrent = l.tier === currentTier;
    return `
      <div class="modal-legend-row${isCurrent ? ' is-current' : ''}">
        <span class="modal-legend-dot dot-${escapeHtml(l.tier)}" aria-hidden="true"></span>
        <span class="modal-legend-text">${escapeHtml(l.text)}</span>
      </div>`;
  }).join('');
  const donut = renderTierDonut(tile);
  return `
    <div class="modal-legend" aria-label="Colour-coding criteria">
      <div class="modal-legend-body">
        <div class="modal-legend-title">Colour scale</div>
        ${rows}
      </div>
      ${donut}
    </div>`;
}

// Union of curated + auto-detected German terms for a tile.
// Curated list lives in TILE_GLOSSARY_KEYS[tile.key]; auto-detection scans
// the tile's user-facing text (explanation + caveat + sources) for any
// GLOSSARY key and adds it to the shown chip list. Case-insensitive
// substring match — GLOSSARY is a curated whitelist, so false positives
// only fire when a defined term legitimately appears in the tile's copy.
export function _detectGlossaryTerms(tile) {
  const curated = TILE_GLOSSARY_KEYS[tile.key] || [];
  const explanation = LENS_TILE_EXPLANATIONS[tile.key] || '';
  const caveat = tile.caveat || '';
  const sourcesText = Array.isArray(tile.sources) ? tile.sources.join(' ') : '';
  const haystack = (explanation + ' ' + caveat + ' ' + sourcesText).toLowerCase();
  const found = new Set(curated.filter(k => GLOSSARY[k]));
  for (const term of Object.keys(GLOSSARY)) {
    if (haystack.includes(term.toLowerCase())) found.add(term);
  }
  return Array.from(found);
}

export function renderModalGlossary(tile, terms) {
  const keys = Array.isArray(terms) ? terms : _detectGlossaryTerms(tile);
  const filtered = keys.filter(k => GLOSSARY[k]);
  if (filtered.length === 0) return '';
  const chips = filtered.map(k =>
      `<span class="glossary-word" data-glossary-term="${escapeHtml(k)}"` +
      ` tabindex="0" role="button" aria-label="Definition of ${escapeHtml(k)}">` +
      `${escapeHtml(k)}</span>`
    ).join(', ');
  return `
    <div class="modal-glossary" aria-label="German glossary for this tile">
      <div class="modal-glossary-list">${chips}</div>
    </div>`;
}

// Parse a provenance string into {publisher, department, dataset, license}.
// Patterns handled:
//   Berlin: "Geoportal Berlin / Kindertagesstätten (dl-de/by-2.0)"
//           → publisher=Geoportal Berlin, dataset=Kindertagesstätten, license=dl-de/by-2.0
//   Hamburg: "Freie und Hansestadt Hamburg / BUKEA — Straßenbaumkataster (dl-de/by-2-0)"
//           → publisher=Freie und Hansestadt Hamburg, department=BUKEA,
//             dataset=Straßenbaumkataster, license=dl-de/by-2-0
//   OSM:    "© OpenStreetMap contributors (ODbL) via Geofabrik"
//           → publisher=© OpenStreetMap contributors, dataset=via Geofabrik, license=ODbL
// Unparseable strings degrade to {publisher: <whole string>, license: ''}.
export function _parseSource(str) {
  if (!str) return { publisher: '', department: '', dataset: '', license: '' };
  // Extract trailing "(license)" if present.
  let head = str.trim();
  let license = '';
  const licenseMatch = head.match(/^(.*?)\s*\(([^()]+)\)\s*(via\s+.+)?$/i);
  let viaSuffix = '';
  if (licenseMatch) {
    head = licenseMatch[1].trim();
    license = licenseMatch[2].trim();
    viaSuffix = (licenseMatch[3] || '').trim();
  }
  // OSM path — starts with ©, may carry "via <source>" suffix.
  if (/^©/.test(head)) {
    return {
      publisher: head,
      department: '',
      dataset: viaSuffix,
      license,
    };
  }
  // Split on the first " / " for publisher | rest.
  const slashIdx = head.indexOf(' / ');
  if (slashIdx < 0) {
    return { publisher: head, department: '', dataset: viaSuffix, license };
  }
  const publisher = head.slice(0, slashIdx).trim();
  const rest = head.slice(slashIdx + 3).trim();
  // Hamburg pattern: "<publisher> / <department> — <dataset>".
  const emIdx = rest.indexOf(' — ');
  if (emIdx > 0) {
    return {
      publisher,
      department: rest.slice(0, emIdx).trim(),
      dataset: rest.slice(emIdx + 3).trim(),
      license,
    };
  }
  // Berlin pattern: "<publisher> / <dataset>".
  return { publisher, department: '', dataset: rest, license };
}

// Render the "About" tab as three labeled sections with rule dividers.
// Section 1 — "What this tells you": user-facing explanation + technical
//             caveat as a follow-on paragraph.
// Section 2 — "Data & attribution": one row per source, parsed into
//             Publisher / Department / Dataset / License. Absent fields
//             are skipped rather than showing empty labels.
// Section 3 — "German glossary": chip strip of every GLOSSARY term
//             detected in the tile's copy (union of curated + auto).
// Empty section 1 / 3 render a muted "—" placeholder so the 3-section
// layout stays constant across every tile. Section 2 is always populated
// (every tile carries at least one source).
export function renderModalAbout(tile) {
  const explanation = LENS_TILE_EXPLANATIONS[tile.key] || '';
  const caveat = tile.caveat || '';
  const sources = Array.isArray(tile.sources) ? tile.sources : [];
  const glossaryTerms = _detectGlossaryTerms(tile);

  const explBlock = explanation
    ? `<div class="modal-explanation">${escapeHtml(explanation)}</div>` : '';
  const caveatBlock = caveat
    ? `<div class="modal-caveat">${escapeHtml(caveat)}</div>` : '';
  const section1Body = (explBlock || caveatBlock)
    ? `${explBlock}${caveatBlock}`
    : `<div class="about-empty">—</div>`;

  const sourceRow = (label, val) => val
    ? `<div class="prov-row"><span class="prov-label">${label}</span>` +
      `<span class="prov-val">${escapeHtml(val)}</span></div>` : '';
  const parsedSources = sources.map(_parseSource);
  const sourcesHtml = parsedSources.length
    ? parsedSources.map((p, i) => {
        const rows =
          sourceRow('Publisher', p.publisher) +
          sourceRow('Department', p.department) +
          sourceRow('Dataset',   p.dataset) +
          sourceRow('Licence',   p.license);
        const sepClass = i > 0 ? ' prov-block-alt' : '';
        return `<div class="prov-block${sepClass}">${rows || sourceRow('Source', sources[i])}</div>`;
      }).join('')
    : `<div class="about-empty">—</div>`;

  const glossaryHtml = renderModalGlossary(tile, glossaryTerms)
    || `<div class="about-empty">—</div>`;

  return `
    <section class="modal-about" aria-label="About this tile">
      <div class="about-section">
        <h4 class="about-heading">What this tells you</h4>
        <div class="about-body">${section1Body}</div>
      </div>
      <hr class="about-divider" aria-hidden="true">
      <div class="about-section">
        <h4 class="about-heading">Data &amp; attribution</h4>
        <div class="about-body modal-provenance">${sourcesHtml}</div>
      </div>
      <hr class="about-divider" aria-hidden="true">
      <div class="about-section">
        <h4 class="about-heading">German glossary</h4>
        <div class="about-body">${glossaryHtml}</div>
      </div>
    </section>`;
}

export function renderLensSingle(addr) {
  const active = getActiveLens();
  const lens = addr && addr.lens && addr.lens[active];
  if (!lens || lens.error) {
    return `
      <div class="lens-picker-row">
        ${renderLensPicker(active)}
      </div>
      <div class="lens-empty">Lens unavailable for this address.</div>
    `;
  }
  const tilesHtml = lens.tiles.map(t => renderLensTile(t, active)).join('');
  const showAiPanel = _hasLensAI(active);
  const aiPanel = showAiPanel
    ? `<section class="lens-ai-panel" id="lens-ai-panel"
                data-lens="${escapeHtml(active)}"
                aria-label="AI Insight for the ${escapeHtml(lens.label || active)} lens">
         ${renderLensAIIdle(lens.label || active, lens.audience)}
       </section>` : '';
  const audience = escapeHtml(lens.audience || '');
  return `
    <div class="lens-picker-row">
      ${renderLensPicker(active)}
      ${(audience && !showAiPanel) ? `<p class="lens-audience">${audience}</p>` : ''}
    </div>
    ${aiPanel}
    <div class="lens-body">
      <div class="lens-tiles-col">
        <div class="lens-grid">${tilesHtml}</div>
        <div class="lens-modal" id="lens-modal" role="dialog"
             aria-modal="true" aria-labelledby="lens-modal-title" hidden></div>
      </div>
      <div class="lens-map-col">
        <div class="map-hint" id="lens-map-hint">Click a tile to plot its locations</div>
        <div id="lens-map"></div>
      </div>
    </div>
  `;
}

export function renderLensDot(tile, lensSlug) {
  if (!tile) {
    return `<button class="lens-compare-cell tier-unknown" type="button"
                    aria-label="unavailable" title="unavailable">•</button>`;
  }
  const tier = tile.tier || 'unknown';
  const short = escapeHtml(tile.rule + (tile.numeric ? ' — ' + tile.numeric : ''));
  const aria  = escapeHtml(tile.label + ', tier ' + tier + ': ' + tile.rule);
  return `<button class="lens-compare-cell tier-${escapeHtml(tier)}" type="button"
                  aria-label="${aria}" title="${short}"><span aria-hidden="true">●</span></button>`;
}

export function renderLensCompareMatrix(addresses, slug) {
  if (!addresses || !addresses.length) return '';
  const first = addresses.find(a => a && a.lens && a.lens[slug] && !a.lens[slug].error);
  if (!first) return `<div class="lens-empty">Lens unavailable for the current addresses.</div>`;
  const lens = first.lens[slug];
  const rowSpec = lens.tiles;
  const header = `
    <div class="lens-compare-row lens-compare-head">
      <div class="lens-compare-rowlabel"></div>
      ${addresses.map(a => `
        <div class="lens-compare-collabel">${escapeHtml(
          (a && a.shortLabel) ||
          (a && a.address && a.address.street) ||
          '—')}</div>
      `).join('')}
    </div>`;
  const rows = rowSpec.map(spec => {
    const cells = addresses.map(a => {
      const t = a && a.lens && a.lens[slug] && !a.lens[slug].error
              ? a.lens[slug].tiles.find(x => x.key === spec.key)
              : null;
      return `<div class="lens-compare-cellwrap">${renderLensDot(t, slug)}</div>`;
    }).join('');
    return `
      <div class="lens-compare-row">
        <div class="lens-compare-rowlabel">${escapeHtml(spec.label)}</div>
        ${cells}
      </div>`;
  }).join('');
  const audience = escapeHtml(lens.audience || '');
  const title = escapeHtml(lens.label || slug);
  return `
    <section class="lens-compare-section" data-slug="${escapeHtml(slug)}">
      <h3 class="lens-compare-section-title">${title}</h3>
      ${audience ? `<p class="lens-audience">${audience}</p>` : ''}
      <div class="lens-compare">${header}${rows}</div>
    </section>
  `;
}

export function renderLensCompare(addresses) {
  const active = getActiveLens();
  if (!addresses || !addresses.length) return '';
  const slides = LIFE_MODE_LENSES.map(lens => {
    const matrix = renderLensCompareMatrix(addresses, lens.slug);
    const hidden = lens.slug !== active ? 'hidden' : '';
    return `<div class="lens-compare-slide" data-slug="${escapeHtml(lens.slug)}" ${hidden}>${matrix}</div>`;
  }).join('');
  return `
    <div class="lens-picker-row no-print">
      ${renderLensPicker(active)}
    </div>
    <div class="lens-compare-body" data-active-lens="${escapeHtml(active)}">
      ${slides}
    </div>
  `;
}

function renderLensFeature(tileKey, feature, idx) {
  const details = _lensFeatureDetailHtml(tileKey, feature);
  const tip = details
    ? `<details class="info-tip"><summary aria-label="More info">${ico.info || 'ⓘ'}</summary><div class="info-body details-block">${details}</div></details>`
    : '';
  const dist = feature.distance_m != null
    ? `${feature.distance_m} m`
    : '';
  return `
    <li class="lens-feature" data-feature-idx="${idx}">
      <span class="feature-marker">${idx + 1}</span>
      <span class="feature-name">${escapeHtml(feature.name)}</span>
      <span class="feature-distance">${escapeHtml(dist)}</span>
      ${tip}
    </li>
  `;
}

function _lensFeatureDetailHtml(tileKey, f) {
  const rows = [];
  const row = (label, val) =>
    `<div class="det-row"><span class="det-label">${label}</span><span class="det-val">${val}</span></div>`;

  if (f.address)          rows.push(row('Address',   escapeHtml(f.address)));
  if (f.walk_min != null) rows.push(row('Walk time', `~${f.walk_min} min`));
  if (f.phone)            rows.push(row('Phone',
                              `<a href="tel:${escapeHtml(f.phone)}">${escapeHtml(f.phone)}</a>`));
  const websiteUrl = (typeof f.website === 'string') ? f.website.trim() : '';
  const websiteSafe = /^https?:\/\//i.test(websiteUrl) ? websiteUrl : '';
  if (websiteSafe)        rows.push(row('Website',
                              `<a href="${escapeHtml(websiteSafe)}" target="_blank" rel="noopener">Visit ↗</a>`));
  if (f.hours)            rows.push(row('Hours',     escapeHtml(f.hours)));
  if (f.wheelchair)       rows.push(row('Access',    'Step-free'));

  if (tileKey === 'kita') {
    if (f.traeger_name) {
      const suffix = f.operator_type ? ` <span class="dim">(${escapeHtml(f.operator_type)})</span>` : '';
      rows.push(row('Operator', escapeHtml(f.traeger_name) + suffix));
    } else if (f.operator_type) {
      rows.push(row('Operator', escapeHtml(f.operator_type)));
    }
    if (f.approach)              rows.push(row('Approach',  escapeHtml(f.approach)));
    if (f.capacity != null)      rows.push(row('Places',    `${f.capacity} <span class="dim">(total, not availability)</span>`));
  } else if (tileKey === 'playground') {
    if (f.area_m2 != null)       rows.push(row('Area',       `${f.area_m2} m²`));
    if (f.renovated_year != null) rows.push(row('Renovated', escapeHtml(String(f.renovated_year))));
  } else if (tileKey === 'transit') {
    if (f.modality)              rows.push(row('Mode',       escapeHtml(f.modality)));
  } else if (tileKey === 'rail_transit' || tileKey === 'tram_transit'
                                        || tileKey === 'bus_transit') {
    const _modeMap = {S: 'S-Bahn', U: 'U-Bahn', T: 'Tram', B: 'Bus'};
    const modeLabel = String(f.mode || '').split(',')
      .map(m => _modeMap[m.trim()] || m.trim())
      .filter(Boolean)
      .join(' · ');
    if (modeLabel)               rows.push(row('Mode',       escapeHtml(modeLabel)));
    if (f.distance_m != null)    rows.push(row('Distance',   `${f.distance_m} m`));
    if (Array.isArray(f.directions) && f.directions.length)
      rows.push(row(f.directions.length > 1 ? 'Directions' : 'Direction',
                    f.directions.map(escapeHtml).join(' · ')));
  } else if (tileKey === 'supermarket') {
    if (f.brand)                 rows.push(row('Brand',      escapeHtml(f.brand)));
    if (f.opening_hours)         rows.push(row('Hours',      escapeHtml(f.opening_hours)));
    if (f.organic)               rows.push(row('Organic',    'Yes'));
  } else if (tileKey === 'refuge') {
    if (f.size_ha != null)       rows.push(row('Size',       `${f.size_ha} ha`));
    if (f.kind)                  rows.push(row('Type',       escapeHtml(f.kind)));
  } else if (tileKey === 'parkzone') {
    // parkzone renders no per-item feature rows (the "feature" here is
    // the zone containing the address itself). All fields come from
    // tile.metadata.parkzone — handled in the modal body below, not
    // per-feature.
    return '';
  } else if (tileKey === 'xmas_market') {
    if (f.bezirk)                rows.push(row('Bezirk',     escapeHtml(f.bezirk)));
    if (f.opening_hours)         rows.push(row('Opening',    escapeHtml(f.opening_hours).replace(/\n/g, '<br>')));
    if (f.organiser)             rows.push(row('Organiser',  escapeHtml(f.organiser)));
    if (f.email)                 rows.push(row('Email',
                                      `<a href="mailto:${escapeHtml(f.email)}">${escapeHtml(f.email)}</a>`));
    if (typeof f.barrier_free === 'string'
        && f.barrier_free.trim().toLowerCase().startsWith('ja')) {
      rows.push(row('Access', escapeHtml(f.barrier_free)));
    }
    if (f.description)           rows.push(row('About',      escapeHtml(f.description)));
    if (f.detail_url && /^https?:\/\//i.test(f.detail_url)) {
      rows.push(row('Details',
        `<a href="${escapeHtml(f.detail_url)}" target="_blank" rel="noopener">Senate page ↗</a>`));
    }
  }

  return rows.join('');
}

function _renderSourceFreshness(sourceDates) {
  if (!Array.isArray(sourceDates) || sourceDates.length === 0) return '';
  const rows = sourceDates
    .filter(d => d && d.label && d.value)
    .map(d => `<div class="modal-freshness-row">`
      + `<span class="modal-freshness-label">${escapeHtml(d.label)}:</span> `
      + `<span class="modal-freshness-value">${escapeHtml(d.value)}</span>`
      + `</div>`)
    .join('');
  if (!rows) return '';
  return `<div class="modal-freshness">`
    + `<div class="modal-freshness-title">Last refreshed on</div>`
    + rows
    + `</div>`;
}

function renderLensTreesBlock(trees) {
  if (!trees) return '';
  const bits = [];
  if (trees.count != null)              bits.push(`${trees.count} street trees`);
  if (trees.crown_coverage_pct != null) bits.push(`${trees.crown_coverage_pct}% crown coverage`);
  if (trees.avg_age_yr != null)         bits.push(`avg age ${trees.avg_age_yr}y`);
  if (trees.tallest_m != null)          bits.push(`tallest ${trees.tallest_m}m`);
  if (bits.length === 0) return '';
  const species = Array.isArray(trees.top_species) && trees.top_species.length
    ? `Top: ${trees.top_species.slice(0, 3).map(s => escapeHtml(s.name)).join(', ')}`
    : '';
  return `
    <div class="modal-trees">
      <div class="modal-trees-summary">${bits.join(' · ')}</div>
      ${species ? `<div class="modal-trees-species">${species}</div>` : ''}
    </div>
  `;
}

function renderLensModalBody(tile, lensSlug) {
  const iconSVG = (typeof ico !== 'undefined' && ico[tile.icon]) || '';
  const isInfo  = true;
  const tier    = tile.tier || 'unknown';
  const badge   = tier === 'unknown' ? 'N/A' : tier.toUpperCase();
  const features = Array.isArray(tile.features) ? tile.features : [];
  const explanation = LENS_TILE_EXPLANATIONS[tile.key] || '';
  const trees = tile.metadata && tile.metadata.trees;

  // The "About" tab (caveat, explanation, provenance, glossary) is now
  // rendered as a single 3-section block via `renderModalAbout(tile)`.
  // Freshness metadata (source_dates) stays outside the About block for
  // now — its only current consumer is the xmas_market tile — but the
  // provenance rows inside About are the primary source citation.
  let emptyBody = '';
  if (!features.length) {
    if (tier === 'red' || tier === 'unknown') {
      if (!explanation) emptyBody = '<div class="modal-empty">No matching items nearby.</div>';
    } else if (!trees && !explanation) {
      emptyBody = '<div class="modal-empty">Match found nearby — per-location details unavailable.</div>';
    }
  }
  const featuresHtml = features.length
    ? `<ul class="modal-features-list">${
        features.map((f, i) => renderLensFeature(tile.key, f, i)).join('')
      }</ul>`
    : emptyBody;
  const treesHtml = renderLensTreesBlock(trees);
  const aboutHtml = renderModalAbout(tile);
  const freshnessHtml = _renderSourceFreshness(tile.source_dates);

  let cardRichBlock = '';
  if (tile.key === 'parkzone') {
    const pz = (tile.metadata && tile.metadata.parkzone) || null;
    if (pz) {
      const row = (label, val) => val
        ? `<div class="det-row"><span class="det-label">${label}</span><span class="det-val">${escapeHtml(String(val))}</span></div>`
        : '';
      let rows = '';
      if (pz.inside) {
        rows += row('Zone',           pz.zone);
        rows += row('Bezirk',         pz.bezirk);
        rows += row('Enforcement',    pz.zeiten);
        rows += row('Visitor fee',    pz.gebuehr ? `${pz.gebuehr} / hour` : '');
        rows += row('Notes',          pz.bemerkung);
      } else {
        rows += row('Regime',           'outside all paid parking zones');
        if (pz.nearest_zone) {
          rows += row('Nearest zone',   `Zone ${pz.nearest_zone} (${pz.nearest_bezirk || ''})`.trim());
        }
        if (pz.nearest_edge_m != null) {
          rows += row('Distance to edge', `${pz.nearest_edge_m} m`);
        }
      }
      if (rows) {
        cardRichBlock = `<div class="parkzone-modal-block">${rows}</div>`;
      }
    }
  } else if (tile.key === 'gesix' || tile.key === 'gesix_newcomer'
      || tile.key === 'gesix_quiet' || tile.key === 'gesix_commuter') {
    const g = (tile.metadata && tile.metadata.gesix) || null;
    const q = g && g.quintile_5;
    const segs = [1,2,3,4,5].map(i => {
      const active = q === i ? ' active' : '';
      const grade = i <= 2 ? ' seg-good' : i === 3 ? ' seg-mid' : ' seg-bad';
      return `<span class="gesix-seg${grade}${active}" aria-hidden="true"></span>`;
    }).join('');
    const plr = g?.plr_name ? `<div class="gesix-plr">${escapeHtml(g.plr_name)}</div>` : '';
    const rank = (g?.rang != null && g?.total)
      ? `<div class="gesix-rank">Rank ${g.rang} of ${g.total} Planungsräume citywide</div>` : '';
    cardRichBlock = `
      <div class="gesix-modal-block">
        ${plr}
        ${rank}
        <div class="gesix-bar gesix-bar-large" role="img" aria-label="Quintile ${q || 'unknown'} of 5">
          <div class="gesix-track gesix-quintile-bar">${segs}</div>
          <div class="gesix-scale"><span>Top 20%</span><span>Bottom 20%</span></div>
        </div>
      </div>`;
  } else if (tile.key === 'sozialmonitoring_status'
      || tile.key === 'sozialmonitoring_gesamt'
      || tile.key === 'sozialmonitoring_status_commuter'
      || tile.key === 'sozialmonitoring_gesamt_commuter'
      || tile.key === 'sozialmonitoring_status_quiet') {
    // Hamburg Sozialmonitoring shape-only tiles — render the sm dict as a
    // definition list so the modal has real content instead of just the
    // "tap for detail" rule string. Mirrors the `.gesix-modal-block`
    // pattern above but without the 5-quintile bar (HH publishes 4-band
    // Statusindex + 2-band Gesamtindex, not a quintile).
    const sm = (tile.metadata && tile.metadata.sozialmonitoring) || null;
    if (sm) {
      const row = (label, val) => val
        ? `<div class="det-row"><span class="det-label">${label}</span><span class="det-val">${escapeHtml(String(val))}</span></div>`
        : '';
      let rows = '';
      rows += row('Stadtteil',    sm.stadtteil);
      rows += row('Statusindex',  sm.statusindex);
      rows += row('Gesamtindex',  sm.gesamtindex);
      rows += row('Dynamikindex', sm.dynamikindex);
      rows += row('Statistisches Gebiet', sm.statgeb);
      rows += row('Berichtsjahr', sm.berichtsjahr);
      if (rows) {
        cardRichBlock = `<div class="sozialmonitoring-modal-block">${rows}</div>`;
      }
    }
  }

  return `
    <button class="lens-modal-close" aria-label="Close details" type="button">✕</button>
    <div class="modal-head">
      <span class="icon-badge${isInfo ? '' : ` tier-${escapeHtml(tier)}`}" aria-hidden="true">${iconSVG}</span>
      <h3 id="lens-modal-title">${labelWithGlossHtml(tile.label)}</h3>
      ${isInfo ? '' : `<span class="tile-tier-badge tier-${escapeHtml(tier)}">${escapeHtml(badge)}</span>`}
    </div>
    <div class="modal-rule">${escapeHtml(tile.rule || '')}</div>
    ${tile.numeric ? `<div class="modal-numeric">${escapeHtml(tile.numeric)}</div>` : ''}
    ${renderModalLegend(tile.legend, tier, tile)}
    ${cardRichBlock}
    ${featuresHtml}
    ${treesHtml}
    ${aboutHtml}
    ${freshnessHtml}
  `;
}

function _injectModalTabs(modal) {
  if (modal.querySelector('.modal-tabbar')) return;   // idempotent
  const head = modal.querySelector('.modal-head');
  if (!head) return;

  const hasReadout = !!(
    modal.querySelector('.modal-rule') ||
    modal.querySelector('.modal-numeric') ||
    modal.querySelector('.modal-legend') ||
    modal.querySelector('.modal-features-list') ||
    modal.querySelector('.modal-trees') ||
    modal.querySelector('.gesix-modal-block') ||
    modal.querySelector('.parkzone-modal-block') ||
    modal.querySelector('.sozialmonitoring-modal-block')
  );
  // About tab is now always emitted as a single `.modal-about` wrapper
  // (see renderModalAbout). Empty sections render `—` placeholders, so
  // presence of the wrapper is a reliable signal that the About tab has
  // content worth showing.
  const hasAbout = !!modal.querySelector('.modal-about');

  const available = [
    hasReadout && { id: 'readout', label: 'Readout' },
    hasAbout   && { id: 'about',   label: 'How this works' },
  ].filter(Boolean);
  if (available.length < 2) return;

  const TAB_ICONS = {
    readout: '<svg viewBox="0 0 256 256" aria-hidden="true"><path d="M232,208H24V48H232Z" opacity="0.2"/><line x1="24" y1="128" x2="72" y2="80" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><line x1="72" y1="80" x2="128" y2="136" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><line x1="128" y1="136" x2="192" y2="72" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><polyline points="152 72 192 72 192 112" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><line x1="24" y1="208" x2="232" y2="208" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>',
    about:   '<svg viewBox="0 0 256 256" aria-hidden="true"><circle cx="128" cy="128" r="96" opacity="0.2"/><circle cx="128" cy="128" r="96" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><polyline points="120 120 128 120 128 176 136 176" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><circle cx="126" cy="84" r="10"/></svg>',
  };
  const tabs = document.createElement('nav');
  tabs.className = 'modal-tabbar';
  tabs.setAttribute('role', 'tablist');
  tabs.innerHTML = available.map((t, i) =>
    `<button type="button" class="modal-tab${i === 0 ? ' active' : ''}"` +
    ` data-modal-tab="${t.id}" role="tab" aria-selected="${i === 0}">` +
    `<span class="modal-tab-icon" aria-hidden="true">${TAB_ICONS[t.id] || ''}</span>` +
    `<span class="modal-tab-label">${t.label}</span>` +
    `</button>`
  ).join('');
  head.after(tabs);

  modal.classList.add('has-tabs');
  modal.setAttribute('data-tab', available[0].id);

  tabs.querySelectorAll('.modal-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      const t = btn.dataset.modalTab;
      modal.setAttribute('data-tab', t);
      tabs.querySelectorAll('.modal-tab').forEach(b => {
        const on = b === btn;
        b.classList.toggle('active', on);
        b.setAttribute('aria-selected', on ? 'true' : 'false');
      });
    });
  });
}

function _wrapSidebarPanelCol(modal) {
  let col = modal.querySelector(':scope > .modal-panel-col');
  if (!col) {
    col = document.createElement('div');
    col.className = 'modal-panel-col';
  }
  const skip = new Set(['modal-head', 'modal-tabbar', 'lens-modal-close',
                        'glossary-popup', 'modal-panel-col']);
  const movers = Array.from(modal.children).filter(el =>
    ![...el.classList].some(c => skip.has(c))
  );
  movers.forEach(el => col.appendChild(el));
  if (!col.parentNode) modal.appendChild(col);
}

function _wireGlossaryPopups(modal) {
  const words = modal.querySelectorAll('.glossary-word');
  if (!words.length) return;

  let popup = modal.querySelector('.glossary-popup');
  if (!popup) {
    popup = document.createElement('div');
    popup.className = 'glossary-popup';
    popup.id = 'glossary-popup';
    popup.setAttribute('role', 'tooltip');
    popup.setAttribute('hidden', '');
    popup.innerHTML = `
      <div class="glossary-popup-term"></div>
      <div class="glossary-popup-def"></div>`;
    modal.appendChild(popup);
  }
  const popupTerm = popup.querySelector('.glossary-popup-term');
  const popupDef  = popup.querySelector('.glossary-popup-def');
  let activeWord  = null;

  const showFor = (word) => {
    const term = word.dataset.glossaryTerm;
    const def  = GLOSSARY[term];
    if (!def) return;
    popupTerm.textContent = term;
    popupDef.textContent  = def;
    popup.hidden = false;
    word.setAttribute('aria-describedby', popup.id);
    activeWord = word;
    const wr = word.getBoundingClientRect();
    const mr = modal.getBoundingClientRect();
    const pw = popup.offsetWidth;
    const ph = popup.offsetHeight;
    let left = wr.left - mr.left + modal.scrollLeft + (wr.width / 2) - (pw / 2);
    left = Math.max(12, Math.min(left, mr.width - pw - 12));
    const spaceAbove = wr.top - mr.top;
    const yBase = modal.scrollTop;
    let top;
    if (spaceAbove >= ph + 10) top = (wr.top - mr.top) + yBase - ph - 8;
    else                       top = (wr.bottom - mr.top) + yBase + 8;
    popup.style.left = `${left}px`;
    popup.style.top  = `${top}px`;
  };
  const hide = () => {
    popup.hidden = true;
    if (activeWord) {
      activeWord.removeAttribute('aria-describedby');
      activeWord = null;
    }
  };

  words.forEach(word => {
    if (word.dataset.glossaryWired === '1') return;
    word.dataset.glossaryWired = '1';

    word.addEventListener('mouseenter', () => showFor(word));
    word.addEventListener('mouseleave', hide);
    word.addEventListener('focus',      () => showFor(word));
    word.addEventListener('blur',       hide);
    word.addEventListener('click', (e) => {
      e.stopPropagation();
      if (popup.hidden || popup.dataset.forTerm !== word.dataset.glossaryTerm) {
        popup.dataset.forTerm = word.dataset.glossaryTerm;
        showFor(word);
      } else {
        hide();
      }
    });
    word.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        e.preventDefault();
        hide();
        word.blur();
      }
    });
  });
}

export function openLensModal(tileKey) {
  if (!S.eduData || !S.eduData.lens) return;
  const active = getActiveLens();
  const lens = S.eduData.lens[active];
  if (!lens || !lens.tiles) return;
  const tile = lens.tiles.find(t => t.key === tileKey);
  if (!tile) return;
  _track('card_open', { lens: active, card: tileKey, tier: tile.tier });

  const modal = document.getElementById('lens-modal');
  if (!modal) return;
  modal.innerHTML = renderLensModalBody(tile, active);
  modal.hidden = false;
  S.lensLastTileKey = tileKey;

  _injectModalTabs(modal);
  _wireGlossaryPopups(modal);

  if (modal.classList.contains('has-tabs')) {
    modal.classList.add('sidebar-layout');
    _wrapSidebarPanelCol(modal);
  }

  const closeBtn = modal.querySelector('.lens-modal-close');
  if (closeBtn) closeBtn.focus();

  _updateLensMapPins(tile);

  S.lensMapFeaturePins.forEach(marker => {
    marker.off('click');
    marker.on('click', () => _highlightLensRow(marker._lensFeatureIdx));
  });
}

export function closeLensModal() {
  const modal = document.getElementById('lens-modal');
  if (!modal || modal.hidden) return;
  modal.hidden = true;
  modal.innerHTML = '';
  modal.classList.remove('has-tabs');
  modal.removeAttribute('data-tab');
  dropOrphanTooltips();
  if (S.lensMap) {
    S.lensMapFeaturePins.forEach(m => { try { S.lensMap.removeLayer(m); } catch (e) {} });
    S.lensMapFeaturePins = [];
    if (S.lensAddressMarker) {
      S.lensMap.setView(S.lensAddressMarker.getLatLng(), 14);
    }
  }
  const hint = document.getElementById('lens-map-hint');
  if (hint) hint.textContent = 'Click a tile to plot its locations';
  if (S.lensLastTileKey) {
    const tile = document.querySelector(`.lens-tile[data-tile-key="${S.lensLastTileKey}"]`);
    if (tile) tile.focus();
  }
  S.lensLastTileKey = null;
}

function _highlightLensRow(idx) {
  const row = document.querySelector(`.lens-feature[data-feature-idx="${idx}"]`);
  if (!row) return;
  row.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  row.classList.add('highlighted');
  setTimeout(() => row.classList.remove('highlighted'), 900);
}

export function renderAllPanels() {
  const onLife = document.body.classList.contains('life-mode');
  let lensEl = document.getElementById('lens-view');
  if (!lensEl) {
    lensEl = document.createElement('div');
    lensEl.id = 'lens-view';
    const panelConn = document.getElementById('panel-conn');
    if (panelConn && panelConn.parentNode) {
      panelConn.parentNode.insertBefore(lensEl, panelConn.nextSibling);
    } else {
      const viewMain = document.getElementById('view-main');
      if (viewMain) viewMain.appendChild(lensEl);
    }
  }
  dropOrphanTooltips();
  if (onLife) {
    lensEl.innerHTML = S.eduData ? renderLensSingle(S.eduData) : '';
    if (S.eduData && S.eduData.address && document.getElementById('lens-map')) {
      initLensMap(S.eduData.address);
    }
    if (S.eduData) { hydrateLensAIPanel(S.eduData); }
  } else {
    if (S.lensMap) {
      try { S.lensMap.remove(); } catch (e) {}
      S.lensMap = null;
      S.lensAddressMarker = null;
      S.lensMapFeaturePins = [];
    }
    lensEl.innerHTML = '';
  }
  const toggle = document.getElementById('life-mode-toggle');
  if (toggle) {
    const focused = S.eduData || null;
    if (focused && !isAnyLensAvailable(focused)) {
      toggle.setAttribute('disabled', 'true');
      toggle.setAttribute('title', 'Lens unavailable for this address');
    } else {
      toggle.removeAttribute('disabled');
      toggle.removeAttribute('title');
    }
  }
}

export function setLifeMode(on) {
  const btn = document.getElementById('life-mode-toggle');
  document.body.classList.toggle('life-mode', on);
  btn.classList.toggle('on', on);
  btn.setAttribute('aria-pressed', on ? 'true' : 'false');
  btn.setAttribute('aria-label', on
    ? 'Life Lens on (toggle to switch off)'
    : 'Life Lens off (toggle to switch on)');
  try { localStorage.setItem(LM_STATE_KEY, on ? 'on' : 'off'); } catch (e) {}
  const modal = document.getElementById('lens-modal');
  if (modal && !modal.hidden) closeLensModal();
  dropOrphanTooltips();
  renderAllPanels();
  if (location.hash === '#compare') {
    import('../compare.js').then(m => m.renderCompare());
  }
}

export function initLifeMode() {
  const btn = document.getElementById('life-mode-toggle');
  if (!btn) return;

  let saved = null;
  try { saved = localStorage.getItem(LM_STATE_KEY); } catch (e) {}
  setLifeMode(saved === 'on');

  let seen = null;
  try { seen = localStorage.getItem(LM_SEEN_KEY); } catch (e) {}
  const stopPulse = () => {
    btn.classList.remove('pulse');
    try { localStorage.setItem(LM_SEEN_KEY, '1'); } catch (e) {}
  };
  if (!seen) {
    btn.classList.add('pulse');
    setTimeout(stopPulse, LM_PULSE_MS);
  }

  btn.addEventListener('click', () => {
    stopPulse();
    setLifeMode(!document.body.classList.contains('life-mode'));
  });

  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.lens-picker [data-lens]');
    if (btn) setActiveLens(btn.dataset.lens);
  });
}

// -- Delegated lens modal handlers (idempotency-guarded) --------------------
// ES-module dedupe already prevents double-install under normal loading; this
// guard is belt-and-braces for a URL-diverged double-load (e.g. mismatched ?v=).
if (!window.__lensListenersInstalled) {
  window.__lensListenersInstalled = true;
  document.addEventListener('click', (e) => {
    if (e.target.closest('.lens-modal-close')) {
      closeLensModal();
      return;
    }
    const modal = document.getElementById('lens-modal');
    if (modal && !modal.hidden && e.target === modal) {
      closeLensModal();
      return;
    }
    const featureRow = e.target.closest('.lens-feature');
    if (featureRow && !e.target.closest('.info-tip')) {
      const idx = parseInt(featureRow.dataset.featureIdx, 10);
      if (!Number.isNaN(idx) && S.lensMap && S.lensMapFeaturePins[idx]) {
        const marker = S.lensMapFeaturePins[idx];
        S.lensMap.setView(marker.getLatLng(), Math.max(S.lensMap.getZoom(), 16), { animate: true });
        marker.openPopup();
        _highlightLensRow(idx);
      }
      return;
    }
    const tile = e.target.closest('.lens-tile');
    if (tile) {
      const key = tile.dataset.tileKey;
      if (key) openLensModal(key);
      return;
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    const modal = document.getElementById('lens-modal');
    if (modal && !modal.hidden) closeLensModal();
  });
}
