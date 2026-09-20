/**
 * Renders a header pill linking to sister cities.
 * Expects `cfg.other_cities` from /api/config; excludes the current city.
 * Called once by app.js after /api/config resolves.
 */
export function renderCitySwitch(cfg) {
  const others = (cfg.other_cities || []).filter(c => c.slug !== cfg.slug);
  if (!others.length) return;
  const container = document.querySelector('.logo') || document.querySelector('header');
  if (!container) return;
  const pill = document.createElement('div');
  pill.className = 'city-switch';
  pill.style.cssText = 'display:inline-flex;gap:8px;margin-left:12px;font-size:12px;';
  for (const c of others) {
    const a = document.createElement('a');
    a.href = c.url;
    a.textContent = `Also live in ${c.display_name} →`;
    a.style.cssText = 'padding:4px 10px;border:1px solid currentColor;border-radius:12px;text-decoration:none;color:inherit;';
    pill.appendChild(a);
  }
  container.parentNode.insertBefore(pill, container.nextSibling);
}
