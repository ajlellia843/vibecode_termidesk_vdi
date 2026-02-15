"""Tests for RAG context trimming utilities."""
from orchestrator.service.context_utils import (
    extract_relevant_section,
    normalize_and_dedup,
    trim_to_limit,
)

FAQ_TEXT = """\
# Termidesk VDI — Частые вопросы

## Что такое Termidesk?

Termidesk — это решение виртуальных рабочих столов (VDI), позволяющее предоставлять пользователям удалённый доступ к рабочим столам и приложениям.

## Как подключиться к Termidesk?

1. Установите клиент Termidesk с официального сайта или из корпоративного репозитория.
2. Запустите клиент и введите адрес сервера (например, termidesk.company.local).
3. Введите учётные данные (логин и пароль домена).
4. Выберите доступный рабочий стол или приложение.

## Ошибка «Не удалось подключиться к серверу»

- Проверьте сетевое подключение и доступность сервера (ping, порты).
- Убедитесь, что адрес сервера введён верно (без лишних пробелов, правильный протокол).
"""


def test_extract_relevant_section() -> None:
    """Section extraction should return only the matching section for 'Что такое Termidesk VDI?'"""
    result = extract_relevant_section(FAQ_TEXT, "Что такое Termidesk VDI?")
    assert "решение виртуальных рабочих столов" in result
    assert "Установите клиент" not in result
    assert "Как подключиться" not in result
    assert "Не удалось подключиться" not in result


def test_extract_relevant_section_no_match_returns_full() -> None:
    """If no section header matches, return the full text."""
    result = extract_relevant_section(FAQ_TEXT, "Как настроить GPU passthrough?")
    assert "Частые вопросы" in result
    assert "Как подключиться" in result


def test_extract_relevant_section_no_headers() -> None:
    """Plain text without headers is returned as-is."""
    plain = "Просто текст без заголовков. Ещё одно предложение."
    assert extract_relevant_section(plain, "что-то") == plain


def test_context_max_chars_and_no_mid_word_cut() -> None:
    """trim_to_limit respects the limit and does not cut mid-word."""
    # Build a 5000-char text made of sentences
    sentence = "Это длинное предложение для тестирования обрезки контекста. "
    text = sentence * (5000 // len(sentence) + 1)
    assert len(text) > 5000

    result = trim_to_limit(text, 2500)
    assert len(result) <= 2500
    # Should not end with a partial word (last non-space char should be punctuation or letter)
    stripped = result.rstrip()
    assert stripped, "Result should not be empty"
    # Should end at a sentence boundary (period)
    assert stripped[-1] == ".", f"Expected sentence-end cut, got: ...{stripped[-30:]}"


def test_trim_to_limit_short_text_unchanged() -> None:
    """Text shorter than limit is returned unchanged."""
    short = "Короткий текст."
    assert trim_to_limit(short, 2500) == short


def test_dedup_lines_and_join_fragments() -> None:
    """Consecutive duplicates removed; lowercase-start fragments joined with previous line."""
    text = (
        "Убедитесь, что адрес сервера введён верно (без лишних пробелов, правиль\n"
        "ный протокол).\n"
        "- Проверьте сетевое подключение.\n"
        "- Проверьте сетевое подключение.\n"
        "- Другой пункт."
    )
    result = normalize_and_dedup(text)
    # Fragment "ный протокол)." should be joined with previous line
    assert "правильный протокол)." in result
    # Duplicate line should be removed
    lines = result.split("\n")
    deduped = [l for l in lines if "Проверьте сетевое" in l]
    assert len(deduped) == 1, f"Expected 1 occurrence, got {len(deduped)}: {deduped}"
    # Other content preserved
    assert "Другой пункт" in result


def test_dedup_preserves_blank_lines() -> None:
    """Blank lines for paragraph separation should be preserved (not treated as duplicates)."""
    text = "Первый абзац.\n\nВторой абзац.\n\nТретий абзац."
    result = normalize_and_dedup(text)
    # Structure should be preserved
    assert "Первый абзац." in result
    assert "Третий абзац." in result
