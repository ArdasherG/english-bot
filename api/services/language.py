"""
Определение языка сообщения пользователя.
Используем простую эвристику по символам — без внешних библиотек.
"""

CYRILLIC = set("абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ")


def detect_language(text: str) -> str:
    """
    Возвращает 'ru' если текст преимущественно на русском, иначе 'en'.
    """
    if not text:
        return "en"

    cyrillic_count = sum(1 for ch in text if ch in CYRILLIC)
    ratio = cyrillic_count / len(text.replace(" ", "") or "1")

    return "ru" if ratio > 0.2 else "en"
