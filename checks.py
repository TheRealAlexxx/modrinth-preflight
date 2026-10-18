"""Local mirror of Modrinth's project validation.

Each function ports one module of apps/labrinth/src/validate/project/ in
github.com/modrinth/code (fetched 2026-10-18) and returns Finding objects
matching the official nag kinds, severities and thresholds.

Input shape is the Modrinth v2 API: the project object from
GET /v2/project/{id} (its `description` field is the short summary and
`body` is the long description) plus the version list from
GET /v2/project/{id}/version.

Not mirrored locally (needs data only Modrinth has): profanity/slur word
lists, English-language detection, NSFW host list, Discord invite
liveness, disclosures, moderation thread state, server listing
components, version file attribution. The official /v3/project/{id}/validate
endpoint covers those for your own projects; preflight.py uses it when a
token is available.
"""

import re
from urllib.parse import urlparse

import textutils as t
from spdx_ids import is_unknown_license, is_custom_license

REQUIRED = "required"
WARNING = "warning"
SUGGESTION = "suggestion"

MIN_SUMMARY_CHARS = 25
MAX_SUMMARY_NAME_SIMILARITY = 0.8
MIN_DESCRIPTION_CHARS = 125
MAX_DESCRIPTION_SUMMARY_SIMILARITY = 0.8
NON_STANDARD_TEXT_FAILURE_THRESHOLD = 0.05
MAX_TAG_COUNT = 8
MAX_TAG_COUNT_SERVER = 18
RESOLUTION_TAGS = ["8x-", "16x", "32x", "48x", "64x", "128x", "256x", "512x+"]

GLOBAL_BLOCKS = [
    "bit.ly", "adf.ly", "tinyurl.com", "short.io", "is.gd", "t.me",
    "telegram.org", "linkvertise.com", "example.com", "example.net",
    "example.org", "9minecraft.net", "creativemode.net", "orcaclient.com",
    "autoforged.cn",
]
EXTERNAL_BLOCKS = [
    "reddit.com", "redd.it", "x.com", "twitter.com", "instagram.com",
    "facebook.com", "tiktok.com", "twitch.tv", "bsky.app", "bilibili.com",
    "youtube.com", "youtu.be", "curseforge.com", "planetminecraft.com",
    "modrinth.com", "minecraft.net", "mcmod.cn", "github.com",
    "drive.google.com", "www.google.com", "google.com", "dropbox.com",
    "mediafire.com", "linktr.ee", "amazon.com", "discord.com", "discord.gg",
    "discordapp.com",
]
SOURCE_DOMAINS = [
    "github.com", "gitlab.com", "bitbucket.org", "codeberg.org",
    "git.sr.ht", "tangled.org", "git.gay", "gitee.com",
]
GITHUB_DOMAINS = ["github.com"]
GITLAB_DOMAINS = ["gitlab.com"]
CURSEFORGE_DOMAINS = ["curseforge.com"]
GOOGLE_FORMS_DOMAINS = ["docs.google.com"]
GOOGLE_FORMS_SHORT_DOMAINS = ["forms.gle"]
MICROSOFT_FORMS_DOMAINS = ["forms.office.com", "forms.microsoft.com", "forms.cloud.microsoft"]
TYPEFORM_DOMAINS = ["typeform.com"]
DISCORD_INVITE_DOMAINS = ["discord.com", "discordapp.com"]
DISCORD_SHORT_INVITE_DOMAINS = ["discord.gg"]
DISCORD_REDIRECT_DOMAINS = ["dsc.gg"]
LICENSE_DOMAINS = [
    "spdx.org", "opensource.org", "choosealicense.com", "gnu.org",
    "apache.org", "creativecommons.org",
]
DONATION_DOMAINS = {
    "patreon": ["patreon.com"],
    "bmac": ["buymeacoffee.com", "buymeacoff.ee", "coff.ee", "bmc.link"],
    "paypal": ["paypal.me", "paypal.com", "py.pl", "paypal.biz"],
    "ko-fi": ["ko-fi.com"],
}
SOURCE_REQUIRING_LICENSES = [
    "GPL-2.0", "GPL-2.0+", "GPL-2.0-only", "GPL-2.0-or-later",
    "GPL-3.0", "GPL-3.0+", "GPL-3.0-only", "GPL-3.0-or-later",
    "LGPL-2.1", "LGPL-2.1+", "LGPL-2.1-only", "LGPL-2.1-or-later",
    "LGPL-3.0", "LGPL-3.0+", "LGPL-3.0-only", "LGPL-3.0-or-later",
    "AGPL-3.0", "AGPL-3.0+", "AGPL-3.0-only", "AGPL-3.0-or-later",
    "MPL-2.0",
]
# fields exempt from the per-field allowlist and the external blocklist
OPEN_FIELDS = {"site", "store", "other", "source", "discord", "wiki"}


