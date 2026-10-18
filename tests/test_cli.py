import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "tests", "fixtures")


def run_cli(*argv):
    return subprocess.run(
        [sys.executable, os.path.join(ROOT, "preflight.py"), *argv],
        capture_output=True, text=True)


def test_offline_good_project_exits_zero():
    good = os.path.join(FIXTURES, "good_project.json")
    versions = os.path.join(FIXTURES, "good_versions.json")
    result = run_cli("check", "--offline", good, "--versions", versions)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "0 required" in result.stdout


def test_offline_bad_project_exits_one_and_reports():
    bad = os.path.join(FIXTURES, "bad_project.json")
    result = run_cli("check", "--offline", bad)
    assert result.returncode == 1
    assert "FAIL" in result.stdout
    assert "description" in result.stdout
    assert "versions" in result.stdout


def test_offline_json_output():
    bad = os.path.join(FIXTURES, "bad_project.json")
    result = run_cli("check", "--offline", bad, "--json")
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["engine"] == "local"
    assert payload["counts"]["required"] > 0
    assert any(f["kind"] == "upload_version" for f in payload["findings"])


def test_strict_makes_suggestions_fail():
    good = os.path.join(FIXTURES, "good_project.json")
    versions = os.path.join(FIXTURES, "good_versions.json")
    result = run_cli("check", "--offline", good, "--versions", versions, "--strict")
    kinds = [f for f in json.loads(run_cli("check", "--offline", good, "--versions", versions, "--json").stdout)["findings"]]
    if kinds:
        assert result.returncode == 1
    else:
        assert result.returncode == 0


def test_missing_offline_file_exits_two():
    result = run_cli("check", "--offline", "/nonexistent/project.json")
    assert result.returncode == 2


def test_no_project_exits_two():
    result = run_cli("check")
    assert result.returncode == 2


def test_rules_command():
    result = run_cli("rules", "--section", "links")
    assert result.returncode == 0
    assert "gpl_license_source_required" in result.stdout
