# AI English Tutor Bot — Документация проекта

## Обзор

Telegram-бот для изучения английского языка с AI-поддержкой. Полностью бесплатный стек, без платных API (кроме опционального).

**Ключевые возможности:**
- 🎤 Голосовая практика с исправлением ошибок
- 📖 Объяснение слов и фраз (EN/RU)
- 💬 Свободный диалог с носителем
- 📹 Изучение слов из YouTube видео + викторина
- 👤 Персональный профиль — адаптация под пользователя

---

## Архитектура

```
Telegram
    ↓
aiogram 3 (Bot)
    ↓
FastAPI (Backend)
    ↓
┌─────────────────────────────────────┐
│  Whisper local  — Speech to Text    │
│  Groq / Llama 3.3 — AI логика      │
│  Edge TTS       — Text to Speech   │
│  yt-dlp         — YouTube субтитры │
│  SQLite         — База данных       │
└─────────────────────────────────────┘
```

Бот и бэкенд запускаются как два отдельных процесса. Бот общается с бэкендом через HTTP (httpx).

---

## Технологический стек

### Bot Layer
| Компонент | Технология | Версия | Описание |
|-----------|-----------|--------|----------|
| Telegram Bot | aiogram | 3.7.0 | Асинхронный фреймворк для Telegram |
| FSM Storage | aiogram-sqlite-storage | 0.4.0 | Хранение состояний FSM в SQLite |

### Backend Layer
| Компонент | Технология | Версия | Описание |
|-----------|-----------|--------|----------|
| Web Framework | FastAPI | 0.111.0 | Async REST API |
| Server | uvicorn | 0.30.1 | ASGI сервер |
| HTTP Client | httpx | 0.27.0 | Async HTTP клиент |

### AI / ML
| Компонент | Технология | Описание | Стоимость |
|-----------|-----------|----------|-----------|
| Speech-to-Text | openai-whisper (local) | Локальная модель `base` | Бесплатно |
| Language Model | Groq API / Llama 3.3 70B | Ответы, коррекция, анализ | Бесплатно (14,400 req/day) |
| Text-to-Speech | Edge TTS (Microsoft) | Синтез речи без API ключа | Бесплатно |

### Data
| Компонент | Технология | Описание |
|-----------|-----------|----------|
| База данных | SQLite + aiosqlite | Профили, история, кэш субтитров |
| YouTube субтитры | yt-dlp | Скачивание субтитров без API |

### Системные зависимости
- **Python** 3.10+
- **ffmpeg** — обработка аудио для Whisper

---

## Структура проекта

```
english-bot/
├── bot/                          # Telegram бот (aiogram)
│   ├── main.py                   # Точка входа, регистрация роутеров
│   └── handlers/
│       ├── onboarding.py         # FSM онбординг (5 шагов)
│       ├── voice.py              # Голосовые сообщения
│       ├── word.py               # Объяснение слов (EN + RU паттерны)
│       ├── chat.py               # Свободный диалог /chat
│       ├── video.py              # YouTube субтитры + викторина
│       └── edit_profile.py       # Редактирование профиля (inline кнопки)
│
├── api/                          # FastAPI бэкенд
│   ├── main.py                   # FastAPI app, роутеры
│   ├── routes/
│   │   ├── voice.py              # POST /voice/process
│   │   ├── explain.py            # POST /explain/word
│   │   └── media.py              # POST /media/analyze, POST /media/quiz
│   └── services/
│       ├── whisper.py            # Локальная транскрипция
│       ├── gpt.py                # Все промпты и парсеры
│       ├── tts.py                # Edge TTS синтез
│       ├── database.py           # SQLite CRUD операции
│       ├── subtitles.py          # yt-dlp + кэширование
│       ├── youtube.py            # YouGlish ссылки
│       └── language.py           # Определение языка (EN/RU)
│
├── config/
│   └── settings.py               # Pydantic Settings (из .env)
│
├── data/                         # Создаётся автоматически
│   ├── users.db                  # SQLite база данных
│   └── fsm_storage.db            # FSM состояния
│
├── .env                          # API ключи (не в git)
├── .env.example                  # Шаблон переменных
├── requirements.txt
└── DOCUMENTATION.md
```

---

## База данных

