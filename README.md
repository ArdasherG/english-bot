# AI English Telegram Bot — MVP

AI-powered English tutor inside Telegram.

## Features
- 🎤 **Voice conversation** — speak, get a reply + grammar corrections
- 📖 **Word explanation** — ask what any word/phrase means
- 🎬 **Media examples** — YouTube clips showing real usage

## Stack
- **Bot**: Python + aiogram 3
- **Backend**: FastAPI
- **STT**: OpenAI Whisper
- **AI**: GPT-4.1
- **TTS**: ElevenLabs
- **Media**: YouTube Data API v3

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Fill in your API keys in .env
```

### 3. Run backend
```bash
uvicorn api.main:app --reload --port 8000
```

### 4. Run bot (separate terminal)
```bash
python -m bot.main
```

## API Keys needed
| Service | Where to get |
|---|---|
| Telegram Bot Token | @BotFather |
| OpenAI API Key | platform.openai.com |
| ElevenLabs API Key | elevenlabs.io |
| YouTube Data API v3 | console.cloud.google.com |

## Project Structure
```
english-bot/
├── bot/               # Telegram bot (aiogram)
│   └── handlers/      # voice.py, word.py
├── api/               # FastAPI backend
│   ├── routes/        # voice.py, explain.py
│   └── services/      # whisper, gpt, tts, youtube
├── config/            # Settings (pydantic)
└── requirements.txt
```
