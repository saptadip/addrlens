# Social embed image (og:image / twitter:image) — deferred

At launch the site ships with `og:` and `twitter:` metadata (title, description,
site name, locale) but **no image**. This document is the one-page playbook for
adding the image when you're ready. Every step is here so you don't have to
reconstruct the context later.

## Why bother adding it

- **Rich vs plain preview**. Reddit, WhatsApp, Slack, LinkedIn, and X all read
  `og:image` when someone pastes your URL. Without it, the embed is a plain
  text card: title + description on a grey background. With it, the embed is a
  full-width preview card with a screenshot / hero image on top. Empirically
  the rich card gets ~2–3× the click-through of the plain card on Reddit.
- **First impression on launch day matters.** The first r/berlin comment
  will paste your link somewhere else (Slack, WhatsApp, quote-tweet). Each
  paste is a free impression *if* the embed is rich.
- Cost to add: ~10 minutes, one PNG, two `<meta>` lines.

## What to make

- **Format:** PNG (works everywhere; JPEG also fine but PNG preserves the
  neumorphic gradient without banding).
- **Dimensions:** **1200×630 pixels**. This is the Open Graph recommended
  aspect ratio (1.91:1) and matches Twitter's `summary_large_image` card.
- **Weight:** aim for under 300 KB. Larger works but slows first-paint of
  embeds on slow mobile networks.
- **Content**: your hero card, framed. The three variants that convert well
  for tools like AddrLens:
  1. **Product screenshot** — hero + one sample lens tile card visible below
     it. Most honest and most self-explanatory. Recommended.
  2. **Hero-only** — just the "Should I Rent It?" heading + sub, big and
     centred, brand-coloured gradient. Cleaner but less informative.
  3. **Split preview** — hero on the left half, a rendered address card on
     the right half. Highest visual density; hardest to shoot cleanly.

## How to shoot the screenshot (option 1, recommended)

```
1. Open https://addrlens.de/ in Chrome (or Chromium).
2. DevTools → Ctrl+Shift+M (Cmd+Shift+M on macOS) to open device toolbar.
3. In the device dropdown → "Responsive". Set width 1200 and height 630.
4. Set the DPR (device pixel ratio) to 2 for a crisp retina export.
5. Search for `Kastanienallee 12, 10435` so the page has a real result
   underneath the hero. Otherwise the hero card looks empty and marketing-y.
6. Scroll so the hero card is at the top with the first tile card visible
   underneath (roughly the first 630 px of content).
7. Right-click the page → "Capture screenshot" (or ⋮ menu → "Capture full
   size screenshot" and crop to 1200×630 afterwards).
8. Save as `v0.1/web/static/og-image.png`.
```

Tip: use `Konrad-Wolf-Straße 44A, 13055` if you want the "Get History" chip
visible in the frame — it makes the tool's LLM angle immediately obvious in
the preview.

## Add the meta tags

Once `og-image.png` is at `v0.1/web/static/og-image.png`, patch `web/index.html`
inside the head:

```html
<meta property="og:image" content="https://addrlens.de/static/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="AddrLens hero and a Berlin address result card">
<meta name="twitter:image" content="https://addrlens.de/static/og-image.png">
```

And upgrade the Twitter card type from the default `summary` to the wider
variant so the image goes full-width instead of a thumbnail:

```html
<meta name="twitter:card" content="summary_large_image">
```

Bump the cache-buster on `app.css` / `app.js` so browsers pull the new HTML.

## Test the embed before promoting

Cloudflare caches the HTML aggressively. After deploying, purge the cache for
just this URL:

```
Cloudflare dashboard → Caching → Configuration → Purge Cache →
    Custom Purge → paste https://addrlens.de/
```

Then check each platform's scraper:

- **Facebook / Instagram / WhatsApp** — `https://developers.facebook.com/tools/debug/` → paste `https://addrlens.de/` → *Scrape Again*.
- **LinkedIn** — `https://www.linkedin.com/post-inspector/` → paste → *Refresh*.
- **X / Twitter** — no first-party validator anymore. Tweet the URL from a
  private account or DM to yourself; check the resulting card.
- **Reddit** — no debugger. Just paste the URL into a subreddit's title bar
  as a URL post; the preview updates live before you hit submit.

Each of these caches for days-to-weeks, so if you see the wrong image, force
a refresh via the debugger above rather than waiting.

## Refresh cadence

The image only needs regeneration when:

- The hero copy changes (title, sub, or the gradient colour).
- You add a visually distinctive feature to the hero (e.g. a new lens tab).
- You want a seasonal variant for a specific launch push.

Bump the file at the same URL and re-run the platform debuggers to bust
their caches. No cache-buster query string is needed on `og:image` itself —
in fact many scrapers strip query strings on image URLs.
