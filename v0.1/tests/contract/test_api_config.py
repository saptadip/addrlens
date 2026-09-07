"""Contract tests for `/api/config` — city display strings + attribution."""


def test_config_returns_200(client):
    r = client.get("/api/config")
    assert r.status_code == 200


def test_config_returns_expected_top_level_keys(client):
    body = client.get("/api/config").json()
    for key in ("slug", "display_name", "default_center", "attribution", "noise_year"):
        assert key in body, f"missing key: {key}"


def test_config_slug_matches_selected_city(client):
    body = client.get("/api/config").json()
    assert body["slug"] == "berlin"
    assert body["display_name"] == "Berlin"


def test_config_attribution_carries_dl_de_license_tags(client):
    # Every Berlin dataset entry must carry an open-data licence tag.
    body = client.get("/api/config").json()
    attribution = body["attribution"]
    assert isinstance(attribution, dict)
    # A few load-bearing keys the frontend footer relies on.
    for k in ("catchment", "schools", "kitas", "sbahn"):
        assert k in attribution, f"attribution missing key: {k}"


def test_config_default_center_is_list_of_two_floats(client):
    body = client.get("/api/config").json()
    center = body["default_center"]
    assert isinstance(center, list)
    assert len(center) == 2
    lat, lon = center
    assert 52 < lat < 53
    assert 13 < lon < 14
