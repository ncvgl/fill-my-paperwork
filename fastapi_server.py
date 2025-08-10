from fastapi import FastAPI, UploadFile, File, Query, Request, Depends, HTTPException
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageDraw
import io
import json
import os
import time
import secrets
import hmac
import hashlib
import urllib.parse

try:
    from google import genai
    from google.genai.types import GenerateContentConfig, Part
except Exception:
    genai = None
    GenerateContentConfig = None
    Part = None

from constants import MODEL_NAME

app = FastAPI()

# NOTE: Do NOT enable permissive CORS. Since frontend and backend
# are served from the same origin, same-origin requests do not need CORS.

# Serve local fonts (e.g., Satisfy.ttf) under /fonts
if os.path.isdir("fonts"):
    app.mount("/fonts", StaticFiles(directory="fonts"), name="fonts")


def _get_client():
    if genai is None:
        raise RuntimeError("google-genai is not installed. pip install google-genai")
    project = os.environ.get("GCP_PROJECT", "")
    location = os.environ.get("GCP_LOCATION", "europe-west9")
    return genai.Client(vertexai=True, project=project, location=location)


def _detect_and_fake(image_bytes: bytes, mime_type: str, model: str):
    """Single Gemini call that returns both boxes and fake text per box.

    The model is instructed to omit very small boxes (checkboxes etc.). We also post-filter on server.
    Expected model JSON: [ {"box_2d": [y_min,x_min,y_max,x_max], "text": "..."}, ... ]
    """
    client = _get_client()
    config = GenerateContentConfig(
        system_instruction=(
            """
You are given an image of a paper form. Find all fields where a human is expected to WRITE text (e.g., blank lines, long empty boxes) and, for each, produce:

- label_box_2d: bounding box for the nearest descriptive label or prompt text for that field
- input_box_2d: bounding box for the empty area where the user writes their answer
- text: a realistic, context-appropriate fake value that matches what the field expects

Important rules:
- INCLUDE small tick, circle, checkbox boxes as fields too. When a field is very small (roughly room for ≤3 letters), it is likely a check box. It is acceptable to return these; setting text to "x" is fine for such small fields.
- Return ONLY a JSON array where each element is an object with exactly these keys:
  {"label_box_2d": [y_min, x_min, y_max, x_max], "input_box_2d": [y_min, x_min, y_max, x_max], "text": "..."}
- All coordinates must be normalized to 0–1000 and should be integers.
- If a field should be left blank purposely, set text to an empty string "" (never the word None).
            """
        ),
        response_mime_type="application/json",
    )
    contents = [
        Part.from_bytes(data=image_bytes, mime_type=mime_type),
        "Return bounding boxes and fake text for writable fields only.",
    ]

    t0 = time.perf_counter()
    resp = client.models.generate_content(
        model=model,
        contents=contents,
        config=config,
    )
    inference_ms = int((time.perf_counter() - t0) * 1000)

    t1 = time.perf_counter()
    data = json.loads(resp.text)
    if not isinstance(data, list):
        data = []
    # Normalize entries and coerce None/'None' to empty string
    normalized = []
    for entry in data:
        if isinstance(entry, dict) and ("input_box_2d" in entry or "box_2d" in entry):
            # Prefer input_box_2d when present; fall back to single box_2d
            box = entry.get("input_box_2d") or entry.get("box_2d")
            txt = entry.get("text", "")
        elif isinstance(entry, list) and len(entry) >= 4:
            # Some models might emit just arrays
            box, txt = entry[:4], ""
        else:
            continue
        if isinstance(txt, str):
            if txt.strip().lower() == "none":
                txt = ""
        elif txt is None:
            txt = ""
        normalized.append({"box_2d": box, "text": txt})

    parse_ms = int((time.perf_counter() - t1) * 1000)
    return normalized, {"inference_ms": inference_ms, "parse_ms": parse_ms}


