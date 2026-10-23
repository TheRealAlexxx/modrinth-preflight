import io
import urllib.error

import pytest

import preflight


def fake_404(url_or_req, timeout=30):
    raise urllib.error.HTTPError(url_or_req.full_url, 404, "Not Found", {}, io.BytesIO(b"{}"))


def test_unknown_project_names_the_slug(monkeypatch):
    monkeypatch.setattr(preflight.urllib.request, "urlopen", fake_404)
    with pytest.raises(preflight.ApiError) as excinfo:
        preflight.fetch_project("unknownslug")
    assert str(excinfo.value) == "no project named 'unknownslug' on Modrinth"


def test_unknown_project_versions_names_the_slug(monkeypatch):
    monkeypatch.setattr(preflight.urllib.request, "urlopen", fake_404)
    with pytest.raises(preflight.ApiError) as excinfo:
        preflight.fetch_versions("unknownslug")
    assert str(excinfo.value) == "no project named 'unknownslug' on Modrinth"


def test_other_404s_keep_the_path(monkeypatch):
    monkeypatch.setattr(preflight.urllib.request, "urlopen", fake_404)
    with pytest.raises(preflight.ApiError) as excinfo:
        preflight.fetch_available_categories()
    assert "/v2/tag/category" in str(excinfo.value)
