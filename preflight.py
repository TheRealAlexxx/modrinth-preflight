#!/usr/bin/env python3
"""modrinth-preflight: check a Modrinth project against Modrinth's own
review rules before you submit.

Two engines:

  official  With a Modrinth personal access token (PROJECT_READ scope) in
            an environment variable, asks Modrinth itself: GET
            /v3/project/{id}/validate returns the exact "nags" their
            reviewers' checklist would flag for your draft.

  local     A dependency-free reimplementation of the same rules that
            runs on public API data (or saved JSON), so you can check any
            project, or run offline in CI.

Exit codes: 0 = no required findings, 1 = required findings (or any
finding with --strict), 2 = usage or fetch error.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

import catalogue
import checks

API_BASE = "https://api.modrinth.com"
USER_AGENT = "modrinth-preflight/0.1.0 (https://github.com/TheRealAlexxx/modrinth-preflight)"
VERSION = "0.1.0"


class ApiError(Exception):
    pass


def _request(path, token=None):
    url = API_BASE + path
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if token:
        headers["Authorization"] = token
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise ApiError("not found: %s" % path)
        if exc.code in (401, 403):
            raise ApiError("access denied (%s): %s (token missing, invalid, or you are not on this project's team)" % (exc.code, path))
        raise ApiError("Modrinth API error %s for %s" % (exc.code, path))
    except urllib.error.URLError as exc:
        raise ApiError("could not reach api.modrinth.com: %s" % exc.reason)


def fetch_project(slug, token=None):
    return _request("/v2/project/%s" % urllib.parse.quote(slug, safe=""), token)


def fetch_versions(slug, token=None):
    return _request("/v2/project/%s/version" % urllib.parse.quote(slug, safe=""), token)


def fetch_available_categories():
    return _request("/v2/tag/category")


def fetch_official_nags(project_id, token):
    return _request("/v3/project/%s/validate" % urllib.parse.quote(project_id, safe=""), token)["nags"]


def official_findings(nags):
    out = []
    for nag in nags:
        section, severity, message = catalogue.render(nag.get("kind", ""), nag.get("details") or {})
        out.append({
            "kind": (nag.get("kind") or "").replace("-", "_"),
            "severity": nag.get("severity") or severity,
            "section": section,
            "message": message,
            "details": nag.get("details") or {},
        })
    return out


def local_findings(project, versions, available_categories):
    out = []
    for finding in checks.run_all(project, versions, available_categories):
        section, severity, message = catalogue.render(finding.kind, finding.details)
        out.append({
            "kind": finding.kind,
            "severity": finding.severity or severity,
            "section": section,
            "message": message,
            "details": finding.details,
        })
    return out


def worst_severity(findings):
    order = ["suggestion", "warning", "required"]
    worst = None
    for finding in findings:
        sev = finding["severity"]
        if sev in order and (worst is None or order.index(sev) > order.index(worst)):
            worst = sev
    return worst


def print_report(title, source, findings, stream=sys.stdout):
    counts = {"required": 0, "warning": 0, "suggestion": 0}
    for finding in findings:
        counts[finding["severity"]] = counts.get(finding["severity"], 0) + 1
    print("%s  [%s engine]" % (title, source), file=stream)
    if not findings:
        print("  no findings - ready to submit for review", file=stream)
    current_section = None
    icons = {"required": "FAIL", "warning": "WARN", "suggestion": "note"}
    for finding in sorted(findings, key=lambda f: (f["section"], -catalogue.severity_rank(f["severity"]) if f["severity"] in catalogue.SEVERITIES else 0, f["kind"])):
        if finding["section"] != current_section:
            current_section = finding["section"]
            print("\n%s:" % current_section, file=stream)
        print("  [%s] %s" % (icons.get(finding["severity"], finding["severity"]), finding["message"]), file=stream)
    print("\n%d required, %d warning, %d suggestion" % (
        counts.get("required", 0), counts.get("warning", 0), counts.get("suggestion", 0)), file=stream)


def cmd_check(args):
    token = os.environ.get(args.token_env, "").strip() or None
    available_categories = None

    if args.offline:
        try:
            with open(args.offline) as handle:
                project = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            print("error: cannot read %s: %s" % (args.offline, exc), file=sys.stderr)
            return 2
        versions = None
        if args.versions:
            try:
                with open(args.versions) as handle:
                    versions = json.load(handle)
            except (OSError, json.JSONDecodeError) as exc:
                print("error: cannot read %s: %s" % (args.versions, exc), file=sys.stderr)
                return 2
        if args.tags:
            try:
                with open(args.tags) as handle:
                    available_categories = json.load(handle)
            except (OSError, json.JSONDecodeError) as exc:
                print("error: cannot read %s: %s" % (args.tags, exc), file=sys.stderr)
                return 2
        title = "%s (offline: %s)" % (project.get("title") or project.get("slug") or args.offline, args.offline)
        findings = local_findings(project, versions, available_categories)
        source = "local"
    else:
        slug = args.project
        try:
            project = fetch_project(slug, token)
        except ApiError as exc:
            print("error: %s" % exc, file=sys.stderr)
            return 2
        title = "%s (%s)" % (project.get("title") or slug, project.get("slug") or slug)

        findings = None
        source = "local"
        if token and not args.local:
            try:
                nags = fetch_official_nags(project["id"], token)
                findings = official_findings(nags)
                source = "official"
            except ApiError as exc:
                print("note: official validation unavailable (%s); falling back to the local mirror" % exc, file=sys.stderr)
        if findings is None:
            try:
                versions = fetch_versions(slug, token)
            except ApiError:
                versions = None
            if not args.no_tags:
                try:
                    available_categories = fetch_available_categories()
                except ApiError:
                    available_categories = None
            findings = local_findings(project, versions, available_categories)

    if args.json:
        print(json.dumps({
            "project": title,
            "engine": source,
            "version": VERSION,
            "counts": {
                "required": sum(1 for f in findings if f["severity"] == "required"),
                "warning": sum(1 for f in findings if f["severity"] == "warning"),
                "suggestion": sum(1 for f in findings if f["severity"] == "suggestion"),
            },
            "findings": findings,
        }, indent=2))
    else:
        print_report(title, source, findings)

    if any(f["severity"] == "required" for f in findings):
        return 1
    if args.strict and findings:
        return 1
    return 0


def cmd_rules(args):
    for kind in sorted(catalogue.NAGS):
        section, severity, message = catalogue.NAGS[kind]
        if args.section and section != args.section:
            continue
        print("%-40s %-10s %-12s %s" % (kind, severity, section, message))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="modrinth-preflight",
        description="Check a Modrinth project against Modrinth's review rules before submitting.",
    )
    parser.add_argument("--version", action="version", version="%(prog)s " + VERSION)
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="check a project")
    check.add_argument("project", nargs="?", help="project slug or id on Modrinth")
    check.add_argument("--token-env", default="MODRINTH_TOKEN", metavar="ENV",
                       help="environment variable holding a Modrinth PAT (default: MODRINTH_TOKEN)")
    check.add_argument("--local", action="store_true",
                       help="force the local mirror even when a token is available")
    check.add_argument("--no-tags", action="store_true",
                       help="skip fetching the category list (disables the all-tags-selected check)")
    check.add_argument("--offline", metavar="PROJECT.json",
                       help="run the local mirror on a saved /v2/project response instead of the API")
    check.add_argument("--versions", metavar="VERSIONS.json",
                       help="saved /v2/project/{id}/version response (with --offline)")
    check.add_argument("--tags", metavar="TAGS.json",
                       help="saved /v2/tag/category response (with --offline)")
    check.add_argument("--json", action="store_true", help="machine-readable output")
    check.add_argument("--strict", action="store_true",
                       help="exit 1 on warnings and suggestions too")
    check.set_defaults(func=cmd_check)

    rules = sub.add_parser("rules", help="list every rule this tool knows about")
    rules.add_argument("--section", help="only show one section (name, summary, icon, gallery, description, license, links, permissions, server, tags, versions, disclosures, moderation)")
    rules.set_defaults(func=cmd_rules)

    args = parser.parse_args(argv)
    if args.command == "check" and not args.project and not args.offline:
        check.error("give a project slug/id, or --offline PROJECT.json")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
