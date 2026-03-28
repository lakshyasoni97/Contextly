"""
LLM helpers — concept extraction from slide text/image,
and one-time tag generation for sparse Lucide icons.
"""
import json
from typing import Optional

from google import genai
from google.genai import types

from .config import GOOGLE_API_KEY, LLM_MODEL

_client = genai.Client(api_key=GOOGLE_API_KEY)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_CONCEPT_SUFFIX = (
    "Extract 4-6 core visual concepts from this slide that would be well "
    "represented by icons. Focus on concrete, specific ideas — not abstractions.\n"
    'Return ONLY a JSON array of short strings. No markdown, no explanation.\n'
    'Example: ["bar chart", "user profile", "cloud upload", "lock", "settings"]'
)

_TAGGEN_PROMPT = (
    'Generate 10 descriptive tags for the icon named "{name}".\n'
    "Tags should describe what the icon looks like AND what it symbolises.\n"
    "Return ONLY a JSON array of strings. No markdown, no explanation."
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def extract_concepts_from_text(text: str) -> list[str]:
    """Extract icon concepts from plain slide text."""
    prompt = f"{_CONCEPT_SUFFIX}\n\nSlide content:\n{text}"
    response = await _client.aio.models.generate_content(
        model=LLM_MODEL,
        contents=prompt,
    )
    return _parse_list(response.text)


async def extract_concepts_from_image(image_data: bytes, mime_type: str = "image/png") -> list[str]:
    """Extract icon concepts from a slide screenshot."""
    response = await _client.aio.models.generate_content(
        model=LLM_MODEL,
        contents=[
            types.Part.from_bytes(data=image_data, mime_type=mime_type),
            _CONCEPT_SUFFIX,
        ],
    )
    return _parse_list(response.text)


async def generate_tags_for_icon(name: str) -> list[str]:
    """One-time tag generation for icons with sparse/missing tags.json metadata."""
    prompt = _TAGGEN_PROMPT.format(name=name.replace("-", " "))
    response = await _client.aio.models.generate_content(
        model=LLM_MODEL,
        contents=prompt,
    )
    return _parse_list(response.text)


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _parse_list(raw: str) -> list[str]:
    """Robustly parse a JSON list from an LLM response."""
    raw = raw.strip()
    # Strip markdown code fences if present
    if "```" in raw:
        for block in raw.split("```"):
            block = block.strip().lstrip("json").strip()
            if block.startswith("["):
                raw = block
                break
    try:
        result = json.loads(raw)
        if isinstance(result, list):
            return [str(x).strip() for x in result if x]
    except json.JSONDecodeError:
        pass
    return []
