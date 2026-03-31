"""FastAPI application для Mini App API.

Объединяет API routes и voice engine в единое приложение.
Запуск: python -m bot.api.app (порт 8001)
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from bot.api.routes import router as api_router
from bot.call_engine.orchestrator import app as voice_app

# ── Main API app ──

app = FastAPI(title="PersonalAI Sergiy API", version="1.0.0")

# CORS for Mini App
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://web.telegram.org",
        "http://localhost:5173",  # Vite dev server
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(api_router)

# Mount voice engine WebSocket
app.mount("/voice", voice_app)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "personalai-api"}


def start_server(host: str = "0.0.0.0", port: int = 8001) -> None:
    """Start the API server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    start_server()