SMALL_BOX_PX_THRESHOLD = 30  # width in pixels considered too small to contain >3 letters


SESSION_SECRET = (os.environ.get("SESSION_SECRET") or "dev-secret-change-me").encode("utf-8")
SESSION_COOKIE_NAME = "_sess"
CSRF_COOKIE_NAME = "_csrf"
CSRF_HEADER_NAME = "x-csrf-token"


def _sign_value(value: str) -> str:
    signature = hmac.new(SESSION_SECRET, value.encode("utf-8"), hashlib.sha256).hexdigest()
    return signature


def _issue_session_and_csrf_cookies(resp: Response, base_url: str) -> None:
    # Stateless signed session token and CSRF token (double submit cookie pattern)
    session_id = secrets.token_urlsafe(32)
    session_token = f"{session_id}.{_sign_value(session_id)}"
    csrf_token = secrets.token_urlsafe(32)

    # Always set cookies on landing page to establish a session
    # Secure flags are on; SameSite=Lax is sufficient for same-origin
    is_secure = base_url.startswith("https://")

    resp.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        httponly=True,
        secure=is_secure,
        samesite="Lax",
        path="/",
    )
    resp.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        secure=is_secure,
        samesite="Lax",
        path="/",
    )


def _first_header_value(raw: str | None) -> str:
    if not raw:
        return ""
    return raw.split(",", 1)[0].strip()


def _normalize_host(host: str) -> str:
    # Lowercase and strip default ports
    host = (host or "").strip().lower()
    if host.endswith(":80"):
        return host[:-3]
    if host.endswith(":443"):
        return host[:-4]
    return host


def _service_origin(request: Request) -> str:
    """Best-effort origin for this service using proxy headers when present."""
    proto = _first_header_value(request.headers.get("x-forwarded-proto")) or request.url.scheme or "http"
    forwarded_host = _first_header_value(request.headers.get("x-forwarded-host"))
    host = forwarded_host or _first_header_value(request.headers.get("host")) or urllib.parse.urlparse(str(request.base_url)).netloc
    return f"{proto}://{host}"


def _origin_of(url: str) -> str:
    p = urllib.parse.urlparse(url)
    if not p.scheme or not p.netloc:
        return ""
    return f"{p.scheme}://{p.netloc}"


def _validate_same_origin(request: Request) -> None:
    # Allow only requests originating from the same origin as this service.
    # If both Origin and Referer are absent, allow and rely on CSRF/session checks.
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")

    base = _service_origin(request)
    base_host = _normalize_host(urllib.parse.urlparse(base).netloc)

    if origin:
        origin_host = _normalize_host(urllib.parse.urlparse(origin).netloc)
        if origin_host != base_host:
            raise HTTPException(status_code=403, detail="forbidden: cross-origin not allowed")
        return
    if referer:
        referer_host = _normalize_host(urllib.parse.urlparse(referer).netloc)
        if referer_host != base_host:
            raise HTTPException(status_code=403, detail="forbidden: cross-origin not allowed")
        return
    # No Origin or Referer headers: allow; CSRF + session will still protect
    return


def _validate_session_and_csrf(request: Request) -> None:
    # Validate signed session cookie
    sess = request.cookies.get(SESSION_COOKIE_NAME)
    if not sess or "." not in sess:
        raise HTTPException(status_code=403, detail="forbidden: no session")
    session_id, signature = sess.rsplit(".", 1)
    if not hmac.compare_digest(signature, _sign_value(session_id)):
        raise HTTPException(status_code=403, detail="forbidden: invalid session")

    # For state-changing requests, require CSRF header matching CSRF cookie
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
        csrf_header = request.headers.get(CSRF_HEADER_NAME)
        if not csrf_cookie or not csrf_header or not hmac.compare_digest(csrf_cookie, csrf_header):
            raise HTTPException(status_code=403, detail="forbidden: csrf failed")


