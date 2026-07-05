# Last Mile — Persistent Delivery-Site Memory

> **Hackathon:** The Hangover Part AI: Where's My Context? (WeMakeDevs × Cognee)

Last-mile delivery loses money every time a new driver rediscovers facts that a previous driver already knew — broken buzzers, gate codes, "dog on property," "only home after 5pm." Last Mile is a memory layer that captures those facts once and surfaces them to every future driver, regardless of whether they've ever been to that address before.

---

## Why graph + vector memory (why Cognee)?

Plain vector search solves the "is this note similar to my query" problem but can't answer "have two different drivers reported conflicting things about this buzzer in the last 30 days?" — that's a graph traversal question. Last Mile uses Cognee's hybrid architecture for both:

- **Graph layer** — address ↔ driver ↔ note ↔ delivery event relationships; conflict detection
- **Vector layer** — cold-start similarity: new address with no history gets guidance from semantically similar past situations
- **`improve()` / cognify** — turns "one driver said something once" into a confirmed operating fact; detects contradictions
- **`forget()`** — genuine privacy/compliance use case: purge a customer's address data on request

---

## Quick start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env — add your OPENAI_API_KEY (or ANTHROPIC_API_KEY)
```
By default `.env.example` is set up for [build.nvidia.com/models](https://build.nvidia.com/models)
(NVIDIA NIM), which exposes an OpenAI-compatible API. Grab a free API key from the catalog and drop
it into `LLM_API_KEY` / `EMBEDDING_API_KEY`. To use a different chat model from the catalog, swap the
slug in `LLM_MODEL` (keep the `openai/` LiteLLM prefix, e.g. `openai/mistralai/mixtral-8x22b-instruct-v0.1`).
To use OpenAI or Anthropic directly instead, set `LLM_PROVIDER=openai` or `LLM_PROVIDER=anthropic`.

### 3. Start the backend
```bash
# From the project root
uvicorn backend.main:app --reload
```
API runs at http://localhost:8000 — docs at http://localhost:8000/docs

### 4. Start the frontend
```bash
# In a second terminal
streamlit run frontend/app.py
```
UI runs at http://localhost:8501

### 5. Load demo data
In the Streamlit sidebar, click **"Load demo data"** — or hit the API directly:
```bash
curl -X POST http://localhost:8000/seed
```

---

## Deploy to Railway

This is two services (FastAPI backend + Streamlit frontend) from one repo. No Dockerfile needed —
Railway's Railpack builder auto-detects Python from `requirements.txt`.

### 1. Push to GitHub, then create a Railway project from that repo
Railway will create one service by default — treat that as the **backend**.

### 2. Configure the backend service
- **Settings → Config-as-code → Config File Path** → `backend/railway.json`
  (this sets the build/start command and health check — see that file)
- **Settings → Networking → Generate Domain** to get a public URL
- **Variables** — add:
  ```
  LLM_PROVIDER=custom
  LLM_MODEL=openai/meta/llama-3.1-8b-instruct
  LLM_ENDPOINT=https://integrate.api.nvidia.com/v1
  LLM_API_KEY=nvapi-...
  EMBEDDING_PROVIDER=fastembed
  EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
  EMBEDDING_DIMENSIONS=384
  FAILED_DELIVERY_COST=15.0
  STALE_NOTE_DAYS=30
  ```
  (swap in `openai`/`anthropic` + their key instead, if you'd rather not use NVIDIA NIM)

### 3. Add a second service for the frontend
**New → GitHub Repo** → same repo again. Then:
- **Settings → Config-as-code → Config File Path** → `frontend/railway.json`
- **Settings → Networking → Generate Domain**
- **Variables** — add `API_BASE=https://<backend-service-domain-from-step-2>`