class Finding:
    def __init__(self, kind, severity, **details):
        self.kind = kind
        self.severity = severity
        self.details = details

    def __repr__(self):
        return "Finding(%s, %s, %r)" % (self.kind, self.severity, self.details)

    def __eq__(self, other):
        return (
            isinstance(other, Finding)
            and (self.kind, self.severity, self.details) == (other.kind, other.severity, other.details)
        )


def _link_finding(field, url, reason, severity=REQUIRED, **extra):
    details = {"field": field, "url": url, "reason": reason}
    details.update(extra)
    return Finding("link_validation", severity, **details)


# ---------------------------------------------------------------------------
# name

_VERSION_NUMBER_RE = re.compile(r"\d+(?:\.\d+)+")


def check_name(project):
    findings = []
    name = project.get("title") or ""
    if t.has_non_standard_text(name):
        findings.append(Finding("project_name_non_standard_text", REQUIRED))
    normalized = t.normalize(name).lower()
    is_port_or_fork = "port" in normalized or "fork" in normalized
    if _VERSION_NUMBER_RE.search(normalized) and not is_port_or_fork:
        findings.append(Finding("project_name_version", REQUIRED))
    if "minecraft" in normalized and len(normalized.split()) <= 3:
        findings.append(Finding("minecraft_title_clause", REQUIRED))
    return findings


# ---------------------------------------------------------------------------
# summary (the v2 `description` field)

def check_summary(project):
    findings = []
    summary = project.get("description") or ""
    name = project.get("title") or ""
    normalized_summary = t.normalize(summary)
    summary_link = t.find_link_or_ip(summary)
    contains_link = summary_link is not None
    has_spam = t.contains_spam(normalized_summary)

    if t.has_non_standard_text(summary):
        findings.append(Finding("project_summary_non_standard_text", REQUIRED))
    if summary and not contains_link and name and \
            t.text_similarity(summary, name) >= MAX_SUMMARY_NAME_SIMILARITY:
        findings.append(Finding("project_summary_matches_title", REQUIRED))
    summary_length = t.js_len(normalized_summary)
    if summary and not contains_link and summary_length < MIN_SUMMARY_CHARS:
        findings.append(Finding("summary_too_short", REQUIRED,
                                length=summary_length, min_chars=MIN_SUMMARY_CHARS))
    if has_spam:
        findings.append(Finding("project_summary_spam", REQUIRED))
    if summary and t.has_summary_formatting(summary):
        findings.append(Finding("summary_special_formatting", REQUIRED))
    if summary_link:
        findings.append(Finding("project_summary_links", REQUIRED, value=summary_link))
    return findings


# ---------------------------------------------------------------------------
# icon

def check_icon(project):
    if not (project.get("icon_url") or "").strip():
        return [Finding("add_icon", SUGGESTION)]
    return []


# ---------------------------------------------------------------------------
# gallery

