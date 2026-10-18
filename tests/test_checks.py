import json
import os

import pytest

import catalogue
import checks
import textutils as t

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def load(name):
    with open(os.path.join(FIXTURES, name)) as handle:
        return json.load(handle)


@pytest.fixture
def good():
    return load("good_project.json")


@pytest.fixture
def bad():
    return load("bad_project.json")


def kinds(findings):
    return {f.kind for f in findings}


# ---- catalogue -------------------------------------------------------------

def test_catalogue_covers_every_upstream_kind():
    # the 55 kinds in ProjectNagKind (modrinth/code, fetched 2026-10-18)
    assert len(catalogue.NAGS) == 55
    for kind, (section, severity, message) in catalogue.NAGS.items():
        assert severity in catalogue.SEVERITIES, kind
        assert section and message, kind


def test_render_fills_details():
    _, sev, msg = catalogue.render("summary_too_short", {"length": 3, "min_chars": 25})
    assert sev == "required"
    assert "3/25" in msg


def test_render_link_validation_severity_by_reason():
    _, sev, _ = catalogue.render("link_validation", {"field": "source", "url": "https://bit.ly/x", "reason": "global_blocklist_match"})
    assert sev == "required"
    _, sev, _ = catalogue.render("link_validation", {"field": "issues", "url": "https://example.io/x", "reason": "not_in_allowlist"})
    assert sev == "warning"


def test_render_unknown_kind_does_not_crash():
    section, sev, msg = catalogue.render("some_future_kind", {})
    assert sev == "warning"
    assert "some_future_kind" in msg


# ---- text utils ------------------------------------------------------------

def test_js_len_counts_utf16_units():
    assert t.js_len("abc") == 3
    assert t.js_len("🧟") == 2  # astral plane chars are 2 UTF-16 units


def test_similarity():
    assert t.text_similarity("Hello World", "helloworld") == 1.0
    assert t.text_similarity("abc", "xyz") < 0.2


def test_summary_spam_ports():
    assert t.contains_spam("a" * 8)
    assert t.contains_spam("one one one one")
    assert t.contains_spam("buy my stuff " * 3)
    assert not t.contains_spam("A handcrafted city with lootable buildings.")


def test_description_spam_upstream_examples():
    assert not t.contains_description_spam("======== ━━━━━━━━ !!!!!!!!")
    assert t.contains_description_spam("a" * 64)
    assert not t.contains_description_spam(
        "aaaaaaaa This project provides configurable tools for exploring "
        "worlds, organizing resources, managing settings, sharing creations, "
        "and helping players understand every available feature through "
        "clear documentation.")


def test_find_link_or_ip():
    assert t.find_link_or_ip("see example.org") == "example.org"
    assert t.find_link_or_ip("join 51.195.60.20:25565 now") == "51.195.60.20:25565"
    assert t.find_link_or_ip("grab it from https://modrinth.com/mods") == "https://modrinth.com/mods"
    assert t.find_link_or_ip("no links at all") is None


def test_summary_formatting():
    assert t.has_summary_formatting("**bold**")
    assert t.has_summary_formatting("<b>html</b>")
    assert t.has_summary_formatting("- bullet")
    assert not t.has_summary_formatting("plain text summary")


def test_non_standard_text():
    assert t.has_non_standard_text("𝕱ancy")
    assert t.has_non_standard_text("z͌a͎l͎g͎o͎")
    assert not t.has_non_standard_text("Outbreak Zone 2")


def test_markdown_structure():
    md = t.DescriptionMarkdown("# Title\n\ntext\n\n## A\n\n## B\n\nend\n")
    assert md.has_adjacent_same_level_headers()
    assert not md.ends_with_header()
    md = t.DescriptionMarkdown("# Title\n\ntext\n\n## Lonely\n")
    assert md.ends_with_header()
    md = t.DescriptionMarkdown("# " + "word " * 30 + "\n\ntext\n")
    assert md.long_header_count() == 1
    # code blocks are invisible to structure checks
    md = t.DescriptionMarkdown("# Real\n\ntext\n\n```yaml\n# fake heading\n```\n\ntail\n")
    assert [h[1] for h in md.headings] == ["Real"]


def test_alt_text():
    assert t.has_image_without_alt_text("![](x.png)")
    assert t.has_image_without_alt_text('<img src="x.png">')
    assert not t.has_image_without_alt_text("![city](x.png)")
    assert not t.has_image_without_alt_text('<img src="x.png" alt="city">')


