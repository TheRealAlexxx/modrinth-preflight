"""Text and Markdown helpers, ported from Modrinth's validator.

Ports of the heuristics in apps/labrinth/src/validate/project/text.rs and
description/markdown.rs (github.com/modrinth/code, fetched 2026-10-18),
using only the Python standard library. Where upstream relies on Rust
crates (pulldown-cmark, linkify, psl) we use close stdlib approximations;
differences are noted per function.
"""

import html
import ipaddress
import re
import unicodedata

# ---------------------------------------------------------------------------
# basic text


def normalize(text):
    """Trim + NFC, as upstream normalize_project_field_text."""
    return unicodedata.normalize("NFC", text.strip())


def js_len(text):
    """Length in UTF-16 code units, matching JavaScript's String.length."""
    return len(text.encode("utf-16-le", "surrogatepass")) // 2


def _levenshtein(left, right):
    if len(left) > len(right):
        left, right = right, left
    previous = list(range(len(left) + 1))
    for rj, rc in enumerate(right, 1):
        current = [rj]
        for li, lc in enumerate(left, 1):
            current.append(min(current[-1] + 1, previous[li] + 1, previous[li - 1] + (lc != rc)))
        previous = current
    return previous[-1]


def text_similarity(left, right):
    """1 - levenshtein/longest over lowercase text with whitespace removed."""
    left = [c for c in normalize(left).lower() if not c.isspace()]
    right = [c for c in normalize(right).lower() if not c.isspace()]
    longest = max(len(left), len(right))
    if longest == 0:
        return 0.0
    return 1.0 - _levenshtein(left, right) / longest


_WORD_RE = re.compile(r"[\w]+", re.UNICODE)