def check_gallery(project):
    findings = []
    gallery = project.get("gallery") or []
    project_type = project.get("project_type") or ""
    categories = set(project.get("categories") or []) | set(project.get("additional_categories") or [])

    if project_type == "shader" and len(gallery) < 3:
        findings.append(Finding("upload_gallery_image", REQUIRED, project_type="shader"))
    elif project_type == "resourcepack" and not gallery and not ({"audio", "locale"} & categories):
        findings.append(Finding("upload_gallery_image", REQUIRED, project_type="resourcepack"))

    if not any(item.get("featured") for item in gallery):
        findings.append(Finding("feature_gallery_image", SUGGESTION))
    return findings


# ---------------------------------------------------------------------------
# description (the v2 `body` field)

def check_description(project):
    findings = []
    description = project.get("body") or ""
    summary = project.get("description") or ""
    markdown = t.DescriptionMarkdown(description)
    without_code = markdown.without_code()
    normalized_description = t.normalize(description)
    text = t.extract_description_text(without_code)
    has_spam = t.contains_description_spam(without_code)

    if t.non_standard_ratio(without_code) >= NON_STANDARD_TEXT_FAILURE_THRESHOLD:
        findings.append(Finding("project_description_non_standard_text", REQUIRED))
    if not normalized_description:
        findings.append(Finding("add_description", REQUIRED))
    else:
        description_length = t.js_len(t.normalize(text))
        if description_length < MIN_DESCRIPTION_CHARS:
            findings.append(Finding("description_too_short", REQUIRED,
                                    length=description_length, min_chars=MIN_DESCRIPTION_CHARS))
    if text and summary and \
            t.text_similarity(t.normalize(text), summary) >= MAX_DESCRIPTION_SUMMARY_SIMILARITY:
        findings.append(Finding("project_description_matches_summary", REQUIRED))
    if has_spam:
        findings.append(Finding("project_description_spam", REQUIRED))
    long_headers = markdown.long_header_count()
    if long_headers > 0:
        findings.append(Finding("long_headers", REQUIRED, count=long_headers))
    if markdown.ends_with_header():
        findings.append(Finding("description_ends_with_header", REQUIRED))
    if markdown.has_adjacent_same_level_headers():
        findings.append(Finding("adjacent_headers", REQUIRED))
    if t.has_image_without_alt_text(without_code):
        findings.append(Finding("missing_alt_text", WARNING))
    return findings


# ---------------------------------------------------------------------------
# license

def check_license(project):
    findings = []
    license_info = project.get("license") or {}
    license_id = license_info.get("id") or ""
    license_url = license_info.get("url")

    if is_unknown_license(license_id):
        findings.append(Finding("select_license", REQUIRED,
                                project_type=project.get("project_type") or ""))
    findings.extend(check_custom_license(license_id, license_url))
    return findings


def check_custom_license(license_id, license_url):
    lid = (license_id or "").strip()
    missing_name = not lid or (
        lid.startswith("LicenseRef-")
        and not lid[len("LicenseRef-"):].strip(" -")
    )
    missing_url = not (license_url or "").strip()
    if is_custom_license(lid) and (missing_name or missing_url):
        return [Finding("add_custom_license_details", REQUIRED,
                        field="license", missing_name=missing_name, missing_url=missing_url)]
    return []


# ---------------------------------------------------------------------------
# links

_MD_LINK_EXTRACT_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)[^)]*\)")
_HTML_HREF_RE = re.compile(r"(?is)<a\b[^>]*?href\s*=\s*(?:\"([^\"]*)\"|'([^']*)')")
_BARE_URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>()\[\]\"']+")


def _extract_description_links(body):
    """URLs linked from the description, like upstream links/description.rs extract."""
    markdown = t.DescriptionMarkdown(body or "")
    without_code = markdown.without_code()
    urls = []
    urls.extend(m.group(1) for m in _MD_LINK_EXTRACT_RE.finditer(without_code))
    for m in _HTML_HREF_RE.finditer(without_code):
        urls.append(m.group(1) or m.group(2))
    urls.extend(m.group(0) for m in _BARE_URL_RE.finditer(without_code))
    # markdown image urls count as description embeds (image=True upstream);
    # they only matter for the download check, which skips images
    return [u.rstrip(".,;:!?") for u in urls if u]


