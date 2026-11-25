"""Standalone local/private service. Bind locally unless deployed behind authentication."""
import asyncio
import secrets
from contextlib import asynccontextmanager
from io import BytesIO

import numpy as np
from fastapi import FastAPI, HTTPException, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from PIL import Image, UnidentifiedImageError

from .recognizer import FooterOCR, Recognizer
from .scryfall import prices
from .config import setting


@asynccontextmanager
async def lifespan(app):
    ocr = FooterOCR() if setting("OCR") == "1" else None
    app.state.recognizer = Recognizer(setting("DATA", "data"), ocr=ocr)
    app.state.semaphore = asyncio.Semaphore(1)
    yield


app = FastAPI(title="Magicou Recognizer", version="0.3.0", lifespan=lifespan)


@app.middleware("http")
async def authenticate(request: Request, call_next):
    from starlette.responses import JSONResponse
    key = setting("API_KEY")
    if key and not secrets.compare_digest(request.headers.get("Authorization", ""), "Bearer " + key):
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    return await call_next(request)


@app.get("/health")
def health(request: Request):
    return {"ready": True, "game": "magic", **request.app.state.recognizer.coverage()}


def decode(data):
    try:
        with Image.open(BytesIO(data)) as source:
            if source.format not in {"JPEG", "PNG", "WEBP"} or source.width * source.height > 20_000_000:
                raise ValueError("Unsupported image or too many pixels")
            from PIL import ImageOps
            return np.asarray(ImageOps.exif_transpose(source).convert("RGB"))
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise ValueError("Invalid image") from error


@app.post("/identify")
async def identify(request: Request, file: UploadFile, guided: bool = False, cropped: bool = False):
    data = await file.read(3_000_001)
    if len(data) > 3_000_000:
        raise HTTPException(413, "Image exceeds 3 MB")
    semaphore = request.app.state.semaphore
    try:
        await asyncio.wait_for(semaphore.acquire(), timeout=.01)
    except TimeoutError as error:
        raise HTTPException(503, "Recognizer busy", headers={"Retry-After": "1"}) from error
    try:
        image = await run_in_threadpool(decode, data)
        return await run_in_threadpool(request.app.state.recognizer.identify, image,
                                      guided=guided, cropped=cropped)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    finally:
        semaphore.release()


@app.get("/cards/{card_id}/price")
async def quote(card_id: str, finish: str = Query("nonfoil", pattern="^(nonfoil|foil|etched)$")):
    try:
        return await run_in_threadpool(prices, card_id, finish)
    except ValueError as error:
        raise HTTPException(400, "Invalid Scryfall card ID") from error
    except Exception as error:
        import httpx
        if isinstance(error, httpx.HTTPStatusError) and error.response.status_code == 404:
            raise HTTPException(404, "Printing not found") from error
        if isinstance(error, (httpx.HTTPError, RuntimeError)):
            raise HTTPException(502, "Scryfall unavailable; retry later") from error
        raise