# ---- name / summary --------------------------------------------------------

def test_name_version_number(bad):
    assert "project_name_version" in kinds(checks.check_name(bad))


def test_minecraft_title_clause():
    project = {"title": "Minecraft Tools"}
    assert "minecraft_title_clause" in kinds(checks.check_name(project))
    # long names using the word descriptively are fine
    project = {"title": "Tools For Your Minecraft Server Management Panel"}
    assert "minecraft_title_clause" not in kinds(checks.check_name(project))


def test_name_port_exception():
    project = {"title": "Sodium 1.20 Port"}
    assert "project_name_version" not in kinds(checks.check_name(project))


def test_summary_rules(bad, good):
    bad_kinds = kinds(checks.check_summary(bad))
    assert "project_summary_matches_title" in bad_kinds
    assert "summary_too_short" in bad_kinds
    assert checks.check_summary(good) == []


def test_summary_with_link():
    project = {"title": "X Pack", "description": "A pack. Download at example.org today!"}
    assert "project_summary_links" in kinds(checks.check_summary(project))


# ---- icon / gallery --------------------------------------------------------

def test_icon(good, bad):
    assert checks.check_icon(good) == []
    assert checks.check_icon(bad)[0].severity == "suggestion"


def test_gallery_shader_minimum():
    project = {"project_type": "shader", "categories": [], "additional_categories": [],
               "gallery": [{"featured": True}, {"featured": False}]}
    assert "upload_gallery_image" in kinds(checks.check_gallery(project))
    project["gallery"].append({"featured": False})
    assert "upload_gallery_image" not in kinds(checks.check_gallery(project))


def test_gallery_resourcepack_audio_exemption():
    project = {"project_type": "resourcepack", "categories": ["audio"],
               "additional_categories": [], "gallery": []}
    assert "upload_gallery_image" not in kinds(checks.check_gallery(project))


def test_featured_suggestion(bad):
    assert "feature_gallery_image" in kinds(checks.check_gallery(bad))


# ---- description -----------------------------------------------------------

def test_description_missing(bad):
    assert "add_description" in kinds(checks.check_description(bad))


def test_description_too_short():
    project = {"title": "X", "description": "A pack with features and more.",
               "body": "Short body."}
    f = [f for f in checks.check_description(project) if f.kind == "description_too_short"]
    assert f and f[0].details["min_chars"] == 125


def test_description_matches_summary():
    text = "A handcrafted city dimension with lootable buildings and hordes."
    project = {"title": "X", "description": text, "body": text}
    assert "project_description_matches_summary" in kinds(checks.check_description(project))


def test_description_clean(good):
    assert checks.check_description(good) == []


# ---- license ---------------------------------------------------------------

def test_license_unknown():
    project = {"project_type": "mod", "license": {"id": "LicenseRef-Unknown"}}
    assert "select_license" in kinds(checks.check_license(project))


def test_custom_license_needs_details():
    project = {"project_type": "mod", "license": {"id": "LicenseRef-Custom", "url": ""}}
    assert "add_custom_license_details" in kinds(checks.check_license(project))
    project = {"project_type": "mod", "license": {"id": "LicenseRef-Custom", "url": "https://example.io/LICENSE"}}
    assert "add_custom_license_details" not in kinds(checks.check_license(project))


def test_spdx_license_ok(good):
    assert checks.check_license(good) == []


# ---- links -----------------------------------------------------------------

@pytest.mark.parametrize("field,url,reason", [
    ("source", "https://bit.ly/x", "global_blocklist_match"),
    ("issues", "notaurl", "malformed"),
    ("source", "http://github.com/a/b", "malformed"),          # non-description must be https
    ("discord", "https://51.195.60.20/x", "ip_address"),
    ("source", "https://gitlab.com", "source_repository"),
    ("site", "https://youtube.com/watch?v=x", "external_blocklist_match"),
    ("patreon", "https://ko-fi.com/me", "wrong_field"),
    ("wiki", "https://youtube.com/watch?v=x", "external_blocklist_match"),
])
def test_link_failures(field, url, reason):
    finding = checks.validate_link(field, url)
    assert finding is not None, (field, url)
    assert finding.details["reason"] == reason


