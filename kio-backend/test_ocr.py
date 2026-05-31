from PIL import Image, ImageDraw, ImageFont
import numpy as np
from app.ocr.engine import run_ocr
from app.ocr.matcher import classify_ocr_results

img = Image.open(r"C:\Users\pyk71\KIO\kio-backend\test_menu.png")
img = img.convert("RGB")
w, h = img.size
img = img.resize((w * 2, h * 2), Image.LANCZOS)

image_array = np.array(img)
results = run_ocr(image_array)
print(f"인식된 텍스트: {len(results)}개\n")
for item in results:
    print(f"{item['text']:<20} 신뢰도: {item['confidence']}")

classified = classify_ocr_results(results)
print("\n=== 매칭 결과 ===")
for item in classified:
    print(f"텍스트: {item['text']:<20} 라벨: {item['label']:<15} {item.get('matched_name', '')}")

try:
    font = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 20)
except:
    font = ImageFont.load_default()

draw = ImageDraw.Draw(img)
for item in classified:
    x1, y1, x2, y2 = item['box']
    draw.rectangle([x1, y1, x2, y2], outline='red', width=2)
    display_text = item.get('matched_name') or item['text']
    draw.text((x1, y1 - 22), display_text, fill='red', font=font)

img.save(r"C:\Users\pyk71\KIO\kio-backend\test_result.png")
print("\n결과 이미지 저장")