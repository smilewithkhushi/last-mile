# StreetSense — Persistent Delivery-Site Memory

> **Hackathon:** The Hangover Part AI: Where's My Context? (WeMakeDevs × Cognee)

Last-mile delivery loses money every time a new driver rediscovers facts that a previous driver already knew — broken buzzers, gate codes, "dog on property," "only home after 5pm." StreetSense is a memory layer that captures those facts once and surfaces them to every future driver, regardless of whether they've ever been to that address before.

---

## Why graph + vector memory (why Cognee)?

Plain vector search solves the "is this note similar to my query" problem but can't answer "have two different drivers reported conflicting things about this buzzer in the last 30 days?" — that's a graph traversal question. StreetSense uses Cognee's hybrid architecture for both:

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
