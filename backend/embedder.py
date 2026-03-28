"""
Google Gemini embedding wrapper.
Handles both single strings and batched lists.
Includes automatic rate-limit retry with exponential backoff.
"""
import asyncio
import time

from google import genai
from google.genai.errors import ClientError

from .config import GOOGLE_API_KEY, EMBEDDING_MODEL

_client = genai.Client(api_key=GOOGLE_API_KEY)

# Free-tier limit: 100 RPM → one request per 0.6s to stay safely under
_MIN_INTERVAL = 0.65   # seconds between batch calls
_last_call_at = 0.0
_call_lock = asyncio.Lock()


async def _throttled_embed(texts: list[str]) -> list[list[float]]:
    """
    Calls embed_content once, respecting the rate limit via a global lock
    and exponential backoff on 429 responses.
    """
    global _last_call_at

    max_retries = 8
    backoff = 15.0  # initial wait on 429 (API typically returns ~14s retry delay)

    for attempt in range(max_retries):
        async with _call_lock:
            # Throttle: ensure minimum interval between consecutive calls
            now = time.monotonic()
            gap = _MIN_INTERVAL - (now - _last_call_at)
            if gap > 0:
                await asyncio.sleep(gap)

            try:
                response = await _client.aio.models.embed_content(
                    model=EMBEDDING_MODEL,
                    contents=texts,
                )
                _last_call_at = time.monotonic()
                return [list(e.values) for e in response.embeddings]

            except ClientError as e:
                if e.code == 429:
                    _last_call_at = time.monotonic()
                    wait = backoff * (2 ** attempt)
                    print(f"    ⏳ Rate limit hit — waiting {wait:.0f}s (attempt {attempt+1}/{max_retries})")
                else:
                    raise

        # Wait outside the lock so other coroutines aren't blocked
        await asyncio.sleep(backoff * (2 ** attempt))

    raise RuntimeError(f"embed_content failed after {max_retries} attempts")


async def embed_text(text: str) -> list[float]:
    """Embed a single string. Used at query time."""
    result = await _throttled_embed([text])
    return result[0]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of strings.
    Sends one API call — the caller (index_builder) is responsible for
    batching at a reasonable chunk size (≤100 items).
    """
    return await _throttled_embed(texts)