def contains_spam(text):
    """Summary spam: 8+ repeated chars, 4+ repeated words, or a phrase x3."""
    normalized = normalize(text).lower()
    previous = None
    repeated = 0
    for ch in normalized:
        if not ch.isspace() and previous == ch:
            repeated += 1
        else:
            repeated = 0 if ch.isspace() else 1
            previous = ch
        if repeated >= 8:
            return True
    words = _WORD_RE.findall(normalized)
    run = 1
    for a, b in zip(words, words[1:]):
        run = run + 1 if a == b else 1
        if run >= 4:
            return True
    max_phrase = min(8, len(words) // 3)
    for size in range(max_phrase, 1, -1):
        for start in range(0, len(words) - size * 3 + 1):
            phrase = words[start:start + size]
            if phrase == words[start + size:start + size * 2] == words[start + size * 2:start + size * 3]:
                return True
    return False


# ---------------------------------------------------------------------------
# non-standard ("fancy" / zalgo) text


def _nonstandard_char(ch):
    cp = ord(ch)
    if 0x1D400 <= cp <= 0x1D7FF:      # mathematical alphanumeric symbols
        return True
    if 0x2460 <= cp <= 0x24FF:        # enclosed alphanumerics
        return True
    if 0xFF01 <= cp <= 0xFF5E:        # fullwidth ASCII variants
        return True
    if 0x1F130 <= cp <= 0x1F19F:      # squared letters (flags 1F1E6+ excluded)
        return unicodedata.category(ch) == "So"
    return False


def non_standard_ratio(text):
    """Share of characters that are 'fancy' variants or zalgo combining runs."""
    total = 0
    bad = 0
    combining_run = 0
    for ch in text:
        if ch.isspace():
            continue
        total += 1
        if unicodedata.category(ch) == "Mn":
            combining_run += 1
            if combining_run >= 4:
                bad += 1
        else:
            combining_run = 0
            if _nonstandard_char(ch):
                bad += 1
    return (bad / total) if total else 0.0


def has_non_standard_text(text):
    """Upstream has_non_standard_text approximation (name/summary fields)."""
    # Any single fancy character in a short field is treated as non-standard;
    # zalgo is caught by combining-mark density or a long combining run.
    for ch in text:
        if _nonstandard_char(ch):
            return True
    chars = [ch for ch in text if not ch.isspace()]
    if not chars:
        return False
    combining = sum(1 for ch in chars if unicodedata.category(ch) == "Mn")
    if combining / len(chars) > 0.15:
        return True
    combining_run = 0
    for ch in text:
        if unicodedata.category(ch) == "Mn":
            combining_run += 1
            if combining_run >= 4:
                return True
        else:
            combining_run = 0
    return False


# ---------------------------------------------------------------------------
# links inside free text

_URL_RE = re.compile(
    r"(?:https?://[^\s<>()\[\]\"']+|www\.[^\s<>()\[\]\"']+|(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?|(?:[\w-]+\.)+(?:"
    r"com|net|org|io|dev|gg|app|me|co|uk|net|info|xyz|site|online|store|tech|"
    r"cc|tv|fm|zone|world|build|software|systems|digital|cloud|host|website|"
    r"de|fr|nl|eu|us|ca|au|jp|cn|in|br|se|fi|no|dk|pl|it|es|pt|cz|sk|at|ch|"
    r"be|ie|gr|tr|ru|ua|kr|sg|hk|tw|mx|ar|cl|nz|za|il|ae|sa|id|vn|th|ph|my)"
    r"(?:/[^\s<>()\[\]\"']*)?)",
    re.IGNORECASE,
)


def find_link_or_ip(text):
    """First URL or IP literal in text, or None.

    Approximates upstream find_link_or_ip (linkify + public-suffix check)
    with a regex covering scheme URLs, www. URLs and common-TLD domains.
    """
    for match in _URL_RE.finditer(text):
        raw = match.group(0).rstrip(".,;:!?")
        if "://" in raw:
            return raw
        host = raw.split("/", 1)[0].split(":", 1)[0]
        if host.lower().startswith("www."):
            return raw
        try:
            ipaddress.ip_address(host)
            return raw
        except ValueError:
            pass
        # bare domain with a plausible TLD (the regex already restricted TLDs)
        return raw
    return None


# ---------------------------------------------------------------------------
# summary formatting

_MD_LINK_RE = re.compile(r"\[[^\]]*\]\([^)]*\)")
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
_CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
_HTML_TAG_PAIR_RE = re.compile(r"</?(?:b|strong|i|em|u|s|del|ins|a|code|pre|span|div|p|h[1-6]|ul|ol|li|blockquote|br|img|table|tr|td|th)\b[^>]*>", re.IGNORECASE)


def has_paired_html_formatting(text):
    without_code = _CODE_BLOCK_RE.sub("", text)
    without_code = _INLINE_CODE_RE.sub("", without_code)
    return bool(_HTML_TAG_PAIR_RE.search(without_code))


def has_summary_formatting(text):
    if has_paired_html_formatting(text):
        return True
    if _MD_LINK_RE.search(text):
        return True
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(("#", ">", "- ", "* ", "+ ", "```")):
            return True
        if "**" in line or "__" in line or "~~" in line:
            return True
        if _INLINE_CODE_RE.search(line):
            return True
    return False


# ---------------------------------------------------------------------------
# description markdown

_FENCED_BLOCK_RE = re.compile(r"^(```|~~~).*$", re.MULTILINE)
_MD_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_MD_FULL_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")
_HTML_IMAGE_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_HTML_ALT_RE = re.compile(r"alt\s*=\s*(?:\"([^\"]*)\"|'([^']*)')", re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")
_HTML_ENTITY_RE = re.compile(r"&(?:#\d+|#x[0-9a-fA-F]+|[a-zA-Z]+);")
_HTML_HEADER_RE = re.compile(r"(?is)<h([1-6])\b[^>]*>(.*?)</h\1>")
_ADJACENT_HTML_HEADERS_RE = re.compile(r"(?is)</h([1-6])>\s*<h([1-6])\b")
_TRAILING_HTML_HEADER_RE = re.compile(r"(?is)</h[1-6]>\s*(?:</[a-z][^>]*>\s*)*$")
_ATX_HEADER_RE = re.compile(r"^(#{1,6})[ \t]+(.*)$")


class DescriptionMarkdown:
    """Line-based Markdown structure with code regions blanked out.

    Approximates the pulldown-cmark parsing upstream uses; setext (===/---)
    headings are not detected.
    """

    def __init__(self, markdown):
        self.markdown = markdown
        self.code_ranges = []   # (start, end) char ranges
        self.headings = []      # (level, rendered_text, start, end)
        self._parse()

    def _parse(self):
        in_fence = None
        fence_start = 0
        pos = 0
        for line in self.markdown.splitlines(keepends=True):
            stripped = line.strip()
            fence = _FENCED_BLOCK_RE.match(line)
            if in_fence:
                if fence and stripped.startswith(in_fence):
                    self.code_ranges.append((fence_start, pos + len(line)))
                    in_fence = None
            elif fence:
                in_fence = fence.group(1)
                fence_start = pos
            else:
                header = _ATX_HEADER_RE.match(line)
                if header:
                    rendered = _render_inline(header.group(2).strip())
                    self.headings.append((len(header.group(1)), rendered, pos, pos + len(line)))
                else:
                    for m in _INLINE_CODE_RE.finditer(line):
                        self.code_ranges.append((pos + m.start(), pos + m.end()))
            pos += len(line)
        if in_fence is not None:
            self.code_ranges.append((fence_start, len(self.markdown)))

    def replace_code(self, replacement):
        if not self.code_ranges:
            return self.markdown
        out = []
        prev = 0
        for start, end in self.code_ranges:
            out.append(self.markdown[prev:start])
            out.append(replacement)
            prev = end
        out.append(self.markdown[prev:])
        return "".join(out)

    def without_code(self):
        return self.replace_code(" ")

    def long_header_count(self):
        count = sum(1 for _, text, _, _ in self.headings if _header_is_long(text))
        without_code = self.without_code()
        count += sum(
            1 for m in _HTML_HEADER_RE.finditer(without_code)
            if _header_is_long(_strip_html(m.group(2)))
        )
        return count

    def ends_with_header(self):
        if self.headings:
            if not self.markdown[self.headings[-1][3]:].strip():
                return True
        without_code = self.replace_code("\n[code]\n")
        return bool(_TRAILING_HTML_HEADER_RE.search(without_code.rstrip()))

    def has_adjacent_same_level_headers(self):
        for (prev_level, _, _, prev_end), (level, _, start, _) in zip(self.headings, self.headings[1:]):
            if prev_level == level and not self.markdown[prev_end:start].strip():
                return True
        without_code = self.replace_code("\n[code]\n")
        return any(
            m.group(1) == m.group(2)
            for m in _ADJACENT_HTML_HEADERS_RE.finditer(without_code)
        )


def _render_inline(text):
    """Strip inline markdown formatting, keeping visible text."""
    text = _MD_FULL_LINK_RE.sub(r"\1", text)
    text = _MD_IMAGE_RE.sub("", text)
    text = _INLINE_CODE_RE.sub(lambda m: m.group(0)[1:-1], text)
    for marker in ("**", "__", "~~", "*", "_"):
        text = text.replace(marker, "")
    return text.strip()


def _strip_html(text):
    return html.unescape(_HTML_TAG_RE.sub("", text)).strip()


def _header_is_long(rendered_text):
    # upstream: more than 80 graphemes; code points are a close approximation
    return len(rendered_text) > 80


def extract_description_text(markdown_without_code):
    """Plain visible text of a description, for length measurement."""
    text = _MD_IMAGE_RE.sub(" ", markdown_without_code)
    text = _HTML_IMAGE_RE.sub(" ", text)
    text = _MD_FULL_LINK_RE.sub(r"\1", text)
    text = _HTML_TAG_RE.sub(" ", text)
    text = _HTML_ENTITY_RE.sub(" ", text)
    out = []
    for line in text.splitlines():
        stripped = line.lstrip()
        stripped = _ATX_HEADER_RE.sub(lambda m: m.group(2), stripped)
        stripped = stripped.lstrip("#> \t")
        out.append(stripped)
    return _render_inline(" ".join(out))


def has_image_without_alt_text(markdown_without_code):
    for m in _MD_IMAGE_RE.finditer(markdown_without_code):
        if not m.group(1).strip():
            return True
    for m in _HTML_IMAGE_RE.finditer(markdown_without_code):
        alt = _HTML_ALT_RE.search(m.group(0))
        if alt is None or not (alt.group(1) or alt.group(2) or "").strip():
            return True
    return False


# ---------------------------------------------------------------------------
# description spam

_SPAM_MIN_CHAR_RUN = 16
_SPAM_MIN_CHAR_EXCESS = 20
_SPAM_MIN_CHAR_EXCESS_PERCENT = 10
_SPAM_EXTREME_CHAR_RUN = 64
_SPAM_MIN_REPEATED_WORDS = 6
_SPAM_MIN_REPEATED_PHRASE_WORDS = 12
_SPAM_MIN_DUPLICATE_BLOCK_PERCENT = 20
_NGRAM_WORDS = 4
_NGRAM_MIN_WORDS = 30
_NGRAM_MIN_DUPLICATE_PERCENT = 50
_NGRAM_MIN_COVERED_PERCENT = 70

_SPAM_TOKEN_RE = re.compile(r"[^\s/\\|*_~#>`-]+")
_DESCRIPTION_LINK_RE = re.compile(r"(?:[a-zA-Z][a-zA-Z0-9+.-]*://|www\.)[^\s<>()\[\]]+")


def contains_description_spam(markdown_without_code):
    """Port of upstream contains_description_spam (same thresholds)."""
    blocks = _description_spam_blocks(markdown_without_code)
    block_counts = {}
    visible_characters = 0
    repeated_character_excess = 0
    longest_run = 0
    total_words = 0

    for block in blocks:
        words = _spam_words(block)
        if not words:
            continue
        total_words += len(words)
        visible, excess, run = _character_repetition(words)
        visible_characters += visible
        repeated_character_excess += excess
        longest_run = max(longest_run, run)
        if (
            _has_repeated_words(words, _SPAM_MIN_REPEATED_WORDS)
            or _has_repeated_phrase(words, _SPAM_MIN_REPEATED_PHRASE_WORDS)
            or _has_repeated_ngram_density(words)
        ):
            return True
        if _is_duplicate_block_candidate(block):
            key = tuple(words)
            block_counts[key] = block_counts.get(key, 0) + 1

    duplicate_block_words = sum(
        len(words) * (count - 1)
        for words, count in block_counts.items()
        if count >= 3 and len(words) * count >= _SPAM_MIN_REPEATED_PHRASE_WORDS
    )
    if duplicate_block_words > 0 and duplicate_block_words * 100 >= total_words * _SPAM_MIN_DUPLICATE_BLOCK_PERCENT:
        return True

    return longest_run >= _SPAM_EXTREME_CHAR_RUN or (
        longest_run >= _SPAM_MIN_CHAR_RUN
        and repeated_character_excess >= _SPAM_MIN_CHAR_EXCESS
        and visible_characters > 0
        and repeated_character_excess * 100 >= visible_characters * _SPAM_MIN_CHAR_EXCESS_PERCENT
    )


def _description_spam_blocks(markdown):
    text = _INLINE_CODE_RE.sub(lambda m: m.group(0)[1:-1], markdown)
    text = _MD_IMAGE_RE.sub(" ", text)
    text = _MD_FULL_LINK_RE.sub(r"\1", text)
    text = _HTML_IMAGE_RE.sub(" ", text)
    text = _HTML_TAG_RE.sub(" ", text)
    text = _HTML_ENTITY_RE.sub(" ", text)
    text = _DESCRIPTION_LINK_RE.sub(" ", text)

    blocks = []
    paragraph = ""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            if paragraph:
                blocks.append(paragraph)
                paragraph = ""
            continue
        if _is_standalone_spam_block(line):
            if paragraph:
                blocks.append(paragraph)
                paragraph = ""
            blocks.append(line)
        else:
            paragraph = (paragraph + " " + line) if paragraph else line
    if paragraph:
        blocks.append(paragraph)
    return blocks


def _is_standalone_spam_block(line):
    trimmed = line.lstrip(">").lstrip()
    if trimmed.startswith("#"):
        return True
    if trimmed.startswith(("- ", "* ", "+ ", "\u2022")):
        return True
    if "|" in trimmed:
        return True
    head, sep, _ = trimmed.partition(". ")
    if sep and head.isdigit():
        return True
    return False


def _is_duplicate_block_candidate(block):
    trimmed = block.lstrip(">").lstrip()
    return not trimmed.startswith("#") and "|" not in trimmed


def _spam_words(text):
    return [w.lower() for w in (unicodedata.normalize("NFC", m.group(0)) for m in _SPAM_TOKEN_RE.finditer(text))]


def _character_repetition(words):
    visible = 0
    excess = 0
    longest = 0
    for word in words:
        chars = list(word)
        visible += len(chars)
        previous = None
        run = 0
        for ch in chars:
            if ch == previous:
                run += 1
            else:
                excess += max(0, run - 3)
                longest = max(longest, run)
                previous = ch
                run = 1
        excess += max(0, run - 3)
        longest = max(longest, run)
    return visible, excess, longest


def _has_repeated_words(words, minimum):
    repetitions = 1
    for a, b in zip(words, words[1:]):
        repetitions = repetitions + 1 if a == b else 1
        if repetitions >= minimum:
            return True
    return False


def _has_repeated_phrase(words, minimum_repeated_words):
    max_phrase = min(8, len(words) // 3)
    for size in range(max_phrase, 1, -1):
        for start in range(0, len(words) - size * 3 + 1):
            phrase = words[start:start + size]
            repetitions = 1
            while (
                start + size * (repetitions + 1) <= len(words)
                and phrase == words[start + size * repetitions:start + size * (repetitions + 1)]
            ):
                repetitions += 1
            if repetitions >= 3 and size * repetitions >= minimum_repeated_words:
                return True
    return False


def _has_repeated_ngram_density(words):
    if len(words) < _NGRAM_MIN_WORDS:
        return False
    ngram_counts = {}
    ngrams = [tuple(words[i:i + _NGRAM_WORDS]) for i in range(len(words) - _NGRAM_WORDS + 1)]
    for ngram in ngrams:
        ngram_counts[ngram] = ngram_counts.get(ngram, 0) + 1
    total = len(ngrams)
    duplicates = sum(count - 1 for count in ngram_counts.values())
    if duplicates * 100 < total * _NGRAM_MIN_DUPLICATE_PERCENT:
        return False
    covered = [False] * len(words)
    for start, ngram in enumerate(ngrams):
        if ngram_counts[ngram] > 1:
            for i in range(start, start + _NGRAM_WORDS):
                covered[i] = True
    return sum(covered) * 100 >= len(words) * _NGRAM_MIN_COVERED_PERCENT
