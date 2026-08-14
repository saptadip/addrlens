# Legal Pages — Impressum & Datenschutzerklärung

Templates for the two legal pages required to run a public URL in Germany:

- `impressum.md` — §5 DDG (Digitale-Dienste-Gesetz) provider identification
- `datenschutzerklaerung.md` — DSGVO / GDPR privacy policy

Both files are bilingual (German first — legally authoritative in Germany —
followed by an English translation for international visitors).

## ⚠️ Important legal caveat

**These are professionally structured templates, not legal advice.** German
compliance case law shifts; before publishing:

1. Have a German lawyer or a legal-compliance service (Kanzlei WBS,
   activeMind.legal, e-recht24.de Premium) review the finalised text.
2. Verify that all placeholder values match your reality *exactly*. False
   or missing Impressum data is a §5 DDG violation and a common target
   for Abmahnung trolls (typical cost €500-2000).
3. Re-review annually or after material changes to processing (adding
   analytics, contact forms, third-party services, etc).

## Placeholder checklist

Fill every `{{TOKEN}}` in both files before publishing:

| Token | Meaning | Example |
|-------|---------|---------|
| `{{FULL_NAME}}` | Your full legal name (private person operator) | `Saptadip Sarkar` |
| `{{POSTAL_STREET_HNR}}` | Street + house number | `Beispielstr. 12` |
| `{{POSTAL_PLZ_CITY}}` | Postal code + city | `10435 Berlin` |
| `{{EMAIL}}` | Dedicated public contact address (not your work email) | `kontakt@addrlens.de` |
| `{{DOMAIN}}` | The site's domain, no scheme | `addrlens.de` |
| `{{PRODUCT_NAME}}` | Public-facing product name | `Berlin Address Intelligence` |
| `{{HOSTING_PROVIDER}}` | Hosting company legal name + address | `Hetzner Online GmbH, Industriestr. 25, 91710 Gunzenhausen` |
| `{{ANALYTICS_PROVIDER}}` | Analytics service or "none" | `Plausible Insights OÜ, Estonia` or `none` |
| `{{ERROR_TRACKING}}` | Error-tracking service or "none" | `Functional Software Inc. (Sentry), USA` or `none` |
| `{{INFERENCE_HOST}}` | Where your LLM runs | `self-hosted on the same server` or `Anthropic, USA` |
| `{{RESPONSIBLE_NAME}}` | Responsible party under §18 Abs. 2 MStV — usually same as `{{FULL_NAME}}` | `Saptadip Sarkar` |

Optional but recommended:

- **Dedicated email domain.** Do not use your work email (`@beyonnex.io`)
  or a personal ISP email. Get a mailbox on the product domain. Most
  registrars include one free. Reduces spam + separates concerns +
  looks professional.
- **PO Box vs home address.** German Impressum requires a real postal
  address at which service of process is possible. A P.O. Box alone is
  not sufficient. If you do not want your home address public, consider
  a Firmensitz service (~€10-30/month) that provides a legal address.

## Deployment notes

The current SPA (`v0.1/web/index.html`) does not have a footer with legal
links. Add before soft launch:

```html
<footer class="legal-footer">
  <a href="/impressum">Impressum</a> ·
  <a href="/datenschutzerklaerung">Datenschutz</a>
</footer>
```

The two pages can be served either as:

- Static HTML mounted under `/impressum` and `/datenschutzerklaerung`
  by FastAPI's `StaticFiles`, OR
- Simple SPA routes rendering the markdown converted to HTML at build time.

Static HTML is simpler for pages that rarely change. The markdown here is
the source of truth; convert with `pandoc` or any renderer, or paste the
translated content into a small HTML shell.

## Accessibility

Both pages must be reachable within two clicks from any page (§5 DDG has
been read strictly by courts). Footer link on every page is the
convention.

## Version history

| Date | Change |
|------|--------|
| 2026-08-14 | Initial templates created |
