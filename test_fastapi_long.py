import io
import os
from PIL import Image
from fastapi.testclient import TestClient
from constants import MODEL_NAME
from utils_for_tests import ensure_dir, draw_boxes_and_text
from fastapi_server import app

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _process_document(client: TestClient, doc_path: str, out_dir: str) -> None:
    with open(doc_path, 'rb') as f:
        upload_bytes = f.read()
    img = Image.open(io.BytesIO(upload_bytes)).convert('RGB')
    upload_name = os.path.basename(doc_path)
    mime = 'image/png' if upload_name.lower().endswith('.png') else 'image/jpeg'

    files = {'file': (upload_name, io.BytesIO(upload_bytes), mime)}
    r = client.post(f'/api/form/detect?detector={MODEL_NAME}', files=files)
    assert r.status_code == 200, f"Detect failed for {upload_name}: {r.status_code} {r.text[:200]}"
    assert r.headers.get('content-type', '').startswith('application/json')
    data = r.json()
    boxes = data.get('boxes', [])
    texts = data.get('texts', [])

    out_img = draw_boxes_and_text(img, boxes, texts)
    stem, _ = os.path.splitext(upload_name)
    out_path = os.path.join(out_dir, f"{stem}_detected.png")
    out_img.save(out_path)
    print(f"Wrote {out_path}")


def test_batch_detect_documents():
    """Process all images from test_documents, writing overlays. Fail on any non-200."""
    client = TestClient(app)
    in_dir = os.path.join(BASE_DIR, 'test_documents')
    out_dir = os.path.join(in_dir, 'output')
    assert os.path.isdir(in_dir), f"Missing test input dir: {in_dir}"
    ensure_dir(out_dir)

    for name in sorted(os.listdir(in_dir)):
        if name.lower().endswith(('.png', '.jpg', '.jpeg')):
            _process_document(client, os.path.join(in_dir, name), out_dir)


def test_single_document_debug():
    """Run detection on a single hardcoded document for easy debugging.
    Change DEBUG_DOC to select a specific file under test_documents/.
    """
    client = TestClient(app)
    DEBUG_DOC = 'irs.png'  # change to another file name for focused debugging
    DEBUG_DOC = 'employment.png'  # change to another file name for focused debugging

    in_dir = os.path.join(BASE_DIR, 'test_documents')
    out_dir = os.path.join(in_dir, 'output')
    ensure_dir(out_dir)

    doc_path = os.path.join(in_dir, DEBUG_DOC)
    assert os.path.exists(doc_path), f"Debug file not found: {doc_path}"
    assert DEBUG_DOC.lower().endswith(('.png', '.jpg', '.jpeg')), "Only image files are supported in debug test"

    _process_document(client, doc_path, out_dir)
