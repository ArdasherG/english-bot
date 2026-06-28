def get_youglish_url(phrase: str) -> str:
    """Формирует ссылку на YouGlish с точными моментами произношения."""
    query = phrase.replace(" ", "+")
    return f"https://youglish.com/pronounce/{query}/english"
