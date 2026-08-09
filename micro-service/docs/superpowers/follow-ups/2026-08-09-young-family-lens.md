# Young Family lens — deferred follow-ups

**Source:** captured from the SDD progress ledger before its workspace was deleted after the final whole-branch review of Spec A (commit range `a0cf987..a2f87de`, final review verdict: MERGE).

Every item below was triaged as **Minor** by the final code-reviewer or during task-level reviews. None blocked shipping. Pick them up opportunistically or bundle them into a small polish PR.

---

## 1. Life Mode compare view: Export PDF button is a silent no-op

**Where:** `web/static/app.js:1390` (render), `web/static/app.js:1405-1416` (handler-bind returns early)

**Symptom:** The Life Mode compare header still renders an `#export-pdf-btn` button, but the click-handler bind lives inside the non-Life-Mode branch of `renderCompare()` — which returns early when Life Mode is on. Result: the button paints, clicks do nothing.

**Fix:** hoist the `#export-pdf-btn` listener into a shared post-render step that runs regardless of mode, OR omit the button from the Life Mode compare header. Either lands one commit.

## 2. Life Mode compare branch attaches a listener to elements it never renders

**Where:** `web/static/app.js:1407-1414`

**Symptom:** In the Life Mode compare branch, `renderCompare()` queries `.col-remove` and `#clear-all-btn`. `renderLensCompare()` emits neither. `.col-remove` is a real dead selector; `#clear-all-btn` is in the surrounding header and works, but the query in this branch is unnecessary duplication of what the outer render already wires.

**Fix:** drop the `.col-remove` line entirely; keep the `#clear-all-btn` line only if it's actually needed here (verify by reading the outer render).

## 3. Compare column labels are ambiguous for same-street addresses

**Where:** `web/static/app.js:2005-2006`

**Symptom:** `renderLensCompare()` builds column headers from `snap.address.street` (Life Mode branch) or the equivalent short label (raw branch). Two saved addresses at different house numbers on the same street render as visually identical columns.

**Fix:** include `hnr` in the label (e.g., `"Kastanienallee 12"` instead of `"Kastanienallee"`). Trim to fit if the compare grid is space-constrained.

## 4. `renderLensTile` aria-label pre-escapes a concatenated string

**Where:** `web/static/app.js` inside `renderLensTile(tile)` (the `ariaLabel` construction line — around 1923)

**Symptom:** `escapeHtml` is applied to the *concatenated* `label + ', tier ' + tier + ': ' + rule` string. Safe (no XSS, HTML entities decoded correctly by screen readers), but stylistically the brief-derived version escaped each field independently before concatenation, which is easier to reason about.

**Fix:** apply `escapeHtml` per field and drop the pre-computed `ariaLabel` variable. Purely cosmetic.

## 5. Outer `#lens-view` wrapper is not CSS-hidden when Life Mode is OFF

**Where:** `web/static/app.css` (`.lens-view` visibility rules) + `web/static/app.js` (`renderAllPanels()`)

**Symptom:** `body:not(.life-mode) .lens-view { display:none }` hides the inner `.lens-view` div built by `renderLensSingle`, but the outer `#lens-view` container stays in the DOM with `display: block`. When Life Mode is OFF, `renderAllPanels()` clears its `innerHTML`, so it renders as an empty invisible block — no visible artifact, but a minor inconsistency between the CSS comment ("hide lens content") and the actual target.

**Fix:** add `body:not(.life-mode) #lens-view { display:none }` for symmetry, OR always set `lensEl.style.display` in `renderAllPanels()`. Either is one line.

## 6. Live selfcheck kita-green asserts lack graceful-skip wrapper

**Where:** `app/selfcheck.py:254-260`

**Symptom:** The Kastanienallee kita-green assert and the "at least one tile is green" defensive check do not have the "skipped: <reason>" graceful-degrade wrapper that the spec calls out for the live block (compare with the Kurfürstendamm noise assert at `app/selfcheck.py:220-226`). If the Berlin Kita WFS goes flaky at test time, these hard-fail the whole selfcheck instead of printing "skipped" and continuing.

**Fix:** wrap the kita-green assertions with a "skipped if empty" guard mirroring the noise pattern. Low probability trip in practice.