def _host(url):
    return (url.hostname or "").rstrip(".")


def _domain_matches(host, domain):
    host = host.lower()
    return host == domain or host.endswith("." + domain)


def _from_domains(parsed, domains):
    host = _host(parsed)
    return any(_domain_matches(host, d) for d in domains)


def _path_parts(parsed):
    return [p for p in parsed.path.split("/") if p]


def _repository_path(parsed):
    parts = _path_parts(parsed)
    return len(parts) >= 2 and parts[0] not in (
        "sponsors", "settings", "login", "join", "explore", "topics")


def _repo_section(parsed, section):
    parts = _path_parts(parsed)
    if not _repository_path(parsed):
        return False
    if len(parts) >= 3 and parts[2] == section:
        return True
    if _from_domains(parsed, GITLAB_DOMAINS):
        return any(a == "-" and b == section for a, b in zip(parts, parts[1:]))
    return False


def _is_github_issues(parsed):
    return (_from_domains(parsed, GITHUB_DOMAINS) and _repository_path(parsed)
            and len(_path_parts(parsed)) >= 3 and _path_parts(parsed)[2] == "issues")


def _discord_code(parsed):
    parts = _path_parts(parsed)
    if _from_domains(parsed, DISCORD_SHORT_INVITE_DOMAINS) and len(parts) == 1:
        code = parts[0]
    elif _from_domains(parsed, DISCORD_INVITE_DOMAINS) and len(parts) == 2 and parts[0] == "invite":
        code = parts[1]
    else:
        return None
    if code and all(c.isalnum() or c in "-_" for c in code):
        return code
    return None


def _known_download(parsed):
    path = parsed.path.lower()
    if "/releases/download/" in path or "/archive/refs/" in path:
        return True
    if _from_domains(parsed, GITHUB_DOMAINS) and "/raw/" in path:
        return True
    if _from_domains(parsed, ["drive.google.com"]) and path in ("/uc", "/download"):
        return True
    if _from_domains(parsed, CURSEFORGE_DOMAINS) and "/download" in path:
        return True
    if _from_domains(parsed, ["api.modrinth.com"]) and path.endswith("/download"):
        return True
    from urllib.parse import parse_qsl
    for key, value in parse_qsl(parsed.query):
        if key in ("download", "dl") and value not in ("0", "false"):
            return True
    return False


def _allowed(field, parsed):
    parts = _path_parts(parsed)
    if field == "source":
        return (_from_domains(parsed, SOURCE_DOMAINS) and _repository_path(parsed)
                and not _is_github_issues(parsed) and not _repo_section(parsed, "wiki"))
    if field == "issues":
        return (
            _is_github_issues(parsed)
            or (_from_domains(parsed, SOURCE_DOMAINS) and not _from_domains(parsed, GITHUB_DOMAINS))
            or (_from_domains(parsed, CURSEFORGE_DOMAINS) and len(parts) == 4
                and parts[0] == "minecraft" and parts[3] == "issues")
            or (_from_domains(parsed, GOOGLE_FORMS_DOMAINS) and parts[:1] == ["forms"])
            or (_from_domains(parsed, GOOGLE_FORMS_SHORT_DOMAINS) and bool(parts))
            or (_from_domains(parsed, MICROSOFT_FORMS_DOMAINS) and bool(parts))
            or (_from_domains(parsed, TYPEFORM_DOMAINS) and len(parts) >= 2 and parts[0] == "to")
        )
    if field == "wiki":
        return _from_domains(parsed, SOURCE_DOMAINS) and _repo_section(parsed, "wiki")
    if field == "discord":
        return _discord_code(parsed) is not None
    if field == "github":
        return (_from_domains(parsed, GITHUB_DOMAINS) and parts[:1] == ["sponsors"]
                and (len(parts) == 2 or (len(parts) == 3 and parts[2] == "sponsorships")))
    if field == "license":
        return _from_domains(parsed, LICENSE_DOMAINS) or (
            _from_domains(parsed, GITHUB_DOMAINS) and _allowed("source", parsed))
    if field in DONATION_DOMAINS:
        return _from_domains(parsed, DONATION_DOMAINS[field])
    return False


