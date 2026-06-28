from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI, HTTPException, Request

from jimini.buffer.worker import worker_loop
from jimini.config import settings
from jimini.hostigamiento.worker import worker_loop_hostigamiento
from jimini.webhook.handler import handle_webhook

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Jimini")

_background_tasks = set()


@app.on_event("startup")
async def startup():
    task1 = asyncio.create_task(worker_loop())
    _background_tasks.add(task1)
    task1.add_done_callback(_background_tasks.discard)
    logger.info("Buffer worker loop started")

    task2 = asyncio.create_task(worker_loop_hostigamiento())
    _background_tasks.add(task2)
    task2.add_done_callback(_background_tasks.discard)
    logger.info("Hostigamiento worker loop started")


@app.post("/api/v1/tg/webhook")
async def tg_webhook(request: Request):
    if settings.webhook_secret_token:
        token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if token != settings.webhook_secret_token:
            raise HTTPException(status_code=401, detail="Invalid secret token")

    update = await request.json()
    result = await handle_webhook(update)

    if result.get("ok", False):
        return {"status": "ok"}

    status_code = result.get("status_code", 500)
    raise HTTPException(status_code=status_code, detail=result.get("detail", "error"))
