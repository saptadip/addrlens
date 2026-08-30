"""Tier tokens + shared helpers used across scoring modules."""


TIER_GREEN   = "green"
TIER_AMBER   = "amber"
TIER_RED     = "red"
TIER_UNKNOWN = "unknown"


def _fmt_dist(m: int) -> str:
    """Format a metre threshold for tile rule text.

    ≥1000m becomes km ("1500" → "1.5km", "1000" → "1km"), else stays in
    metres with no space ("400" → "400m"). Kept spaceless to match the
    Young-Family rule style ("≥3 kitas within 400m").
    """
    if m >= 1000:
        return f"{m/1000:g}km"
    return f"{int(m)}m"


def _walk_minutes(dist_m: float) -> float:
    """Haversine → estimated walking minutes.
    4.8 km/h walking speed × 1.3 route factor ≈ 62 m/min effective.
    Uniform across all walk-distance tiles."""
    return dist_m / 62


if __name__ == "__main__":
    assert (TIER_GREEN, TIER_AMBER, TIER_RED, TIER_UNKNOWN) == \
        ("green", "amber", "red", "unknown")

    assert _fmt_dist(400) == "400m"
    assert _fmt_dist(1000) == "1km"
    assert _fmt_dist(1500) == "1.5km"
    assert _fmt_dist(2500) == "2.5km"

    assert _walk_minutes(0) == 0.0
    assert _walk_minutes(62) == 1.0
    assert abs(_walk_minutes(930) - 15.0) < 1e-9
    print("scoring.constants selfcheck OK")
