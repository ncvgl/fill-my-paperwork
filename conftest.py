import os
import io
import pytest

# Base directory for tests (the playground folder)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@pytest.fixture(scope="session")
def sample_image():
    """Provides a (name, bytes, mime) tuple for a test image from test_documents.
    The image is unmodified and safe to reuse across tests.
    """
    img_path = os.path.join(BASE_DIR, 'test_documents', 'english.jpg')
    assert os.path.exists(img_path), f"Test image not found at {img_path}"
    with open(img_path, 'rb') as f:
        data = f.read()
    mime = 'image/png'
    return ('irs.png', data, mime)
