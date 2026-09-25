// EN-primary landing i18n toggle. Persists selection in localStorage['addrlens.lang'].
// Loaded from index.html, impressum.html, datenschutzerklaerung.html — same behavior
// across all landing surfaces. English default; DE toggle.
(function () {
  const KEY = 'addrlens.lang';
  const stored = localStorage.getItem(KEY) || 'en';
  const html = document.documentElement;
  const btn = document.getElementById('lang-toggle');
  if (!btn) return;

  function apply(lang) {
    html.lang = lang;
    document.querySelectorAll('[data-lang]').forEach(function (el) {
      el.hidden = el.dataset.lang !== lang;
    });
    btn.textContent = lang === 'en' ? 'DE' : 'EN';
    btn.setAttribute('aria-label', lang === 'en' ? 'Auf Deutsch umschalten' : 'Switch to English');
  }

  apply(stored);
  btn.addEventListener('click', function () {
    const next = html.lang === 'en' ? 'de' : 'en';
    localStorage.setItem(KEY, next);
    apply(next);
  });
})();