@pytest.mark.parametrize("field,url", [
    ("source", "https://github.com/modrinth/code"),
    ("issues", "https://github.com/modrinth/code/issues"),
    ("issues", "https://gitlab.com/group/repo"),
    ("wiki", "https://github.com/modrinth/code/wiki"),
    ("wiki", "https://github.com/modrinth/code"),  # wiki field accepts source hosts
    ("wiki", "https://gitlab.com/group/repo/-/wikis/home"),
    ("discord", "https://discord.gg/abcdef"),
    ("discord", "https://discord.com/invite/abc-def_1"),
    ("license", "https://spdx.org/licenses/MIT.html"),
    ("license", "https://github.com/a/b/blob/main/LICENSE"),
    ("patreon", "https://patreon.com/me"),
    ("ko-fi", "https://ko-fi.com/me"),
    ("site", "https://myproject.dev"),
])
def test_link_passes(field, url):
    assert checks.validate_link(field, url) is None, (field, url)


def test_description_download_link():
    body = "Get it [here](https://github.com/a/b/releases/download/v1/file.jar) now."
    findings = [f for f in checks.check_links({"body": body, "title": "x", "license": {"id": "MIT"}})
                if f.details.get("reason") == "download"]
    assert findings


def test_duplicate_links_across_fields():
    project = {
        "title": "x", "license": {"id": "MIT"},
        "issues_url": "https://github.com/a/b/issues",
        "wiki_url": "https://github.com/a/b/issues",
        "body": "text " * 40,
    }
    assert any(f.details.get("reason") == "duplicate" for f in checks.check_links(project))


def test_no_links_suggestion():
    project = {"title": "x", "license": {"id": "MIT"}, "body": ""}
    assert "add_links" in kinds(checks.check_links(project))


def test_gpl_requires_source(bad):
    findings = checks.check_links(bad, versions=[])
    assert "gpl_license_source_required" in kinds(findings)
    ok = dict(bad)
    ok["source_url"] = "https://github.com/a/b"
    findings = checks.check_links(ok, versions=[])
    assert "gpl_license_source_required" not in kinds(findings)


def test_gpl_source_exemption_with_bundled_sources(bad):
    versions = [{"files": [{"filename": "a.jar"}, {"filename": "sources.jar"}]}]
    findings = checks.check_links(bad, versions=versions)
    assert "gpl_license_source_required" not in kinds(findings)


# ---- tags / versions -------------------------------------------------------

def test_too_many_tags():
    project = {"project_type": "mod", "categories": [str(i) for i in range(9)],
               "additional_categories": []}
    f = [f for f in checks.check_tags(project) if f.kind == "too_many_tags"]
    assert f and f[0].severity == "warning" and f[0].details["max_tag_count"] == 8


def test_all_tags_selected():
    available = [{"category": "a", "project_type": "mod"}, {"category": "b", "project_type": "mod"}]
    project = {"project_type": "mod", "categories": ["a", "b"], "additional_categories": []}
    assert "all_tags_selected" in kinds(checks.check_tags(project, available))


def test_resolution_tags():
    project = {"project_type": "resourcepack", "categories": ["16x", "32x"], "additional_categories": []}
    assert "multiple_resolution_tags" in kinds(checks.check_tags(project))


def test_versions_required(bad, good):
    assert "upload_version" in kinds(checks.check_versions(bad))
    assert checks.check_versions(good, load("good_versions.json")) == []


def test_environment_required_for_mods(bad):
    assert "select_environment" in kinds(checks.check_versions(bad))
    good_mod = dict(bad, client_side="required", server_side="unsupported", versions=["X"])
    assert "select_environment" not in kinds(checks.check_versions(good_mod))


# ---- end to end ------------------------------------------------------------

def test_run_all_bad_project_finds_the_big_blockers(bad):
    found = kinds(checks.run_all(bad, versions=[]))
    assert {
        "project_name_version", "minecraft_title_clause",
        "project_summary_matches_title", "add_description",
        "select_environment", "upload_version",
        "gpl_license_source_required", "add_icon",
    } <= found
    required = [f for f in checks.run_all(bad, versions=[]) if f.severity == "required"]
    assert len(required) >= 6


def test_run_all_good_project_has_no_required(good):
    findings = checks.run_all(good, load("good_versions.json"))
    required = [f for f in findings if f.severity == "required"]
    assert required == [], required
