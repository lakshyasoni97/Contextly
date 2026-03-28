"""
Semantic icon search via ChromaDB.
Queries are per-concept; results are merged and re-ranked by best score.
"""
from typing import Optional

import chromadb

from .config import CHROMA_PATH, COLLECTION_NAME, TOP_K
from .embedder import embed_text

# Lazy-initialised singletons
_chroma: Optional[chromadb.PersistentClient] = None
_collection = None


def _get_collection():
    global _chroma, _collection
    if _collection is None:
        _chroma = chromadb.PersistentClient(path=CHROMA_PATH)
        _collection = _chroma.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


async def search_icons(concepts: list[str], top_k: int = TOP_K) -> list[dict]:
    """
    For each concept, embed it and query ChromaDB.
    Results are merged (deduplicated) and ranked by best similarity score.

    Returns:
        [{"name": str, "score": float, "tags": list[str]}, ...]
    """
    collection = _get_collection()

    best_score: dict[str, float] = {}
    best_tags: dict[str, str] = {}

    for concept in concepts:
        embedding = await embed_text(concept)
        results = collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            include=["distances", "metadatas"],
        )

        ids = results["ids"][0]
        distances = results["distances"][0]
        metadatas = results["metadatas"][0]

        for icon_id, dist, meta in zip(ids, distances, metadatas):
            score = 1.0 - float(dist)   # cosine distance → similarity
            if icon_id not in best_score or score > best_score[icon_id]:
                best_score[icon_id] = score
                best_tags[icon_id] = meta.get("tags", "")

    ranked = sorted(best_score.items(), key=lambda x: x[1], reverse=True)

    return [
        {
            "name": name,
            "score": round(score, 4),
            "tags": [t for t in best_tags[name].split(",") if t],
        }
        for name, score in ranked[:top_k]
    ]
