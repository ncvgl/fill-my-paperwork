from typing import List, Dict, Any
import io
from PIL import Image, ImageDraw, ImageFont


def ensure_dir(path: str) -> None:
    import os
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def render_pdf_first_page_to_png_bytes(pdf_path: str) -> bytes:
    try:
        import fitz  # PyMuPDF
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("PyMuPDF (fitz) is required to render PDFs in tests") from exc
    doc = fitz.open(pdf_path)
    page = doc.load_page(0)
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
    data = pix.tobytes('png')
    doc.close()
    return data


def draw_boxes_and_text(img: Image.Image, boxes: List[Dict[str, Any]], texts: List[str]) -> Image.Image:
    out = img.convert('RGBA')
    draw = ImageDraw.Draw(out)
    width_px, height_px = out.size
    # Font setup
    try:
        font = ImageFont.truetype("Arial.ttf", 20)
    except Exception:
        font = ImageFont.load_default()
    for i, entry in enumerate(boxes):
        box = entry.get('box_2d') if isinstance(entry, dict) else entry
        if not isinstance(box, list) or len(box) != 4:
            continue
        y_min, x_min, y_max, x_max = box
        x0 = int(x_min / 1000 * width_px)
        y0 = int(y_min / 1000 * height_px)
        x1 = int(x_max / 1000 * width_px)
        y1 = int(y_max / 1000 * height_px)
        draw.rectangle([(x0, y0), (x1, y1)], outline=(0, 128, 255, 255), width=2)
        text = texts[i] if i < len(texts) else ''
        draw.text((x0 + 4, y0 + 2), text, fill=(0, 0, 0, 255), font=font)
    return out
