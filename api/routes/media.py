from fastapi import APIRouter
from pydantic import BaseModel
from api.services import subtitles as svc, gpt

router = APIRouter(prefix="/media", tags=["media"])


class VideoRequest(BaseModel):
    url: str
    profile: dict | None = None
    interface_lang: str = "ru"


class QuizRequest(BaseModel):
    word: str
    example: str
    interface_lang: str = "ru"


@router.post("/analyze")
async def analyze_video(req: VideoRequest):
    """
    Полный пайплайн:
    1. Скачать субтитры
    2. GPT анализ — саммари + слова
    """
    data = await svc.get_subtitles(req.url)
    analysis = await gpt.analyze_subtitles(
        title=data["title"],
        text=data["text"],
        profile=req.profile,
        interface_lang=req.interface_lang,
    )
    return {
        "video_id":   data["video_id"],
        "title":      data["title"],
        "from_cache": data.get("from_cache", False),
        "summary":    analysis["summary"],
        "words":      analysis["words"],
    }


@router.post("/quiz")
async def quiz_question(req: QuizRequest):
    """Генерирует вопрос викторины для одного слова."""
    question = await gpt.generate_quiz_question(
        word=req.word,
        example=req.example,
        interface_lang=req.interface_lang,
    )
    return question
