# Contributing to AddrLens

Thanks for your interest. AddrLens is a solo project today; contributions are welcome but the review bandwidth is one person's evenings, so please read this document before opening a PR so we don't waste each other's time.

## What contributions land quickly

- **Bug reports** with a reproducer URL (e.g. an addrlens.de query that shows the bug). File as an [Issue](https://github.com/saptadip/addrlens/issues).
- **Documentation fixes** — typos, outdated command lines, unclear playbook steps.
- **New Berlin open datasets** that fit an existing tile (e.g. adding a fresh Umweltatlas layer to the Environment tab).
- **Accessibility improvements** — screen-reader landmarks, keyboard nav, contrast fixes.
- **Data-source resilience** — snapshot fallbacks, error handling for slow WFS endpoints, better cache eviction rules.

## What needs discussion first

Please open an Issue and let's talk before writing the code, otherwise the PR may need a rewrite:

- **New lenses** (a lens is a curated tile bundle for a specific life situation — Student, Senior, etc.). Adding one touches the scorer, city config, inference templates, frontend picker, and tests. Design first.
- **New cities.** The architecture supports it (each city is a `CityConfig` in `app/cities/<slug>.py`) but each additional city needs data-source research, glossary translation, and boot-time WFS discovery.
- **Any change to `provenance` payloads.** Every response carries dataset attributions; changes must keep licence tags visible per §14 of the [product doc](docs/product/product-brief.md).
- **Breaking changes to the JSON API** at `/api/lookup`, `/api/history`, `/api/card_insight`.

## Development setup

See the **Local development** section of the [README](README.md). Two paths, both work.

For an isolated iteration on a single module, the pure `__main__` selfcheck at the bottom of most files runs sub-second and needs no network:

```bash
cd v0.1
python -m app.core.scorer
python -m app.core.rate_limit
python -m app.core.address_index
python -m app.routes.card_insight
python -m inference.templates.history
python -m inference.runtime.cloudflare_backend
```

Every module you touch should have its `__main__` block re-run and still pass.

## Code style

### Python

- **Stdlib + Shapely + FastAPI + httpx + friends only.** No ORM, no ML frameworks in the app path, no build step.
- **Frozen dataclasses** for anything the app treats as immutable (see `CityConfig`, `LensTileConfig`).
- **`ponytail:` comments** mark deliberate simplifications that have a known upgrade path. Do not strip them; only remove one with a real reason (a bug, a metric, a user complaint).
- **Behaviour parity with `phase3/server.py`** is a hard constraint for modules ported from that tree. If you touch `app/core/*` or a route, check the corresponding phase3 function and preserve response shape unless an Issue explicitly authorises a change.
- **No unhandled exceptions in routes.** Wrap external calls in a scoped `try/except` and translate to HTTPException with a specific status code + a plain-English detail.
- **No comments explaining WHAT well-named code already says.** Only WHY — a subtle invariant, a workaround, or a non-obvious constraint. Docstrings should explain the *contract*, not the implementation.

### JavaScript

- **Vanilla JS, no framework, no bundler.** Direct DOM manipulation is fine.
- **`escapeHtml()` on every user-derived string** before insertion into `innerHTML`. If it can carry an apostrophe or an angle bracket, escape it.
- **Cache-buster query strings** on `app.js` and `app.css` must be bumped whenever either file changes. Format: `v=YYYYMMDDx` where `x` cycles a-z within a day.
- **New event tracking** goes through `_track()`, not directly to `window.umami`. Keeps the analytics guarded when running locally without Umami.

### CSS

- **Design tokens** live in `web/static/app.css` under `:root {...}`. Prefer tokens over hardcoded colours.
- **`.info-tip` pattern** for click-to-open popovers (see how the Kita ⓘ button and the Locality pill use it). The portal + auto-flip + scroll-anchor logic is centralised; new consumers get all of it for free.

### Commits

- **Conventional commit prefix**: `feat:`, `fix:`, `docs:`, `deploy:`, `analytics:`, `web:`, `legal:`, `chore:`.
- **Subject in imperative mood**, ≤72 characters.
- **Body optional but preferred**: explain the *why* if it isn't obvious. If a change fixes a subtle bug or reverses an earlier decision, capture the reasoning so future-you doesn't re-litigate it.
- **Co-author trailer** for AI-assisted changes:
  ```
  Co-Authored-By: <name> <no-reply@example>
  ```

## Selfchecks required before opening a PR

Minimum bar:

```bash
cd v0.1
python -m app.core.scorer            # pure — must pass
python -m app.core.rate_limit         # pure — must pass
python -m app.core.address_index      # pure — must pass
python -m app.routes.card_insight     # pure — must pass
```

If your change touches a route or an `Index` loader, also run the live selfcheck (needs `gdi.berlin.de` reachable):

```bash
python -m app.selfcheck
```

If it touches an inference template:

```bash
python -m inference.templates.<template_name>
```

## Pull request template

Please answer these in the PR description:

1. **What does this change?** One or two sentences.
2. **Why now?** Bug report, feature request, opportunity — link the Issue if there is one.
3. **What did you test?** Which selfchecks, which browser interactions, which endpoints.
4. **Anything reviewer should look at closely?** Areas of uncertainty, alternative approaches you considered.
5. **Screenshots?** For any visible UI change, a before / after screenshot. Bonus: mobile.

## Reporting security issues

Please **do not open a public Issue** for security vulnerabilities. Email `sapta@addrlens.de` with:

- A clear description of the vulnerability
- Steps to reproduce
- Suggested severity (low / medium / high)

I aim to acknowledge within 72 hours and to ship a fix within 2 weeks for anything actionable.

## Code of conduct

Be kind. Assume good faith. This is a public-interest project for people evaluating where to live — the audience is often stressed and making a big decision. Keep that context in mind in review discussions.

## Licence agreement

By submitting a contribution, you agree that it will be released under the same [MIT licence](LICENSE) as the rest of the repository.
