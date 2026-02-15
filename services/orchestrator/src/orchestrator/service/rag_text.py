"""RAG text utilities: Russian-aware tokenization, markdown section extraction, normalization."""
import re

_WORD_RE = re.compile(r"[^\W\d_]+|\d+", re.UNICODE)
_HEADER_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)
_ENDS_WITH_PUNCT = re.compile(r"[.!?:;]\s*$")

# Minimal expansion so "виснет" matches section "зависает" / "обрывается"
_QUERY_EXPAND: dict[str, list[str]] = {
    "виснет": ["зависает", "обрывается"],
    "висне": ["зависает", "обрывается"],
}


def tokenize_ru(text: str) -> set[str]:
    """Lowercase, ё→е, drop punctuation, words len>=2; primitive stem: add word[:-1] for len>4, word[:-2] for len>6."""
    if not text:
        return set()
    s = text.lower().replace("ё", "е")
    words = _WORD_RE.findall(s)
    out: set[str] = set()
    for w in words:
        if len(w) < 2:
            continue
        out.add(w)
        if len(w) > 4:
            out.add(w[:-1])
        if len(w) > 6:
            out.add(w[:-2])
    return out


def split_markdown_sections(md: str) -> list[dict]:
    """Split by ## and # headers. Return list of {header, level, body, raw}."""
    sections: list[dict] = []
    headers = list(_HEADER_RE.finditer(md))
    if not headers:
        if md.strip():
            sections.append({"header": None, "level": 0, "body": md.strip(), "raw": md.strip()})
        return sections
    for i, m in enumerate(headers):
        level = len(m.group(1))
        title = m.group(2).strip()
        start = m.start()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(md)
        body = md[m.end() : end].strip()
        raw = md[start:end].strip()
        sections.append({"header": title, "level": level, "body": body, "raw": raw})
    return sections


def best_section(md: str, query: str) -> str:
    """Return the best-matching markdown section for the query, or full md if no good match."""
    sections = split_markdown_sections(md)
    if not sections or (len(sections) == 1 and sections[0].get("header") is None):
        return md
    q_tokens = tokenize_ru(query)
    for t in list(q_tokens):
        for add in _QUERY_EXPAND.get(t, []):
            q_tokens.add(add)
    best_idx = -1
    best_score = -1
    for i, sec in enumerate(sections):
        header = sec.get("header") or ""
        body = sec.get("body") or ""
        combined = f"{header} {body}"
        sec_tokens = tokenize_ru(combined)
        score = len(q_tokens & sec_tokens)
        if header and q_tokens & tokenize_ru(header):
            score += 2
        if score > best_score:
            best_score = score
            best_idx = i
    if best_score < 2 or best_idx < 0:
        return md
    raw = sections[best_idx]["raw"]
    return safe_trim(raw, 1200)


def normalize_text(text: str) -> str:
    """Normalize newlines, collapse 3+ blanks, dedup consecutive lines, join fragment lines."""
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = text.split("\n")
    result: list[str] = []
    for line in lines:
        if result and line == result[-1]:
            continue
        if (
            result
            and line
            and (line[0].islower() or line[0].isdigit())
            and result[-1]
            and not _ENDS_WITH_PUNCT.search(result[-1])
        ):
            prev = result[-1].rstrip()
            sep = "" if prev and prev[-1].isalpha() else " "
            result[-1] = prev + sep + line.lstrip()
            continue
        result.append(line)
    return "\n".join(result)


def safe_trim(text: str, max_chars: int) -> str:
    """Trim to max_chars at last newline, sentence end, or space within 200 chars of limit."""
    if not text or len(text) <= max_chars:
        return text
    search_start = max(0, max_chars - 200)
    window = text[search_start : max_chars + 1]
    last_nl = window.rfind("\n")
    last_dot = window.rfind(". ")
    last_ex = window.rfind("! ")
    last_q = window.rfind("? ")
    last_sp = window.rfind(" ")
    cut = max(last_nl, last_dot, last_ex, last_q, last_sp)
    if cut >= 0:
        return text[: search_start + cut].rstrip()
    return text[:max_chars].rstrip()
