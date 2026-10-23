# modrinth-preflight

Check a Modrinth project against Modrinth's own review rules before you
submit, so a rejection never surprises you.

Modrinth moderators run every submission through a validation checklist
(55 checks: name, summary, description, icon, gallery, license, links,
tags, versions, server settings). Modrinth computes this list for your
own projects, but only through an owner-authenticated API endpoint that
almost nobody uses. This tool surfaces it in a terminal, and mirrors the
same rules locally so you can check any public project or run offline
in CI.

## Install

No dependencies. Python 3.9+.

```sh
git clone https://github.com/TheRealAlexxx/modrinth-preflight
cd modrinth-preflight
python3 preflight.py --help
```

## Usage

Check any public project with the local rule mirror:

```sh
python3 preflight.py check sodium
```

Check your own draft against Modrinth's official verdict. Create a
personal access token at modrinth.com/settings/pats with the
PROJECT_READ scope, keep it in an environment variable, and the tool
asks Modrinth itself:

```sh
export MODRINTH_TOKEN=mrp_...
python3 preflight.py check your-project-slug
```

The token is only ever read from the environment, never from a command
line argument, so it cannot leak into shell history.

Offline mode for CI, using saved API responses:

```sh
python3 preflight.py check --offline project.json --versions versions.json --json
```

Exit codes: `0` no required findings, `1` required findings (or, with
`--strict`, any finding or an incomplete run), `2` usage or fetch error.
`--json` gives machine-readable output. `python3 preflight.py rules`
lists every rule the tool knows.

If the version list or category list cannot be fetched, the report says
so: the summary reads "partial run" and names the skipped checks, the
JSON carries a non-empty `degraded` list, and `--strict` exits 1. A full
run never carries that marker.

A ready to submit result from the official engine is exactly what the
reviewers' checklist would show; from the local engine it is a close
mirror (see Accuracy).

## GitHub Actions example

```yaml
- name: Preflight the Modrinth listing
  env:
    MODRINTH_TOKEN: ${{ secrets.MODRINTH_TOKEN }}
  run: python3 preflight.py check my-project
```

## Accuracy

Rule identifiers, severities and thresholds are ported from Modrinth's
backend validator (apps/labrinth/src/validate/project in
github.com/modrinth/code, fetched 2026-10-18). Modrinth's code is under
its own licenses; all messages here are this project's own wording, and
the heuristics are reimplemented, not copied.

The official engine returns Modrinth's verdict verbatim. The local
engine mirrors the static checks faithfully, with these documented
gaps (they need data only Modrinth has):

- profanity and slur word lists
- English-language detection
- the NSFW host blocklist
- Discord invite liveness and URL reachability
- disclosures, moderation thread state, version file attribution
- server listing fields (region, languages, Java address)
- setext (=== / ---) headings in descriptions

`tools/refresh_catalogue.py` diffs the bundled rule catalogue against
the current upstream source so the tool can be kept in sync.

## Development

Tests need pytest:

```sh
pip install pytest
python3 -m pytest tests
```

## License

MIT
