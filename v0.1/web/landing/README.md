# web/landing/

Assets served by the `app-landing` container at `addrlens.de` (apex).

## Files

- `index.html` — landing page, EN-primary with DE toggle
- `impressum.html`, `datenschutzerklaerung.html` — apex-scoped legal pages
- `robots.txt`, `sitemap.xml` — apex crawler + SEO surface
- `static/landing.css` — landing-only stylesheet
- `static/img/{logo,favicon,og-image,berlin-card,hamburg-card}.png` — assets
- `static/fonts/*.woff2` — copies of `web/static/fonts/*` (Inter + Space Grotesk)

## Coupling with the CF Redirect Rule

The Cloudflare Redirect Rule at the apex (see `ops/cloudflared/README.md`)
maintains a **deny-list of paths that should NOT redirect** to
`berlin.addrlens.de`. The deny-list includes:
- `/`, `/impressum`, `/datenschutzerklaerung`, `/robots.txt`, `/sitemap.xml`, `/health`
- Exact filenames under `/static/img/`: `logo.png`, `og-image.jpg`, `favicon.png`, `berlin-card.png`, `hamburg-card.png`
- `starts_with(/static/fonts/)`, `starts_with(/static/landing.css)`

**If you add, remove, or rename any landing asset served under `/static/`,
you MUST update the CF Redirect Rule in the same PR.** Otherwise either
(a) legacy Berlin `/static/*` links break, or (b) new landing assets 404
because the redirect swallows them.

## How to add a new city card

1. Add asset: `cp v0.1/web/static/img/hero/<city>.png v0.1/web/landing/static/img/<city>-card.png`
2. Duplicate a `<a class="city-card">` block in `index.html`, swap the img
   src, city name, and href to `https://<city>.addrlens.de/`
3. Add the filename to the CF Redirect Rule's deny-list (see above)
4. Update `sitemap.xml` cross-refs (optional — keeps GSC discovery snappy)
