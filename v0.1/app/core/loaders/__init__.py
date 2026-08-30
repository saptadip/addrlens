"""Boot-time data loaders — helpers used by `Index.__init__` to pull
preloaded per-city datasets.

- `wfs_layer` — shared shape/point WFS loaders that used to be inlined
  as 8+ near-identical polygon/point loops in `Index.__init__`.
- `buergeramt_service_portal` — the service.berlin.de REST/GeoJSON
  loader with its HTML-scrape for address + website. Isolated here so
  the generic WFS path stays clean and the REST/HTML code has its own
  selfcheck.
"""