def _field_block_reason(field, parsed):
    """Wrong-field / external-blocklist reasons, port of upstream field_block."""
    if field == "wiki" and _from_domains(parsed, SOURCE_DOMAINS):
        return None  # wiki fields accept any source host
    own_pattern = _allowed(field, parsed)
    if field == "issues" and own_pattern:
        return None
    other_checks = [
        ("issues", lambda: _is_github_issues(parsed) if _from_domains(parsed, SOURCE_DOMAINS) else _allowed("issues", parsed)),
        ("wiki", lambda: _allowed("wiki", parsed)),
        ("discord", lambda: _allowed("discord", parsed)),
        ("github", lambda: _allowed("github", parsed)),
        ("patreon", lambda: _allowed("patreon", parsed)),
        ("bmac", lambda: _allowed("bmac", parsed)),
        ("paypal", lambda: _allowed("paypal", parsed)),
        ("ko-fi", lambda: _allowed("ko-fi", parsed)),
        ("license", lambda: _from_domains(parsed, LICENSE_DOMAINS)),
    ]
    for other, check in other_checks:
        if other != field and check():
            return "wrong_field"
    if field != "source" and _from_domains(parsed, SOURCE_DOMAINS) and not own_pattern:
        return "wrong_field"
    if field != "discord" and _from_domains(parsed, DISCORD_REDIRECT_DOMAINS):
        return "wrong_field"
    explicit_exception = field in ("source", "issues", "wiki", "github", "discord", "license") and own_pattern
    if _from_domains(parsed, EXTERNAL_BLOCKS) and not explicit_exception:
        return "external_blocklist_match"
    return None


def validate_link(field, url, in_description=False):
    """Validate one link target. Returns a Finding or None."""
    if len(url) > 2048:
        return _link_finding(field, url, "malformed")
    try:
        parsed = urlparse(url)
    except ValueError:
        return _link_finding(field, url, "malformed")
    if in_description and parsed.scheme == "file":
        return _link_finding(field, url, "download")
    if parsed.scheme not in ("https", "http") \
            or (not in_description and parsed.scheme != "https") \
            or not parsed.hostname \
            or parsed.username \
            or parsed.password:
        return _link_finding(field, url, "malformed")
    if _from_domains(parsed, GLOBAL_BLOCKS):
        return _link_finding(field, url, "global_blocklist_match")
    if in_description:
        if _known_download(parsed):
            return _link_finding(field, url, "download")
        return None
    try:
        import ipaddress
        ipaddress.ip_address(_host(parsed).split("%")[0])
        return _link_finding(field, url, "ip_address")
    except ValueError:
        pass
    reason = _field_block_reason(field, parsed)
    if reason:
        return _link_finding(field, url, reason)
    if field == "source" and _from_domains(parsed, SOURCE_DOMAINS) and not _repository_path(parsed):
        return _link_finding(field, url, "source_repository")
    if field not in OPEN_FIELDS and not _allowed(field, parsed):
        return _link_finding(field, url, "not_in_allowlist", WARNING)
    return None


def project_link_targets(project):
    """(field, url, in_description) for every link attached to the project."""
    targets = []
    for field, key in (("issues", "issues_url"), ("source", "source_url"),
                       ("wiki", "wiki_url"), ("discord", "discord_url")):
        url = project.get(key)
        if url:
            targets.append((field, url, False))
    for donation in project.get("donation_urls") or []:
        url = donation.get("url")
        if url:
            targets.append(((donation.get("id") or donation.get("platform") or "other").lower(), url, False))
    license_url = (project.get("license") or {}).get("url")
    if license_url:
        targets.append(("license", license_url, False))
    for url in _extract_description_links(project.get("body") or ""):
        targets.append(("description", url, True))
    return targets


