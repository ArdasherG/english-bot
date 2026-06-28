from fastapi import FastAPI
from api.routes import voice, explain, media

app = FastAPI(
    title="AI English Bot API",
    description="Backend for Telegram English tutor bot",
    version="0.1.0",
)

app.include_router(voice.router)
app.include_router(explain.router)
app.include_router(media.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
