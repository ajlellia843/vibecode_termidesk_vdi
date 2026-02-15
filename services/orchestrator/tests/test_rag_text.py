"""Tests for RAG text utilities: section extraction, normalization."""
from orchestrator.service.rag_text import best_section, normalize_text

TROUBLESHOOTING_MD = """# Termidesk VDI — Устранение неполадок

## Диагностика проблем с подключением

1. **Проверка сети**: убедитесь, что компьютер имеет доступ в сеть и что сервер Termidesk доступен (ping, проверка портов).
2. **Версия клиента**: используйте актуальную версию клиента Termidesk, совместимую с версией сервера.
3. **Учётные данные**: проверьте правильность логина и пароля; при смене пароля в домене может потребоваться повторный вход.

## Сессия обрывается или «зависает»

- Проверьте стабильность сети и загрузку каналов.
- Убедитесь, что на стороне клиента и сервера не применяются агрессивные таймауты или ограничения сессий.
- Соберите логи клиента и сервера за момент обрыва и передайте в техническую поддержку.

## Чёрный экран после входа

- Обновите видеодрайверы на клиентском устройстве.
- Проверьте, что разрешение и настройки дисплея поддерживаются сервером.
- При необходимости перезапустите клиент и попробуйте подключиться снова. Если проблема сохраняется — соберите логи и обратитесь в поддержку.

## Рекомендации при обращении в поддержку

- Опишите шаги, которые привели к проблеме.
- Укажите версию клиента и ОС.
- Приложите логи за период возникновения ошибки (клиент и, по возможности, сервер).
- Укажите, воспроизводится ли проблема стабильно или случайным образом.
"""


def test_best_section_black_screen() -> None:
    """Query 'Черный экран' should return only the 'Чёрный экран после входа' section."""
    result = best_section(TROUBLESHOOTING_MD, "Черный экран")
    assert "Чёрный экран после входа" in result
    assert "видеодрайверы" in result
    assert "Диагностика проблем с подключением" not in result
    assert "Рекомендации при обращении" not in result


def test_best_section_hangs() -> None:
    """Query 'Виснет клиент' should select section 'Сессия обрывается или «зависает»'."""
    result = best_section(TROUBLESHOOTING_MD, "Виснет клиент")
    assert "зависает" in result or "обрывается" in result
    assert "Чёрный экран после входа" not in result
    assert "стабильность сети" in result or "каналов" in result


def test_normalize_text_joins_fragments_and_dedups() -> None:
    """Consecutive duplicates removed; fragment joined to previous line when prev has no terminal punct."""
    text = (
        "Убедитесь, что на стороне клиента и сервера не применя\n"
        "ются агрессивные таймауты или ограничения сессий.\n"
        "- Соберите логи."
    )
    result = normalize_text(text)
    assert "не применяются агрессивные" in result
    assert "- Соберите логи." in result
    dup_text = "Строка один.\nСтрока один.\nСтрока два."
    dup_result = normalize_text(dup_text)
    assert dup_result.count("Строка один.") == 1
    assert "Строка два." in dup_result
