# Contextly

Most people spend way too long digging through icon libraries. You search for "growth" and get a picture of a plant when you actually needed a financial chart. **Contextly** fixes that.

It's a simple tool: give it a slide, it understands the *intent* of your slide, and hands you the right SVGs to paste directly into your presentation.

## Why use this?

- **Keyword search is dumb:** Standard search doesn't understand context. Contextly uses semantic embeddings to find icons that match your actual topic — not just your words.
- **Zero friction:** No downloading icons just to re-upload them. One click to copy, one shortcut to paste.
- **Consistency:** Everything is pulled from the **Lucide** library, so your icons will actually look like they belong together.

## How it works

1. **Input:** Drop a screenshot of a slide or paste your bullet points.
2. **Analysis:** An LLM extracts the 3–5 core concepts being discussed.
3. **Vector match:** Those concepts are queried against a vector index built from Lucide's icon tag metadata — so "revenue growth" finds `chart-bar`, not `sprout`.
4. **Action:** You get a ranked list of matches. Hit copy and paste them into your presentation tool.

## The tech

- **Backend:** Python
- **Search:** Semantic embeddings + ChromaDB for vector matching
- **Icon metadata:** `tags.json` from the Lucide repository — each icon's tag list is embedded at index-build time
- **Icon assets:** Lucide SVG files bundled directly (no library wrapper needed — just a flat directory of `.svg` files keyed by icon name)
- **Clipboard:** PNG copy by default (works everywhere); SVG download available for when you need the vector

## Setup & Local Usage

Follow these steps to get Contextly running on your machine:

### 1. Environment Setup

Create a virtual environment and install the dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configuration

Create a `.env` file in the project root and add your [Google AI Studio API Key](https://aistudio.google.com/app/apikey):

```env
GOOGLE_API_KEY=your_api_key_here
```

### 3. Prepare Assets

First, download the latest icons and metadata from the Lucide repository:

```bash
python scripts/download_lucide.py
```

Then, build the semantic search index (this may take a few minutes as it generates embeddings):

```bash
python -m backend.index_builder
```

*Note: The indexer is resumable — if it stops, just run it again to pick up where you left off.*

### 4. Run the Server

Start the FastAPI development server:

```bash
uvicorn backend.main:app --reload
```

Open your browser to **[http://localhost:8000](http://localhost:8000)** to start finding icons!

### How the index is built

```
tags.json  →  embed each icon's tag list  →  store in ChromaDB
                                                      ↓
slide text  →  LLM extracts concepts  →  query ChromaDB  →  get icon names  →  read SVGs from disk
```

At setup time, any icons with missing or sparse tags get a one-time LLM pass to generate tags — so coverage is complete, and the index never needs to be rebuilt unless Lucide ships new icons.

## Platform compatibility

Contextly copies icons as **PNG by default**, which works across all major presentation tools without any extra steps. A **Download SVG** option is also available for when you need the vector format.

| Platform | PNG paste | SVG paste | Notes |
|---|---|---|---|
| Keynote (Mac) | ✓ | ✓ | SVG clipboard works natively |
| PowerPoint (Mac) | ✓ | ✓ | Requires Office 365+ |
| PowerPoint (Windows) | ✓ | ~ | SVG paste is inconsistent; PNG recommended |
| Google Slides | ✓ | ✗ | No SVG clipboard support; use Insert → Image |

## What it doesn't do

- Contextly does not generate custom icons — every icon comes from the Lucide library.
- It does not directly inject icons into your presentation file. You copy, you paste.
- Google Slides users will need to use the Download SVG / PNG and upload manually via *Insert → Image*. There is no programmatic paste path into Google Slides.