import base64
from fastapi import APIRouter, UploadFile, File, Form
from api.services import whisper, gpt, tts
from api.services.language import detect_language

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post("/process")
async def process_voice(
    audio: UploadFile = File(...),
    level: str = Form(""),
    profession: str = Form(""),
    interests: str = Form(""),
    goal: str = Form(""),
    interface_lang: str = Form("ru"),
):
    audio_bytes = await audio.read()

    # 1. Whisper → текст
    user_text = await whisper.transcribe(audio_bytes, filename=audio.filename or "audio.ogg")

    # 2. Определяем язык речи
    lang = detect_language(user_text)

    # 3. Профиль
    profile = None
    if profession or interests or goal:
        profile = {
            "onboarded": 1,
            "level": level,
            "profession": profession,
            "interests": [i.strip() for i in interests.split(",") if i.strip()],
            "goal": goal,
            "interface_lang": interface_lang,
        }

    # 4. GPT → ответ + коррекция (с учётом языка интерфейса)
    gpt_result = await gpt.process_voice_input(
        user_text,
        profile=profile,
        lang=interface_lang,  # исправления на языке интерфейса
    )

    # 5. TTS — озвучиваем исправленную фразу если есть ошибка
    has_mistake = (
        gpt_result.get("improved")
        and gpt_result["improved"] != "-"
        and gpt_result.get("correction") not in ("No mistakes!", "Ошибок нет!", "")
    )
    text_to_speak = gpt_result["improved"] if has_mistake else user_text
    audio_response = await tts.synthesize(text_to_speak)

    return {
        "user_text": user_text,
        "lang": lang,
        "reply": gpt_result["reply"],
        "correction": gpt_result["correction"],
        "improved": gpt_result["improved"],
        "audio_base64": base64.b64encode(audio_response).decode(),
    }
