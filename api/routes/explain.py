from fastapi import APIRouter
from pydantic import BaseModel
from api.services import gpt, youtube
from api.services.language import detect_language

router = APIRouter(prefix="/explain", tags=["explain"])


class ExplainRequest(BaseModel):
    phrase: str
    profile: dict | None = None
    lang: str = "en"


@router.post("/word")
async def explain_word(req: ExplainRequest):
    lang = req.lang if req.lang in ("ru", "en") else detect_language(req.phrase)

    explanation = await gpt.explain_word(req.phrase, profile=req.profile, lang=lang)

    # Для YouGlish используем английский эквивалент если есть
    youglish_phrase = explanation.get("english") or req.phrase
    youglish_url = youtube.get_youglish_url(youglish_phrase)

    return {
        "phrase": req.phrase,
        "lang": lang,
        **explanation,
        "youglish_url": youglish_url,
    }
