import os
import sys

# Ensure we import from playground directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from fastapi.testclient import TestClient  # type: ignore
from fastapi_server import app
from constants import MODEL_NAME
import io
from PIL import Image
from utils_for_tests import ensure_dir, draw_boxes_and_text


def test_health_ok():
    """Checks /api/health returns 200 and {'status': 'ok'}."""
    client = TestClient(app)
    r = client.get('/api/health')
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, dict)
    assert body.get('status') == 'ok'


def test_detect_endpoint_responds(sample_image):
    """Sends a sample image and asserts endpoint returns JSON; validates schema and timings when 200."""
    client = TestClient(app)
    # Use shared image from test_documents (provided by fixture)
    name, data_bytes, mime = sample_image
    files = {'file': (name, io.BytesIO(data_bytes), mime)}
    r = client.post(f'/api/form/detect?detector={MODEL_NAME}', files=files)

    # Endpoint should respond with JSON always
    assert r.headers.get('content-type', '').startswith('application/json')

    assert r.status_code == 200

    data = r.json()
    assert isinstance(data, dict)
    for k in ('image', 'normalized_scale', 'boxes', 'texts'):
        assert k in data
    assert isinstance(data['boxes'], list)
    assert isinstance(data['texts'], list)
    assert len(data['boxes']) == len(data['texts'])
    # Combined API should include timings and expected timing keys
    assert 'timings_ms' in data
    assert isinstance(data['timings_ms'], dict)
    assert 'combined_inference_ms' in data['timings_ms']
    assert 'combined_parse_ms' in data['timings_ms']


def test_draw_boxes_endpoint(sample_image):
    """Posts the sample image to /api/form/draw_boxes and expects JSON boxes; draws overlay locally to output dir."""
    client = TestClient(app)
    name, data_bytes, mime = sample_image
    files = {'file': (name, io.BytesIO(data_bytes), mime)}
    r = client.post('/api/form/draw_boxes?detector=' + MODEL_NAME, files=files)
    assert r.status_code == 200
    assert r.headers.get('content-type', '').startswith('application/json')
    data = r.json()
    assert 'normalized_scale' in data and data['normalized_scale'] == 1000
    assert 'boxes' in data and isinstance(data['boxes'], list)
    # If model returns no boxes due to parse error, we still proceed to draw (no-op) and save
    # Draw overlay locally and save to test_documents/output
    img = Image.open(io.BytesIO(data_bytes)).convert('RGB')
    out_dir = os.path.join(BASE_DIR, 'test_documents', 'output')
    ensure_dir(out_dir)
    out_img = draw_boxes_and_text(img, data['boxes'], [])
    stem, _ = os.path.splitext(name)
    out_path = os.path.join(out_dir, f"{stem}_boxes.png")
    out_img.save(out_path)
    assert os.path.exists(out_path)
 

