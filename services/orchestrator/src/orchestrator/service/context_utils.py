"""Pure-function utilities for RAG context trimming: section extraction, dedup, limit."""
import re

_HEADER_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)
_WORD_RE = re.compile(r"\w+", re.UNICODE)


# ---------------------------------------------------------------------------
# 1. Section-aware extraction
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> set[str]:
    """Lowercase words of length >= 2."""
    return {w for w in _WORD_RE.findall(text.lower()) if len(w) >= 2}


def extract_relevant_section(text: str, question: str) -> str:
    """Return only the markdown section most relevant to *question*.

    If the text has no markdown headers or no section scores high enough,
    return the original text unchanged.
    """
    headers = list(_HEADER_RE.finditer(text))
    if not headers:
        return text

    # Build (level, title, start, end) tuples
    sections: list[tuple[int, str, int, int]] = []
    for i, m in enumerate(headers):
        level = len(m.group(1))
        title = m.group(2).strip()
        start = m.start()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        sections.append((level, title, start, end))

    if not sections:
        return text

    q_words = _tokenize(question)
    if not q_words:
        return text

    best_idx = -1
    best_overlap = 0
    for i, (_, title, _, _) in enumerate(sections):
        h_words = _tokenize(title)
        overlap = len(q_words & h_words)
        if overlap > best_overlap:
            best_overlap = overlap
            best_idx = i

    if best_overlap >= 2 and best_idx >= 0:
        _, _, start, end = sections[best_idx]
        return text[start:end].strip()

    return text


# ---------------------------------------------------------------------------
# 2. Line-level dedup + fragment repair
# ---------------------------------------------------------------------------

_ENDS_WITH_PUNCT = re.compile(r"[.!?:;]\s*$")


def normalize_and_dedup(text: str) -> str:
    """Normalize whitespace, deduplicate consecutive lines, repair fragment joins."""
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)

    lines = text.split("\n")
    result: list[str] = []
    for line in lines:
        # Skip consecutive duplicate lines
        if result and line == result[-1]:
            continue
        # Fragment repair: line starts lowercase and prev line lacks terminal punctuation
        if (
            result
            and line
            and line[0].islower()
            and result[-1]
            and not _ENDS_WITH_PUNCT.search(result[-1])
        ):
            prev = result[-1].rstrip()
            # If prev line ends with a letter (mid-word break), join without space
            sep = "" if prev and prev[-1].isalpha() else " "
            result[-1] = prev + sep + line.lstrip()
            continue
        result.append(line)
    return "\n".join(result)


# ---------------------------------------------------------------------------
# 3. Trim to character limit without mid-word cuts
# ---------------------------------------------------------------------------

_SENTENCE_END = re.compile(r"[.!?]\s+|\n")


def trim_to_limit(text: str, max_chars: int) -> str:
    """Truncate *text* to at most *max_chars*, cutting at sentence / word boundary."""
    if not text or len(text) <= max_chars:
        return text

    # Try last sentence-end before max_chars
    last = -1
    for m in _SENTENCE_END.finditer(text[:max_chars]):
        last = m.end()
    if last > max_chars // 2:
        return text[:last].rstrip()

    # Fallback: last whitespace
    ws = text[:max_chars].rfind(" ")
    if ws > max_chars // 2:
        return text[:ws].rstrip()

    return text[:max_chars].rstrip()
