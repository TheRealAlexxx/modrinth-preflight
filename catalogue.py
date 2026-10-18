"""Catalogue of Modrinth project validation nags.

The nag kinds mirror the ProjectNagKind enum in Modrinth's backend
(apps/labrinth/src/validate/project/mod.rs in github.com/modrinth/code,
fetched 2026-10-18). Titles and messages here are our own wording; the
kind identifiers, severities and thresholds match upstream.

severity is the default Modrinth assigns; link_validation varies by
details.reason and is resolved in checks.py / preflight.py.
"""

# severity ranks: required > warning > suggestion
REQUIRED = "required"
WARNING = "warning"
SUGGESTION = "suggestion"
SEVERITIES = (REQUIRED, WARNING, SUGGESTION)

# kind -> (section, default severity, message template)
# Message templates may reference {placeholders} filled from nag details.
NAGS = {
    # name
    "project_name_slur": ("name", REQUIRED, "The project name contains an offensive term: {value}."),
    "project_name_profanity": ("name", REQUIRED, "The project name contains profanity: {value}."),
    "project_name_non_standard_text": ("name", REQUIRED, "The project name uses non-standard characters (fancy text or zalgo)."),
    "project_name_version": ("name", REQUIRED, "The project name includes a version number. Version numbers belong in versions, not the title."),
    "minecraft_title_clause": ("name", REQUIRED, "The name uses Minecraft's branding. \"Minecraft\" must not be a significant part of the name."),
    # summary
    "project_summary_slur": ("summary", REQUIRED, "The summary contains an offensive term: {value}."),
    "project_summary_profanity": ("summary", REQUIRED, "The summary contains profanity: {value}."),
    "project_summary_non_standard_text": ("summary", REQUIRED, "The summary uses non-standard characters (fancy text or zalgo)."),
    "project_summary_non_english": ("summary", REQUIRED, "The summary must be written in English or include an English translation."),
    "project_summary_matches_title": ("summary", REQUIRED, "The summary repeats the project name. It should add new information."),
    "summary_too_short": ("summary", REQUIRED, "The summary is too brief ({length}/{min_chars} characters). Add a sentence describing the project."),
    "project_summary_spam": ("summary", REQUIRED, "The summary contains repeated characters, words or phrases used as padding."),
    "summary_special_formatting": ("summary", REQUIRED, "The summary contains Markdown or HTML. It can only display plain text."),
    "project_summary_links": ("summary", REQUIRED, "The summary contains a link or IP address: {value}. Links do not belong in the summary."),
    # icon
    "add_icon": ("icon", SUGGESTION, "The project has no icon. A unique, relevant icon makes it identifiable in search."),
    # gallery
    "gallery_text_slur": ("gallery", REQUIRED, "Gallery image #{gallery_index} {field} contains an offensive term: {value}."),
    "gallery_text_profanity": ("gallery", REQUIRED, "Gallery image #{gallery_index} {field} contains profanity: {value}."),
    "gallery_text_non_standard": ("gallery", REQUIRED, "Gallery image #{gallery_index} {field} uses non-standard characters."),
    "upload_gallery_image": ("gallery", REQUIRED, "The project has too few gallery images. Shaders need at least 3; resource packs need at least 1 unless tagged audio or locale."),
    "feature_gallery_image": ("gallery", SUGGESTION, "No gallery image is featured. The featured image is the project's first impression in search."),
    # description
    "project_description_slur": ("description", REQUIRED, "The description contains an offensive term: {value}."),
    "project_description_profanity": ("description", REQUIRED, "The description contains excessive profanity. Detected: {value}."),
    "project_description_non_standard_text": ("description", REQUIRED, "The description makes excessive use of non-standard characters (fancy text or zalgo)."),
    "project_description_non_english": ("description", REQUIRED, "The description must be written in English or include an English translation."),
    "project_description_matches_summary": ("description", REQUIRED, "The description repeats the summary. It should provide unique information."),
    "add_description": ("description", REQUIRED, "The project has no description. A description covering content, purpose and appeal is required."),
    "description_too_short": ("description", REQUIRED, "The description is too brief ({length}/{min_chars} characters). Add detail about content, purpose and appeal."),
    "project_description_spam": ("description", REQUIRED, "The description contains repeated characters, words or blocks used as padding."),
    "long_headers": ("description", REQUIRED, "{count} header(s) in the description are too long. Headers are section titles, not full sentences."),
    "description_ends_with_header": ("description", REQUIRED, "The description ends with a header that has no text under it."),
    "adjacent_headers": ("description", REQUIRED, "Two headers of the same level sit next to each other with no text between them."),
    "missing_alt_text": ("description", WARNING, "Some description images are missing alt text, which matters for accessibility."),
    # license
    "select_license": ("license", REQUIRED, "No license is selected. Choose the license the project is distributed under."),
    "add_custom_license_details": ("license", REQUIRED, "The custom license is missing a name or a URL. Add a valid URL and a name or SPDX identifier."),
    # links
    "add_links": ("links", SUGGESTION, "The project has no external links. A source, issues or wiki link helps users trust and evaluate it."),
    "add_links_server": ("links", SUGGESTION, "The listing has no external links. A website or community link helps players evaluate the server."),
    "link_validation": ("links", REQUIRED, "Link problem in {field}: {reason_message} ({url})"),
    "gpl_license_source_required": ("links", REQUIRED, "The license ({project_type} under a copyleft license) requires published source code. Add a source link or attach source files."),
    # permissions
    "review_permissions": ("permissions", REQUIRED, "A version file needs attribution review. Confirm you have permission to redistribute every bundled file."),
    # server settings
    "select_country": ("server", REQUIRED, "No region is selected. Players need to know where the server is located."),
    "all_languages": ("server", REQUIRED, "Every available language is selected. List only languages the server actively supports."),
    "add_java_address": ("server", REQUIRED, "No Java address. Add the IP and port Java Edition players use to join."),
    "select_compatibility": ("server", REQUIRED, "No compatibility selected. Choose the versions the server supports."),
    "too_many_languages": ("server", WARNING, "{language_count} languages selected (max 10). List only actively supported languages."),
    "select_language": ("server", SUGGESTION, "No languages listed. Add the language or languages the server supports."),
    # tags
    "select_tags": ("tags", SUGGESTION, "No tags selected. Tags help users find the project in search."),
    "too_many_tags": ("tags", WARNING, "{tag_count} tags selected (max {max_tag_count}). Fewer, accurate tags rank better in search."),
    "too_many_tags_server": ("tags", REQUIRED, "{tag_count} tags selected (max {max_tag_count} for servers)."),
    "multiple_resolution_tags": ("tags", WARNING, "{count} resolution tags selected ({tags}). Resource packs should carry only their primary resolution."),
    "all_tags_selected": ("tags", REQUIRED, "All {total_available_tags} available tags are selected. Select only relevant tags."),
    # versions
    "upload_version": ("versions", REQUIRED, "No versions uploaded. At least one version is required to submit for review."),
    "select_environment": ("versions", REQUIRED, "No environment specified. Set where the project runs (client and/or server side)."),
    # disclosures
    "check_disclosures": ("disclosures", SUGGESTION, "No disclosures set. Review whether the project uses AI, ads, telemetry, paid features or similar, and disclose it."),
    "disclosures_special_formatting": ("disclosures", REQUIRED, "A disclosure note contains Markdown or HTML. Disclosure notes are plain text."),
    # moderation
    "moderator_feedback": ("moderation", WARNING, "The project has moderator feedback from a previous rejection. Read the moderation thread before resubmitting."),
}