### Таблица `users`
```sql
CREATE TABLE users (
    user_id        INTEGER PRIMARY KEY,  -- Telegram user ID
    username       TEXT,
    name           TEXT,
    level          TEXT,       -- beginner / intermediate / advanced
    profession     TEXT,       -- профессия пользователя
    interests      TEXT,       -- JSON массив интересов
    goal           TEXT,       -- цель изучения
    interface_lang TEXT DEFAULT 'ru',  -- ru / en
    onboarded      INTEGER DEFAULT 0,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Таблица `chat_history`
```sql
CREATE TABLE chat_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER,
    role       TEXT,    -- user / assistant
    content    TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```
Автоматически очищается при старте бота (записи старше 30 дней удаляются).

### Таблица `subtitles_cache`
```sql
CREATE TABLE subtitles_cache (
    video_id   TEXT PRIMARY KEY,
    title      TEXT,
    subtitles  TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```
Кэш субтитров YouTube — одно видео скачивается только один раз.

---

## API эндпоинты

### POST `/voice/process`
Полный голосовой pipeline.

**Входные данные:** `multipart/form-data`
- `audio` — аудио файл (.ogg)
- `level`, `profession`, `interests`, `goal` — данные профиля

**Ответ:**
```json
{
  "user_text": "I go to store yesterday",
  "lang": "en",
  "reply": "Oh nice! What did you buy?",
  "correction": "go → went, missing 'the'",
  "improved": "I went to the store yesterday",
  "audio_base64": "<base64 mp3>"
}
```

### POST `/explain/word`
Объяснение слова или фразы.

**Входные данные:**
```json
{
  "phrase": "I'm broke",
  "profile": {...},
  "lang": "ru"
}
```

**Ответ:**
```json
{
  "phrase": "I'm broke",
  "english": "I'm broke",
  "meaning": "I'm broke — не иметь денег совсем",
  "tone": "разговорный / неформальный",
  "examples": [
    "I can't go out tonight, I'm broke. (Я не могу выйти, у меня нет денег.)"
  ],
  "youglish_url": "https://youglish.com/pronounce/I'm+broke/english"
}
```

### POST `/media/analyze`
Анализ YouTube видео.

**Входные данные:**
```json
{
  "url": "https://youtube.com/watch?v=...",
  "profile": {...},
  "interface_lang": "ru"
}
```

**Ответ:**
```json
{
  "video_id": "dQw4w9WgXcQ",
  "title": "How to negotiate a salary",
  "from_cache": false,
  "summary": "В этом видео карьерный коуч объясняет...",
  "words": [
    {
      "word": "negotiate",
      "example": "You should negotiate your salary before accepting.",
      "hint": "торговаться, вести переговоры"
    }
  ]
}
```

### POST `/media/quiz`
Генерация вопроса викторины.

**Входные данные:**
```json
{
  "word": "negotiate",
  "example": "You should negotiate your salary.",
  "interface_lang": "ru"
}
```

---

## Ключевые решения и почему

### Почему локальный Whisper, а не OpenAI API?
Бесплатно. OpenAI Whisper API стоит $0.006/мин. Локальная модель `base` достаточно точна для учебных целей и работает без интернета.

**Компромисс:** модель `base` занимает ~150MB RAM и ~1-2 сек на транскрипцию. Модель `small` точнее но медленнее.

### Почему Groq вместо OpenAI GPT?
Groq даёт 14,400 бесплатных запросов в день против платного GPT-4. Llama 3.3 70B на Groq по качеству сопоставим с GPT-3.5-turbo для учебных задач.

**Лимиты Groq (free tier):**
- 14,400 запросов / день
- 6,000 токенов / минута
- При превышении — ошибка `429`, бот сообщает пользователю

### Почему Edge TTS вместо ElevenLabs?
Полностью бесплатно, не требует API ключа, качество достаточное для учебного бота.

**Компромисс:** Edge TTS требует интернет соединение для синтеза.

### Почему SQLite вместо PostgreSQL?
Для MVP с небольшим числом пользователей SQLite проще в деплое — не нужен отдельный сервер БД. При росте до 1000+ активных пользователей стоит мигрировать на PostgreSQL.

### Почему два процесса (бот + бэкенд)?
Разделение позволяет перезапускать бэкенд без потери Telegram соединения и масштабировать независимо. Whisper и yt-dlp — тяжёлые операции, им место на бэкенде.

---

## Переменные окружения (.env)

```env
# Telegram
TELEGRAM_BOT_TOKEN=         # @BotFather → /newbot

# Groq API (бесплатно: console.groq.com)
GROQ_API_KEY=               # Формат: gsk_...
GROQ_MODEL=llama-3.3-70b-versatile

# Whisper
WHISPER_MODEL_SIZE=base     # tiny / base / small / medium / large

# Edge TTS
EDGE_TTS_VOICE=en-US-JennyNeural

# Backend
BACKEND_URL=http://localhost:8000
```

**Нужно получить только 2 ключа:**
- `TELEGRAM_BOT_TOKEN` → @BotFather в Telegram
- `GROQ_API_KEY` → console.groq.com (бесплатная регистрация)

---

## Запуск локально

### 1. Установка зависимостей
```bash
# Клонируй проект
cd english-bot

# Создай виртуальное окружение
python -m venv .venv

# Активируй
source .venv/bin/activate      # macOS / Linux
.venv\Scripts\activate         # Windows

# Установи зависимости
pip install -r requirements.txt
```

### 2. Системные зависимости
```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg

# Windows
# Скачай с https://ffmpeg.org/download.html
# Добавь в PATH
```

### 3. Настройка
```bash
cp .env.example .env
# Открой .env и заполни TELEGRAM_BOT_TOKEN и GROQ_API_KEY
```

### 4. Запуск
```bash
# Терминал 1 — бэкенд
uvicorn api.main:app --reload --port 8000

# Терминал 2 — бот
python -m bot.main
```

### 5. Проверка
```
GET http://localhost:8000/health  → {"status": "ok"}
GET http://localhost:8000/docs    → Swagger UI
```

---

## Онбординг пользователя

При первом `/start` бот задаёт 5 вопросов через FSM:

```
1. Уровень английского
   [🌱 Beginner] [📚 Intermediate] [🚀 Advanced]

2. Профессия / специальность
   → свободный текст

3. Интересы (через запятую)
   → свободный текст

4. Цель изучения
   → свободный текст

5. Язык интерфейса
   [🇷🇺 На русском] [🇬🇧 In English]
```

Данные сохраняются в `users.db` и передаются в каждый запрос к GPT для персонализации примеров.

---

## Пользовательские сценарии

### Голосовая практика
```
Пользователь → голосовое сообщение на английском
Бот → транскрипция (Whisper)
    → анализ ошибок (Groq)
    → текстовый ответ + исправление
    → голосовой ответ (Edge TTS)
```

### Объяснение слова
```
Пользователь → "что значит 'deadline'?" / "what does 'deadline' mean?"
Бот → определяет язык вопроса
    → GPT объясняет (на языке вопроса)
    → примеры на английском + перевод
    → ссылка YouGlish с реальным произношением
```

### YouTube видео
```
Пользователь → ссылка на YouTube
Бот → yt-dlp скачивает субтитры
    → GPT: саммари + 5-7 слов для изучения
    → inline кнопки для каждого слова
    → тап → объяснение в контексте видео
    → викторина fill-in-the-blank
```

### Свободный диалог
```
Пользователь → /chat
Бот → активирует режим диалога
    → отвечает как native speaker
    → при ошибках — мягкое исправление отдельной строкой
    → история последних 10 сообщений передаётся в GPT
    → /stop или 15 мин тишины → выход
```

---

## Известные ограничения

| Ограничение | Причина | Решение при росте |
|-------------|---------|-------------------|
| Groq 14,400 req/day | Бесплатный tier | Платный план или OpenAI |
| Whisper `base` — только английский | Параметр `language="en"` | Убрать параметр для мультиязычности |
| SQLite — не для высокой нагрузки | Простота деплоя | Миграция на PostgreSQL |
| Edge TTS — требует интернет | Microsoft облако | Kokoro TTS локально |
| yt-dlp — YouTube может блокировать | Политика YouTube | Обновлять yt-dlp регулярно |

---

## Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Запуск онбординга |
| `/menu` | Главное меню |
| `/chat` | Свободный диалог |
| `/stop` | Выход из диалога |
| `/profile` | Просмотр профиля |
| `/edit` | Редактирование профиля |

---

*Документация актуальна для версии v14 проекта.*
