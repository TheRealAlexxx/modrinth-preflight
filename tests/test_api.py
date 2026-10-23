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


def test_degraded_version_fetch_is_mentioned(monkeypatch, capsys):
    import json
    import os
    fixtures = os.path.join(os.path.dirname(preflight.__file__), "tests", "fixtures")
    with open(os.path.join(fixtures, "good_project.json")) as handle:
        project = json.load(handle)
    monkeypatch.setattr(preflight, "fetch_project", lambda slug, token=None: project)
    def boom(slug, token=None):
        raise preflight.ApiError("Modrinth API error 500 for /v2/project/sodium/version")
    monkeypatch.setattr(preflight, "fetch_versions", boom)
    monkeypatch.setattr(preflight, "fetch_available_categories", lambda: [])
    rc = preflight.main(["check", "sodium"])
    assert rc == 0
    err = capsys.readouterr().err
    assert "version list unavailable" in err
    assert "weaker" in err