def check_links(project, versions=None):
    findings = []
    targets = project_link_targets(project)

    for field, url, in_description in targets:
        finding = validate_link(field, url, in_description)
        if finding:
            findings.append(finding)

    seen = {}
    for field, url, in_description in targets:
        if field == "description":
            continue
        seen.setdefault(url, []).append(field)
    for url, fields in seen.items():
        if len(fields) > 1:
            for field in fields:
                other = next(f for f in fields if f != field)
                findings.append(_link_finding(field, url, "duplicate", REQUIRED, other_field=other))

    external = [(f, u) for f, u, d in targets if not d]
    if not external:
        findings.append(Finding("add_links", SUGGESTION))

    project_type = project.get("project_type") or ""
    license_id = (project.get("license") or {}).get("id") or ""
    has_source = bool(project.get("source_url"))
    versions = versions or []
    if project_type in ("mod", "plugin") \
            and license_id in SOURCE_REQUIRING_LICENSES \
            and not has_source \
            and not (versions and all(len(v.get("files") or []) >= 2 for v in versions)):
        findings.append(Finding("gpl_license_source_required", REQUIRED,
                                project_type=project_type, field="source"))
    return findings


# ---------------------------------------------------------------------------
# tags

def check_tags(project, available_categories=None):
    findings = []
    categories = project.get("categories") or []
    additional = project.get("additional_categories") or []
    tag_count = len(categories) + len(additional)
    project_type = project.get("project_type") or ""

    if project.get("versions") and not categories:
        findings.append(Finding("select_tags", SUGGESTION))

    if tag_count > MAX_TAG_COUNT:
        findings.append(Finding("too_many_tags", WARNING,
                                tag_count=tag_count, max_tag_count=MAX_TAG_COUNT))

    resolution = sorted(
        (tag for tag in list(categories) + additional if tag in RESOLUTION_TAGS),
        key=RESOLUTION_TAGS.index,
    )
    if project_type == "resourcepack" and len(resolution) > 1:
        findings.append(Finding("multiple_resolution_tags", WARNING,
                                count=len(resolution), tags="|".join(resolution)))

    if available_categories is not None:
        available = {c.get("category") or c.get("name") for c in available_categories
                     if c.get("project_type") == project_type}
        available.discard(None)
        selected = set(categories) | set(additional)
        if available and available <= selected:
            findings.append(Finding("all_tags_selected", REQUIRED,
                                    total_available_tags=len(available)))
    return findings


# ---------------------------------------------------------------------------
# versions

def check_versions(project, versions=None):
    findings = []
    version_ids = project.get("versions")
    if versions is not None:
        has_versions = len(versions) > 0
    else:
        has_versions = bool(version_ids)
    if not has_versions:
        findings.append(Finding("upload_version", REQUIRED))

    if project.get("project_type") in ("mod", "modpack"):
        sides = [project.get("client_side"), project.get("server_side")]
        if any(s is None or not str(s).strip() or s == "unknown" for s in sides):
            findings.append(Finding("select_environment", REQUIRED))
    return findings


# ---------------------------------------------------------------------------

def run_all(project, versions=None, available_categories=None):
    """Every local check, in upstream validator order."""
    findings = []
    findings.extend(check_name(project))
    findings.extend(check_summary(project))
    findings.extend(check_icon(project))
    findings.extend(check_gallery(project))
    findings.extend(check_description(project))
    findings.extend(check_license(project))
    findings.extend(check_links(project, versions))
    findings.extend(check_tags(project, available_categories))
    findings.extend(check_versions(project, versions))
    return findings