# link_validation details.reason -> (severity, human message)
LINK_REASONS = {
    "malformed": (REQUIRED, "the URL is malformed, over 2048 characters, not HTTPS, or contains credentials"),
    "global_blocklist_match": (REQUIRED, "the domain is prohibited everywhere on Modrinth (link shortener, placeholder, or piracy site)"),
    "external_blocklist_match": (REQUIRED, "this kind of link is not allowed in external link fields (social media, video, or unrelated host)"),
    "wrong_field": (REQUIRED, "the URL belongs in a different link field"),
    "ip_address": (REQUIRED, "raw IP addresses are not allowed as links"),
    "not_in_allowlist": (WARNING, "the URL does not look like a typical link for this field; double check it"),
    "duplicate": (REQUIRED, "the same URL is also used in the {other_field} field"),
    "unverifiable": (WARNING, "the URL could not be verified as reachable"),
    "download": (REQUIRED, "direct download links are not allowed here"),
    "discord_invite": (REQUIRED, "the Discord invite link is not a valid invite URL"),
    "source_repository": (REQUIRED, "the source link must point at a source repository, not a site home page"),
}


def severity_rank(severity):
    return SEVERITIES.index(severity)


def render(kind, details=None):
    """Return (section, severity, message) for a nag kind."""
    details = details or {}
    kind = kind.replace("-", "_")
    if kind == "link_validation":
        reason = details.get("reason", "")
        severity, reason_message = LINK_REASONS.get(
            reason, (REQUIRED, "the link failed validation (%s)" % reason)
        )
        merged = dict(details)
        merged["reason_message"] = reason_message.format(**{k: v for k, v in details.items() if k != "reason_message"}) if "{" in reason_message else reason_message
        section, _, template = NAGS[kind]
        return section, severity, _fill(template, merged)
    if kind not in NAGS:
        return "unknown", WARNING, "Unrecognized check '%s' (Modrinth may have added it recently). Details: %s" % (kind, details)
    section, severity, template = NAGS[kind]
    return section, severity, _fill(template, details)


def _fill(template, details):
    class _Safe(dict):
        def __missing__(self, key):
            return "{" + key + "}"
    try:
        return template.format_map(_Safe({k: v for k, v in details.items()}))
    except Exception:
        return template
