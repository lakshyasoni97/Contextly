"""
FastAPI application — serves the REST API and the frontend static files.

Endpoints:
    GET  /                      → frontend index.html
    POST /analyze/text          → {text} → {concepts, icons}
    POST /analyze/image         → file upload → {concepts, icons}
    GET  /icon/{name}           → serves the Lucide SVG file
    POST /build-index           → trigger index build (optional force rebuild)
    GET  /health                → liveness check
"""
import os
import asyncio

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import BASE_DIR, ICONS_DIR
from .llm import extract_concepts_from_image, extract_concepts_from_text
from .search import search_icons
from .index_builder import build_index

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Contextly",
    description="Semantic icon finder for presentations",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend static files at /static/*
_frontend_dir = os.path.join(BASE_DIR, "frontend")
if os.path.isdir(_frontend_dir):
    app.mount("/static", StaticFiles(directory=_frontend_dir), name="static")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class TextRequest(BaseModel):
    text: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def serve_frontend():
    index = os.path.join(_frontend_dir, "index.html")
    if not os.path.exists(index):
        raise HTTPException(404, "Frontend not found")
    return FileResponse(index)


@app.post("/analyze/text")
async def analyze_text(req: TextRequest):
    if not req.text.strip():
        raise HTTPException(400, "text must not be empty")
    concepts = await extract_concepts_from_text(req.text)
    if not concepts:
        raise HTTPException(422, "Could not extract concepts — check your input")
    icons = await search_icons(concepts)
    return {"concepts": concepts, "icons": icons}


@app.post("/analyze/image")
async def analyze_image(file: UploadFile = File(...)):
    allowed = {"image/png", "image/jpeg", "image/webp", "image/gif"}
    if file.content_type not in allowed:
        raise HTTPException(415, f"Unsupported image type: {file.content_type}")
    data = await file.read()
    concepts = await extract_concepts_from_image(data, file.content_type)
    if not concepts:
        raise HTTPException(422, "Could not extract concepts from image")
    icons = await search_icons(concepts)
    return {"concepts": concepts, "icons": icons}


@app.get("/icon/{name}")
async def get_icon(name: str):
    # Sanitise — only allow alphanumeric and hyphens
    safe_name = "".join(c for c in name if c.isalnum() or c == "-")
    svg_path = os.path.join(ICONS_DIR, f"{safe_name}.svg")
    if not os.path.isfile(svg_path):
        raise HTTPException(404, f"Icon '{safe_name}' not found")
    return FileResponse(svg_path, media_type="image/svg+xml")


@app.post("/build-index")
async def trigger_build(force: bool = False):
    asyncio.create_task(build_index(force_rebuild=force))
    return {"status": "building", "force": force}


@app.get("/health")
async def health():
    return {"status": "ok"}
