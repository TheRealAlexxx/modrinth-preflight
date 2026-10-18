#!/usr/bin/env python3
"""Diff the bundled nag catalogue against Modrinth's current source.

Fetches the ProjectNagKind enum from github.com/modrinth/code and prints
kinds upstream added or removed since the catalogue was bundled, so a
maintainer can update catalogue.py. Read-only; changes nothing.
"""

import json
import re
import sys
import urllib.request

sys.path.insert(0, __file__.rsplit("/", 2)[0])
import catalogue  # noqa: E402

SOURCE = ("https://raw.githubusercontent.com/modrinth/code/main/"
          "apps/labrinth/src/validate/project/mod.rs")


def upstream_kinds():
    with urllib.request.urlopen(urllib.request.Request(
            SOURCE, headers={"User-Agent": "modrinth-preflight"}), timeout=30) as resp:
        rust = resp.read().decode()
    body = rust.split("pub enum ProjectNagKind", 1)[1].split("}", 1)[0]
    variants = re.findall(r"^\s*([A-Z][A-Za-z0-9]+),?\s*$", body, re.MULTILINE)
    return {re.sub(r"(?<!^)(?=[A-Z])", "_", v).lower() for v in variants}


def main():
    upstream = upstream_kinds()
    bundled = set(catalogue.NAGS)
    new = sorted(upstream - bundled)
    gone = sorted(bundled - upstream)
    print(json.dumps({"upstream": len(upstream), "bundled": len(bundled),
                      "new_upstream_kinds": new, "removed_upstream_kinds": gone}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
