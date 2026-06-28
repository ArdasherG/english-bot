import base64
import logging
import httpx
from aiogram import Router, F
from aiogram.types import Message, BufferedInputFile
from api.services.database import get_user
from config.settings import settings

router = Router()
logger = logging.getLogger(__name__)


async def _get_lang(user_id: int) -> str:
    profile = await get_user(user_id)
    return profile.get("interface_lang", "ru") if profile else "ru"


@router.message(F.voice)
async def handle_voice(message: Message):
    user_id = message.from_user.id
    lang = await _get_lang(user_id)

    await message.bot.send_chat_action(message.chat.id, "typing")

    try:
        profile = await get_user(user_id)
        interface_lang = profile.get("interface_lang", "ru") if profile else "ru"

        file = await message.bot.get_file(message.voice.file_id)
        file_url = f"https://api.telegram.org/file/bot{settings.TELEGRAM_BOT_TOKEN}/{file.file_path}"

        async with httpx.AsyncClient(timeout=120) as client:
            audio_resp = await client.get(file_url)
            audio_resp.raise_for_status()
            audio_bytes = audio_resp.content

            response = await client.post(
                f"{settings.BACKEND_URL}/voice/process",
                files={"audio": ("audio.ogg", audio_bytes, "audio/ogg")},
                data={
                    "level":          profile.get("level", "") if profile else "",
                    "profession":     profile.get("profession", "") if profile else "",
                    "interests":      ",".join(profile.get("interests") or []) if profile else "",
                    "goal":           profile.get("goal", "") if profile else "",
                    "interface_lang": interface_lang,
                },
            )
            response.raise_for_status()
            data = response.json()

    except httpx.TimeoutException:
        err = "⏱ Обработка заняла слишком долго. Попробуй короткое сообщение." if lang == "ru" \
              else "⏱ Processing took too long. Try a shorter message."
        await message.answer(err)
        return
    except httpx.HTTPStatusError as e:
        logger.error(f"Backend HTTP error for user {user_id}: {e}")
        err = "⚠️ Сервер временно недоступен. Попробуй через минуту." if lang == "ru" \
              else "⚠️ Server temporarily unavailable. Try again in a minute."
        await message.answer(err)
        return
    except Exception as e:
        logger.error(f"Voice handler error for user {user_id}: {e}", exc_info=True)
        err = "⚠️ Что-то пошло не так. Попробуй ещё раз." if lang == "ru" \
              else "⚠️ Something went wrong. Please try again."
        await message.answer(err)
        return

    detected_lang = data.get("lang", "en")

    if detected_lang == "ru":
        await message.answer(
            f"🗣 *Ты сказал:* _{data['user_text']}_\n\n"
            "💡 Голосовые — для практики *английской* речи.\n"
            "Попробуй сказать это по-английски! 🎤",
            parse_mode="Markdown",
        )
        return

    # Формируем текстовый ответ на языке интерфейса
    if interface_lang == "ru":
        text = f"🗣 *Ты сказал:* {data['user_text']}\n\n"
        text += f"💬 *Ответ:* {data['reply']}\n\n"
        if data.get("correction") and data["correction"] not in ("No mistakes!", "Ошибок нет!"):
            text += f"✏️ *Исправление:* {data['correction']}\n"
            if data.get("improved") and data["improved"] != "-":
                text += f"✅ *Правильно:* `{data['improved']}`\n"
        else:
            text += "✅ *Ошибок нет!*\n"
        caption = "🔊 Послушай правильный вариант"
    else:
        text = f"🗣 *You said:* {data['user_text']}\n\n"
        text += f"💬 *Reply:* {data['reply']}\n\n"
        if data.get("correction") and data["correction"] != "No mistakes!":
            text += f"✏️ *Correction:* {data['correction']}\n"
            if data.get("improved") and data["improved"] != "-":
                text += f"✅ *Improved:* `{data['improved']}`\n"
        else:
            text += "✅ *No mistakes!*\n"
        caption = "🔊 Listen to the correct version"

    await message.answer(text, parse_mode="Markdown")

    if data.get("audio_base64"):
        try:
            audio_out = base64.b64decode(data["audio_base64"])
            await message.answer_voice(
                BufferedInputFile(audio_out, filename="reply.mp3"),
                caption=caption,
            )
        except Exception as e:
            logger.error(f"TTS send error for user {user_id}: {e}")