async def frontend_only(request: Request):
    _validate_same_origin(request)
    _validate_session_and_csrf(request)


@app.get("/api/health")
async def health(dep: None = Depends(frontend_only)):
    return {"status": "ok"}


@app.get("/.well-known/appspecific/com.chrome.devtools.json")
async def chrome_devtools_probe():
    # Quiet Chrome DevTools probe with no content
    return Response(status_code=204)

@app.get("/")
async def root_index(request: Request):
    # Serve the main UI and set session + CSRF cookies so only this frontend can call APIs
    resp = FileResponse("index.html")
    # Use proxy headers to compute the public origin for cookie flags
    public_origin = _service_origin(request)
    _issue_session_and_csrf_cookies(resp, base_url=public_origin)
    return resp

@app.get("/dev-preload.jpg")
async def preload_image():
    return FileResponse("dev-preload.jpg")


@app.post("/api/form/detect")
async def detect(
    file: UploadFile = File(...),
    detector: str = Query(MODEL_NAME, description="Combined model for boxes+text"),
    dep: None = Depends(frontend_only),
):
    t_route_start = time.perf_counter()
    content = await file.read()
    mime_type = file.content_type or "image/png"
    # Validate it's an image and get dimensions
    t_img_open_start = time.perf_counter()
    with Image.open(io.BytesIO(content)) as img:
        width, height = img.size
    image_open_ms = int((time.perf_counter() - t_img_open_start) * 1000)
    try:
        (combined, t_combined) = _detect_and_fake(content, mime_type, detector)
        # Post-filter: drop tiny boxes (by pixel width) and build boxes/texts arrays
        boxes = []
        texts = []
        for item in combined:
            box = item.get("box_2d")
            txt = item.get("text", "")
            if not isinstance(box, list) or len(box) != 4:
                continue
            y_min, x_min, y_max, x_max = box
            width_px = int((x_max - x_min) / 1000 * width)
            if width_px <= SMALL_BOX_PX_THRESHOLD:
                # Small checkbox-like field: mark with an 'x'
                boxes.append({"box_2d": box})
                texts.append("x")
                continue
            boxes.append({"box_2d": box})
            texts.append(txt or "")

        total_ms = int((time.perf_counter() - t_route_start) * 1000)
        return JSONResponse({
            "image": {"width": width, "height": height},
            "normalized_scale": 1000,
            "boxes": boxes,
            "texts": texts,
            "timings_ms": {
                "combined_inference_ms": t_combined.get("inference_ms", 0),
                "combined_parse_ms": t_combined.get("parse_ms", 0),
                "image_open_ms": image_open_ms,
                "total_ms": total_ms,
            },
        })
    except Exception as e:
        total_ms = int((time.perf_counter() - t_route_start) * 1000)
        return JSONResponse({"error": str(e), "timings_ms": {"total_ms": total_ms, "image_open_ms": image_open_ms}}, status_code=500)


@app.post("/api/form/draw_boxes")
async def draw_boxes(
    file: UploadFile = File(...),
    detector: str = Query(
        "gemini-2.5-flash-lite",
        description="Model for boxes-only: gemini-2.5-flash-lite or gemini-2.5-pro",
    ),
    dep: None = Depends(frontend_only),
):
    """Detects fields and returns only bounding box locations as JSON."""
    content = await file.read()
    mime_type = file.content_type or "image/png"
    try:
        combined, _ = _detect_and_fake(content, mime_type, detector)
        boxes = []
        for item in combined:
            box = item.get("box_2d")
            if isinstance(box, list) and len(box) == 4:
                boxes.append({"box_2d": box})
        return JSONResponse({"normalized_scale": 1000, "boxes": boxes})
    except Exception as e:
        # Be lenient for boxes-only route: return empty boxes on model/parse errors
        return JSONResponse({"normalized_scale": 1000, "boxes": [], "error": str(e)})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001, reload=True)
