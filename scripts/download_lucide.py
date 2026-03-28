#!/usr/bin/env python3
"""
Download Lucide icon assets — run this once before building the index.

Steps:
    1. Lists all icons via the GitHub Git Tree API (one request, no pagination)
    2. Downloads every {name}.json  → aggregates into data/tags.json
    3. Downloads every {name}.svg   → saves into icons/

Usage:
    python scripts/download_lucide.py
"""
import asyncio
import json
import os

import httpx

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR    = os.path.join(PROJECT_DIR, "data")
ICONS_DIR   = os.path.join(PROJECT_DIR, "icons")

REPO        = "lucide-icons/lucide"
BRANCH      = "main"
TREE_URL    = f"https://api.github.com/repos/{REPO}/git/trees/{BRANCH}?recursive=1"
RAW         = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"

CONCURRENCY = 40   # parallel downloads


# ---------------------------------------------------------------------------
# Step 1 — list all icons via Git Tree API
# ---------------------------------------------------------------------------

async def fetch_icon_names(client: httpx.AsyncClient) -> list[str]:
    """
    Returns a list of icon names (without extension) by finding all
    icons/*.svg entries in the full git tree.
    """
    print("Fetching file tree from GitHub API …")
    resp = await client.get(TREE_URL, timeout=30, headers={"Accept": "application/vnd.github+json"})
    resp.raise_for_status()
    data = resp.json()

    if data.get("truncated"):
        print("  ⚠ Tree was truncated — some icons may be missing. Consider adding a GitHub token.")

    names = []
    for item in data.get("tree", []):
        path: str = item.get("path", "")
        # Only files directly in icons/ that end in .svg are actual icon SVGs
        if path.startswith("icons/") and path.endswith(".svg") and path.count("/") == 1:
            name = path[len("icons/"):-len(".svg")]
            names.append(name)

    print(f"  → Found {len(names):,} icons")
    return names


# ---------------------------------------------------------------------------
# Step 2 — download individual {name}.json, aggregate into tags.json
# ---------------------------------------------------------------------------

async def fetch_icon_json(client: httpx.AsyncClient, sem: asyncio.Semaphore, name: str) -> tuple[str, dict | None]:
    url = f"{RAW}/icons/{name}.json"
    async with sem:
        try:
            resp = await client.get(url, timeout=15)
            if resp.status_code == 200:
                return name, resp.json()
        except Exception:
            pass
    return name, None


async def download_all_metadata(client: httpx.AsyncClient, names: list[str]) -> dict:
    """
    Downloads {name}.json for every icon and aggregates into:
    { "icon-name": { "tags": [...], "categories": [...] }, ... }
    """
    sem = asyncio.Semaphore(CONCURRENCY)
    print(f"\nDownloading {len(names):,} icon metadata files …")

    tasks = [fetch_icon_json(client, sem, n) for n in names]
    aggregated: dict = {}
    done = 0
    failed = []

    for coro in asyncio.as_completed(tasks):
        name, data = await coro
        done += 1
        if data:
            aggregated[name] = {
                "tags":       data.get("tags", []),
                "categories": data.get("categories", []),
            }
        else:
            failed.append(name)
        if done % 200 == 0 or done == len(names):
            print(f"  {done}/{len(names)}")

    if failed:
        print(f"  ⚠ {len(failed)} metadata files failed: {failed[:5]}")

    return aggregated


# ---------------------------------------------------------------------------
# Step 3 — download {name}.svg
# ---------------------------------------------------------------------------

async def fetch_svg(client: httpx.AsyncClient, sem: asyncio.Semaphore, name: str) -> bool:
    dest = os.path.join(ICONS_DIR, f"{name}.svg")
    if os.path.exists(dest):
        return True
    url = f"{RAW}/icons/{name}.svg"
    async with sem:
        try:
            resp = await client.get(url, timeout=15)
            if resp.status_code == 200:
                with open(dest, "wb") as f:
                    f.write(resp.content)
                return True
        except Exception:
            pass
    return False


async def download_all_svgs(client: httpx.AsyncClient, names: list[str]) -> None:
    sem = asyncio.Semaphore(CONCURRENCY)
    print(f"\nDownloading {len(names):,} SVG files …")
    os.makedirs(ICONS_DIR, exist_ok=True)

    tasks = [fetch_svg(client, sem, n) for n in names]
    done = failed = 0

    for coro in asyncio.as_completed(tasks):
        ok = await coro
        done += 1
        if not ok:
            failed += 1
        if done % 200 == 0 or done == len(names):
            print(f"  {done}/{len(names)}")

    print(f"  ✓ {done - failed:,} SVGs saved  ({failed} failed)")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    print("=== Contextly — Lucide Asset Downloader ===\n")
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(ICONS_DIR, exist_ok=True)

    async with httpx.AsyncClient() as client:
        # 1. Get icon names
        names = await fetch_icon_names(client)

        # 2. Download metadata and aggregate
        aggregated = await download_all_metadata(client, names)

        # Save aggregated tags.json
        tags_path = os.path.join(DATA_DIR, "tags.json")
        with open(tags_path, "w") as f:
            json.dump(aggregated, f, indent=2)
        print(f"\n  ✓ tags.json saved ({len(aggregated):,} icons, {os.path.getsize(tags_path):,} bytes)")

        # 3. Download SVGs
        await download_all_svgs(client, names)

    print("\n✓ All done!")
    print("Next step → python -m backend.index_builder")


if __name__ == "__main__":
    asyncio.run(main())