### 4. Persistence (optional but recommended)
Railway's container filesystem doesn't survive redeploys. To keep delivery notes and the memory
graph across deploys, attach a **Volume** to the backend service (e.g. mounted at `/data`) and add:
```
SQLITE_DB_PATH=/data/last_mile.db
DATA_ROOT_DIRECTORY=/data/.data_storage
SYSTEM_ROOT_DIRECTORY=/data/.cognee_system
CACHE_ROOT_DIRECTORY=/data/.cognee_cache
```
Without a volume, the app still works — you'll just need to hit "Load demo data" again after each deploy.

### 5. Seed the demo data
Once both services are deployed, click **"Load demo data"** in the frontend, or:
```bash
curl -X POST https://<backend-service-domain>/seed
```

---

## Memory lifecycle demo (3-part narrative)

| Scene | Address | What it shows |
|---|---|---|
| **Cold start** | 500 Pine Boulevard | No history → similarity-based fallback briefing |
| **Rich memory** | 88 Oak Street, Unit 12 | 5 driver confirmations → HIGH confidence briefing (gate code, dog, porch drop) |
| **Conflict resolution** | 142 Maple Ave, Unit 3A | Buzzer broken (3 reports) → buzzer fixed (2 recent) → improve() resolves recency |
| **Problem address** | 33 Elm Court | 6 deliveries, 5 failed → ops dashboard flags cost impact |
| **Stale data** | 201 Cedar Lane | Notes from 35+ days → flagged as potentially stale |

---

## API reference

| Method | Path | Cognee lifecycle |
|---|---|---|
| `POST` | `/notes` | `remember()` |
| `GET` | `/briefing/{address_id}` | `recall()` |
| `POST` | `/improve/{address_id}` | `improve()` |
| `DELETE` | `/forget/{address_id}` | `forget()` |
| `GET` | `/dashboard` | — (ops view) |
| `POST` | `/seed` | loads demo dataset |
| `POST` | `/landmarks/resolve` | resolves a landmark description to an address_id |
| `POST` | `/transcribe` | voice-note transcription |

---

## Landmark-based addressing

The urban framing of this problem ("which Sector 22?") is the smaller, better-served version. The
harder one: villages and areas with **no formal address at all** — delivery is human-navigated
("near the temple, ask for Salim's house near Pasha's shop"). `backend/landmarks.py` lets a
delivery location be a free-text landmark description instead of a formal address:

- The description is embedded and compared against every previously seen landmark, so "near the
  temple" from one driver and "Shiv Mandir ke paas, peeche wala ghar" from another collapse onto
  the same memory instead of fragmenting into duplicate, un-findable records.
- A confident match (similarity ≥ `LANDMARK_AUTO_MATCH_THRESHOLD`, default `0.65`) reuses the
  existing cluster immediately. An ambiguous one (≥ `LANDMARK_SUGGEST_THRESHOLD`, default `0.45`)
  is surfaced as "did you mean this place?" for the driver to confirm — a wrong auto-merge (sending
  the next driver to the wrong physical location) is worse than asking once.
- Runs a small multilingual paraphrase embedding model locally (`fastembed`, no API key), calibrated
  against Hindi/English mixed-language test pairs — a plain English-only model couldn't reliably
  tell same-place paraphrases apart from different-place descriptions at all.
- Once resolved, a landmark cluster is just an `address_id` like any other — `/notes`, `/briefing`,
  `/improve`, `/forget`, and the ops dashboard all work on it unchanged.

Try it in the Streamlit driver app: both the briefing and log-note tabs have a
**"Landmark / no formal address"** mode.

---

## Business model

B2B SaaS API sold to regional/mid-market delivery operators, courier networks, and last-mile aggregators. Priced against the cost it displaces — a 15% reduction in failed-first-attempt rate across 1,000 weekly deliveries at $15/failure saves ~$1,170/week per operator. The cross-operator anonymized pattern-sharing roadmap item (learn once, benefit every courier serving that building) is a genuine network-effect moat.

---

## Stack

| Layer | Choice |
|---|---|
| Memory | Cognee (graph + vector hybrid) |
| Backend | Python + FastAPI |
| Frontend | Streamlit (Next.js upgrade path planned) |
| Database | SQLite (structured metadata + ops dashboard) |
