import easyocr

_reader = None

def _get_reader() -> easyocr.Reader:
    global _reader
    if _reader is None:
        _reader = easyocr.Reader(
            ['ko', 'en'],
            model_storage_directory=r'C:\Users\pyk71\.EasyOCR\model'
        )
    return _reader

def run_ocr(image_source) -> list[dict]:
    reader = _get_reader()
    results = reader.readtext(image_source)

    items = []
    for (box, text, confidence) in results:
        x1 = int(min(p[0] for p in box))
        y1 = int(min(p[1] for p in box))
        x2 = int(max(p[0] for p in box))
        y2 = int(max(p[1] for p in box))
        items.append({
            "text": text,
            "box": [x1, y1, x2, y2],
            "confidence": round(confidence, 3)
        })
    return items