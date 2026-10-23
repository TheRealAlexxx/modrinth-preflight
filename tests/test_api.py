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


def _degraded_run(monkeypatch, capsys, argv):
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
    rc = preflight.main(argv)
    out, err = capsys.readouterr().out, capsys.readouterr().err
    return rc, out, err


def test_partial_run_does_not_claim_ready_to_submit(monkeypatch, capsys):
    rc, out, err = _degraded_run(monkeypatch, capsys, ["check", "sodium"])
    assert rc == 0
    assert "ready to submit" not in out
    assert "no findings in the checks that ran" in out
    assert "partial run" in out
    assert "version list unavailable" in out


def test_json_marks_degraded(monkeypatch, capsys):
    import json
    rc, out, err = _degraded_run(monkeypatch, capsys, ["check", "sodium", "--json"])
    payload = json.loads(out)
    assert payload["degraded"], "JSON must mark the run degraded"
    assert any("version list" in d for d in payload["degraded"])


def test_strict_fails_on_partial_run(monkeypatch, capsys):
    rc, out, err = _degraded_run(monkeypatch, capsys, ["check", "sodium", "--strict"])
    assert rc == 1, "--strict must not pass a partial run"


def test_full_run_still_says_ready(capsys):
    import io
    buf = io.StringIO()
    preflight.print_report("x", "local", [], stream=buf)
    assert "ready to submit" in buf.getvalue()


def test_both_fetches_failing_list_both_reasons(monkeypatch, capsys):
    import json
    import os
    fixtures = os.path.join(os.path.dirname(preflight.__file__), "tests", "fixtures")
    with open(os.path.join(fixtures, "good_project.json")) as handle:
        project = json.load(handle)
    monkeypatch.setattr(preflight, "fetch_project", lambda slug, token=None: project)
    def boom_versions(slug, token=None):
        raise preflight.ApiError("Modrinth API error 500 for /v2/project/sodium/version")
    def boom_categories():
        raise preflight.ApiError("access denied (403): /v2/tag/category (token missing, invalid, or you are not on this project's team)")
    monkeypatch.setattr(preflight, "fetch_versions", boom_versions)
    monkeypatch.setattr(preflight, "fetch_available_categories", boom_categories)
    rc = preflight.main(["check", "sodium"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "partial run" in out
    assert "version list unavailable" in out, out
    assert "category list unavailable" in out, out
    assert out.count("  - ") >= 2, out


def test_403_on_versions_is_degraded_not_crash(monkeypatch, capsys):
    import json
    import os
    fixtures = os.path.join(os.path.dirname(preflight.__file__), "tests", "fixtures")
    with open(os.path.join(fixtures, "good_project.json")) as handle:
        project = json.load(handle)
    monkeypatch.setattr(preflight, "fetch_project", lambda slug, token=None: project)
    def boom(slug, token=None):
        raise preflight.ApiError("access denied (403): /v2/project/sodium/version (token missing, invalid, or you are not on this project's team)")
    monkeypatch.setattr(preflight, "fetch_versions", boom)
    monkeypatch.setattr(preflight, "fetch_available_categories", lambda: [])
    rc = preflight.main(["check", "sodium"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "version list unavailable" in out


def test_strict_fails_on_warnings_full_run(monkeypatch, capsys):
    import json
    import os
    fixtures = os.path.join(os.path.dirname(preflight.__file__), "tests", "fixtures")
    with open(os.path.join(fixtures, "good_project.json")) as handle:
        project = json.load(handle)
    monkeypatch.setattr(preflight, "fetch_project", lambda slug, token=None: project)
    monkeypatch.setattr(preflight, "fetch_versions", lambda slug, token=None: [])
    monkeypatch.setattr(preflight, "fetch_available_categories", lambda: [])
    warning_only = [{"kind": "link_problem", "severity": "warning", "section": "links", "message": "double check a link"}]
    monkeypatch.setattr(preflight, "local_findings", lambda p, v, c: warning_only)
    assert preflight.main(["check", "sodium"]) == 0, "warnings alone pass without --strict"
    assert preflight.main(["check", "sodium", "--strict"]) == 1, "warnings fail under --strict"
