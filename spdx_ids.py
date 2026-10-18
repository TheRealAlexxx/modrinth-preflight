"""SPDX license identifiers known to this tool.

A curated subset of common licenses, plus a shape check in
is_probably_spdx(). Modrinth validates against the full SPDX list via the
Rust `spdx` crate; shipping all ~600 ids here would bloat the tool for a
rare edge case. Unknown-but-well-formed ids pass with an informational
note rather than a false failure.
"""

import re

COMMON_SPDX = frozenset("""
0BSD AFL-3.0 AGPL-1.0-only AGPL-1.0-or-later AGPL-3.0 AGPL-3.0-only AGPL-3.0-or-later
Apache-1.0 Apache-1.1 Apache-2.0 Artistic-1.0 Artistic-1.0-Perl Artistic-2.0
BSD-1-Clause BSD-2-Clause BSD-2-Clause-Patent BSD-3-Clause BSD-3-Clause-Clear BSD-4-Clause
BSL-1.0 CC-BY-1.0 CC-BY-2.0 CC-BY-3.0 CC-BY-4.0 CC-BY-NC-4.0 CC-BY-NC-ND-4.0
CC-BY-NC-SA-4.0 CC-BY-ND-4.0 CC-BY-SA-4.0 CC0-1.0 CDDL-1.0 CDDL-1.1
CECILL-2.1 CPL-1.0 EPL-1.0 EPL-2.0 EUPL-1.1 EUPL-1.2
GFDL-1.3-only GFDL-1.3-or-later GPL-1.0-only GPL-1.0-or-later
GPL-2.0 GPL-2.0-only GPL-2.0-or-later GPL-3.0 GPL-3.0-only GPL-3.0-or-later
ISC LGPL-2.0-only LGPL-2.0-or-later LGPL-2.1 LGPL-2.1-only LGPL-2.1-or-later
LGPL-3.0 LGPL-3.0-only LGPL-3.0-or-later MIT MIT-0 MIT-Modern-Variant
MPL-1.0 MPL-1.1 MPL-2.0 MS-PL MS-RL NCSA OFL-1.1 OSL-3.0
PHP-3.0 PHP-3.01 PostgreSQL Python-2.0 Unlicense UPL-1.0
Vim WTFPL X11 Zlib ZPL-2.1
LicenseRef-Polyform-Shield-1.0.0 LicenseRef-PolyForm-Noncommercial-1.0.0
PolyForm-Noncommercial-1.0.0 PolyForm-Shield-1.0.0 BUSL-1.1 Elastic-2.0 SSPL-1.0
""".split())

# ids Modrinth treats as "no real license selected"
UNKNOWN_LICENSE_IDS = frozenset([
    "", "LicenseRef-Unknown", "NOASSERTION", "LicenseRef-NOASSERTION",
])

# LicenseRef ids Modrinth accepts without further details
KNOWN_LICENSEREF_IDS = frozenset([
    "LicenseRef-All-Rights-Reserved", "arr",
])

_SPDX_SHAPE = re.compile(r"^[A-Za-z0-9.+-]{2,60}$")


def is_unknown_license(license_id):
    return (license_id or "").strip() in UNKNOWN_LICENSE_IDS


def is_custom_license(license_id):
    """Mirror of upstream: custom means not SPDX and not a known LicenseRef."""
    lid = (license_id or "").strip()
    if lid in COMMON_SPDX or lid in KNOWN_LICENSEREF_IDS or lid in UNKNOWN_LICENSE_IDS:
        return False
    if lid.startswith("LicenseRef-"):
        return True
    if _SPDX_SHAPE.match(lid):
        # well-formed but not in our curated set: assume valid SPDX
        return False
    return True


def is_probably_spdx(license_id):
    return (license_id or "").strip() in COMMON_SPDX
