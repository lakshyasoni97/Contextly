"""
Build (or rebuild) the ChromaDB vector index from Lucide's tags.json.

Resumable: if a previous run was interrupted, re-running will skip icons
that are already in the collection and only embed the remaining ones.

Usage:
    python -m backend.index_builder            # build / resume
    python -m backend.index_builder --rebuild  # wipe and start over
"""
import json
import asyncio
import argparse

import chromadb

from .config import (
    CHROMA_PATH,
    TAGS_PATH,
    COLLECTION_NAME,
    EMBED_BATCH_SIZE,
    MIN_TAGS,
)
from .embedder import embed_texts
from .llm import generate_tags_for_icon


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_tags() -> dict[str, list[str]]:
    """
    Load data/tags.json (produced by download_lucide.py) and normalise to
    {icon_name: [tag, ...]}.

    Format produced by the downloader:
      { "name": { "tags": [...], "categories": [...] } }

    Categories are merged into the tag list so they contribute to embeddings
    (e.g. "finance", "account", "media" all become searchable terms).
    """
    with open(TAGS_PATH, "r") as f:
        raw: dict = json.load(f)

    icons: dict[str, list[str]] = {}
    for name, value in raw.items():
        if isinstance(value, list):
            icons[name] = value
        elif isinstance(value, dict):
            tags = list(value.get("tags", []))
            categories = value.get("categories", [])
            for cat in categories:
                if cat not in tags:
                    tags.append(cat)
            icons[name] = tags
        else:
            icons[name] = []
    return icons


def _icon_document(name: str, tags: list[str]) -> str:
    """Text document that represents an icon for embedding."""
    readable_name = name.replace("-", " ")
    return f"{readable_name}: {', '.join(tags)}"


def _get_already_indexed(collection) -> set[str]:
    """Return the set of icon names already stored in the collection."""
    total = collection.count()
    if total == 0:
        return set()
    # Fetch all IDs — ChromaDB returns them without embeddings (fast)
    result = collection.get(include=[])
    return set(result["ids"])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def build_index(force_rebuild: bool = False) -> None:
    print("=== Contextly — Index Builder ===\n")

    # 1. Load tags
    icons = _load_tags()
    print(f"→ Loaded {len(icons):,} icons from tags.json")

    # 2. Fill sparse icons — try LLM first, fall back to name-word tokens
    sparse = [name for name, tags in icons.items() if len(tags) < MIN_TAGS]
    if sparse:
        print(f"→ {len(sparse)} sparse icons — enriching with name-based fallback …")
        llm_skipped = 0
        for i, name in enumerate(sparse, 1):
            try:
                generated = await generate_tags_for_icon(name)
                if generated:
                    icons[name] = generated
                    continue
            except Exception:
                llm_skipped += 1

            # Fallback: split icon name into words
            name_words = name.replace("-", " ").split()
            existing_tags = set(icons.get(name, []))
            icons[name] = list(existing_tags | set(name_words))

            if i % 20 == 0 or i == len(sparse):
                print(f"   {i}/{len(sparse)}")

        if llm_skipped:
            print(f"   ↳ LLM skipped for {llm_skipped} icons — name fallback used")

    # 3. Open ChromaDB collection
    chroma = chromadb.PersistentClient(path=CHROMA_PATH)
    if force_rebuild:
        try:
            chroma.delete_collection(COLLECTION_NAME)
            print("→ Dropped existing collection")
        except Exception:
            pass

    collection = chroma.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    # 4. Determine which icons still need to be indexed (resumable)
    already_indexed = _get_already_indexed(collection)
    if already_indexed:
        print(f"→ Resuming: {len(already_indexed):,} icons already indexed, "
              f"{len(icons) - len(already_indexed):,} remaining")
    
    todo_names = [n for n in icons if n not in already_indexed]

    if not todo_names:
        print(f"✓ All {len(icons):,} icons already indexed — nothing to do.")
        print("  (Run with --rebuild to force a full rebuild.)")
        return

    # 5. Embed + store in batches (embed and write each batch immediately
    #    so progress is saved to disk even if the run is interrupted)
    total_todo = len(todo_names)
    print(f"→ Embedding & storing {total_todo:,} icons in batches of {EMBED_BATCH_SIZE} …")

    for i in range(0, total_todo, EMBED_BATCH_SIZE):
        batch_names = todo_names[i : i + EMBED_BATCH_SIZE]
        batch_docs  = [_icon_document(n, icons[n]) for n in batch_names]
        batch_meta  = [{"name": n, "tags": ",".join(icons[n])} for n in batch_names]

        # Embed
        embeddings = await embed_texts(batch_docs)

        # Write immediately — this is the checkpoint
        collection.add(
            ids=batch_names,
            embeddings=embeddings,
            documents=batch_docs,
            metadatas=batch_meta,
        )

        done = min(i + EMBED_BATCH_SIZE, total_todo)
        total_so_far = len(already_indexed) + done
        print(f"   {done}/{total_todo}  (total indexed: {total_so_far:,}/{len(icons):,})")

    print(f"\n✓ Done — {len(icons):,} icons indexed.\n")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the Contextly icon index")
    parser.add_argument(
        "--rebuild", action="store_true", help="Wipe the index and start from scratch"
    )
    args = parser.parse_args()
    asyncio.run(build_index(force_rebuild=args.rebuild))
