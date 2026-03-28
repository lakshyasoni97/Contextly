# Deploying Contextly — Free Hosting + Auth

## Overview

The stack I recommend: **Render** (hosting) + **Clerk** (auth). Both have generous free tiers and require no credit card.

| Service | What it does | Free tier |
|---|---|---|
| **Render** | Hosts the FastAPI app | 750 hrs/mo, spins to sleep after 15 min idle |
| **Clerk** | Authentication (email, Google, GitHub login) | 10,000 MAU forever |

> [!IMPORTANT]
> The pre-built ChromaDB index (15MB) and icon SVGs (6.6MB) will be **committed directly to the git repo** and served from disk — so no managed vector DB is needed. This works because the index is built once and read-only at runtime.

---

## Architecture

```
Browser (Clerk JS SDK)
  │
  ├── GET /          → served by Render (FastAPI), no auth required (login page)
  ├── POST /analyze/ → requires valid Clerk JWT in Authorization header
  └── GET /icon/     → public (SVGs are not sensitive)
```

---

## Proposed Changes

### New Files

#### [NEW] `backend/auth.py`
FastAPI dependency that validates Clerk JWTs:
- Fetches Clerk's public JWKS endpoint to verify tokens
- Returns 401 if missing/expired/invalid
- Usable as a FastAPI `Depends()` on any protected route

#### [NEW] `.gitignore` additions
Make sure `.env` is ignored, but `chroma_db/`, `icons/`, `data/` are **committed** (they're the pre-built assets).

#### [NEW] `render.yaml`
Render deploy config — defines the web service, build command, and start command.

### Modified Files

#### [MODIFY] `backend/main.py`
- Add `Depends(get_current_user)` to `/analyze/text` and `/analyze/image` routes
- Keep `/`, `/icon/{name}`, and `/health` public

#### [MODIFY] `frontend/index.html` + `frontend/app.js`
- Add the `@clerk/clerk-js` CDN script
- Add a sign-in gate: show Clerk's hosted sign-in UI if not authenticated
- Attach the Clerk JWT to all `fetch()` calls in `Authorization: Bearer <token>` header
- Show a sign-out button in the header

#### [MODIFY] `requirements.txt`
- Add `python-jose[cryptography]` for JWT verification

---

## Deployment Steps (after code changes)

1. Create a free account at [clerk.com](https://clerk.com) → create an Application → copy the **Publishable Key** and **Secret Key**
2. Create a free account at [render.com](https://render.com) → connect your GitHub repo
3. Add env vars on Render dashboard: `GOOGLE_API_KEY`, `CLERK_SECRET_KEY`
4. Push to GitHub → Render auto-deploys

---

## Open Questions

> [!NOTE]
> **Who should be able to sign up?** Clerk supports:
> - **Open sign-up** (anyone with an email/Google account can log in) — best for sharing with friends
> - **Allowlist** (only specific emails) — restrict to just yourself or a small group
>
> Which do you prefer?

> [!WARNING]
> Render's **free web services spin down after 15 minutes of inactivity** and take ~30 seconds to cold-start on the next request. For personal/demo use this is fine. If you need it always-on, Render's cheapest paid plan is $7/mo.
