"""wfs() must pass srsName= when caller supplies it (Hamburg requirement);
must omit it when caller does not (Berlin behaviour preserved)."""
from unittest.mock import patch, MagicMock
import urllib.parse

from app.core import wfs as wfs_mod


def test_srsname_included_when_supplied():
    with patch.object(wfs_mod, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"features": []}
        mock_resp.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_get_client.return_value = mock_client
        wfs_mod.wfs("https://example/wfs", typeNames="foo:bar",
                    count=1, outputFormat="application/geo+json",
                    srsName="EPSG:4326")
        called_url = mock_client.get.call_args[0][0]
        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(called_url).query)
        assert "EPSG:4326" in parsed.get("srsName", [])


def test_srsname_omitted_when_not_supplied():
    with patch.object(wfs_mod, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"features": []}
        mock_resp.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_get_client.return_value = mock_client
        wfs_mod.wfs("https://example/wfs", typeNames="foo:bar",
                    count=1, outputFormat="application/json")
        called_url = mock_client.get.call_args[0][0]
        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(called_url).query)
        assert "srsName" not in parsed
