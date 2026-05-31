from fastapi import APIRouter, File, Form, UploadFile
from PIL import Image
import numpy as np
import io

from .engine import run_ocr
from .matcher import classify_ocr_results
from .db import init_db, save_screen, query_text, get_screens

router = APIRouter(prefix="/ocr", tags=["ocr"])
init_db()


@router.post("/learn")
async def learn_screen(
    file: UploadFile = File(...),
    screen_name: str = Form(...),
):
    image_data = await file.read()
    img = Image.open(io.BytesIO(image_data)).convert("RGB")
    image_array = np.array(img)

    ocr_items = run_ocr(image_array)
    classified = classify_ocr_results(ocr_items)
    save_screen(screen_name, classified)

    return {"status": "ok", "screen": screen_name, "count": len(classified)}


@router.get("/query")
async def query_screen(text: str):
    results = query_text(text)
    return {"results": results}


@router.get("/screens")
async def list_screens():
    return {"screens": get_screens()}
