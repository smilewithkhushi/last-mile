# Product Requirements Document
## Project Name (working title): **StreetSense** — Persistent Delivery-Site Memory

**Hackathon:** The Hangover Part AI: Where's My Context? (WeMakeDevs × Cognee)
**Author:** [Your name/team]
**Date:** July 2026
**Status:** Draft v1

---

## 1. Problem Statement

Last-mile delivery is the most expensive and failure-prone leg of logistics, and a large share of that cost comes from **knowledge that never gets captured**: buzzer codes, "leave with the neighbor," dogs on the property, gate codes, "call before arriving," which entrance to use, which hours the customer is actually home. This knowledge lives entirely in a driver's head or a scrawled note. It doesn't survive to the next delivery, and it certainly doesn't survive the driver quitting — which, in gig-driver networks, happens constantly.

Every new driver re-discovers the same facts about the same addresses, one failed attempt at a time. Failed deliveries trigger redelivery costs, support tickets, and customer trust erosion — a compounding tax that nobody has built a system to eliminate, because most "AI for last-mile" investment goes into routing and orchestration, not institutional memory.

**Core insight:** the delivery network should remember a location even when every individual driver working it is brand new.

---

## 2. Target Users & Buyers

| Role | Who they are | What they need |
|---|---|---|
| **Buyer (economic)** | Ops lead / Head of Delivery at a regional courier, food-delivery platform, or 3PL | Fewer failed-attempt costs, fewer support tickets, measurable on-time improvement |
| **End user (driver/courier)** | Gig or contracted driver, often new to the route | A quick, trustworthy answer to "what do I need to know before I get there" |
| **Indirect beneficiary** | The recipient/customer | Fewer missed deliveries, less repeating themselves to every new driver |

**Not the target for v1:** enterprise carriers like UPS/Amazon (they already have proprietary systems at that scale). The wedge is regional/mid-market delivery operators and delivery-network aggregators who don't have this infrastructure and can't build it themselves.

---

## 3. Product Vision

A lightweight memory layer that sits alongside any dispatch or delivery app. Every time a driver completes (or fails) a delivery, the system captures what happened at that address in plain language. Before the next driver arrives at that same address — regardless of who they are — the system surfaces exactly what they need to know, with confidence built from every prior visit, not just the last one.

---

## 4. Goals & Success Metrics (for the hackathon submission)

| Goal | Metric | Why it matters for judging |
|---|---|---|
| Prove the memory loop works end-to-end | remember → recall → improve → forget all demonstrably functioning | "Best Use of Cognee" criterion explicitly rewards full lifecycle usage |
| Show it solves a real cost problem | Simulated reduction in failed-first-attempt rate on demo dataset | "Potential Impact" |
| Show it's usable, not just a backend | A driver-facing screen that answers "what should I know here" in under a second | "User Experience" |
| Show it's a coherent business, not a toy | Clear buyer, pricing logic, and expansion path | Differentiates from generic hackathon demos |

---

## 5. Product Features

### 5.1 MVP (hackathon scope — must ship)

1. **Delivery note capture**
   - After a delivery (success or failure), driver logs a short free-text or voice note: e.g. "buzzer broken, use side door," "left with neighbor unit 4B," "dog on property, don't approach gate."
   - Notes are tied to a specific address/unit, a driver, and a timestamp.

2. **Pre-arrival briefing (the core "aha" feature)**
   - Before a driver is dispatched to an address, they get a short, synthesized briefing: the current best-known facts about that address, weighted by recency and how many drivers have confirmed them.
   - If the address has no history, the system falls back to similarity: "buildings like this one typically need a gate code" or "similar addresses in this area require call-ahead."

3. **Conflict reconciliation**
   - When two notes disagree (e.g., one driver says "buzzer works," another says "buzzer broken" a month later), the system doesn't just store both — it resolves which is more likely current and flags the address for review if conflicts persist.

4. **Confidence signaling**
   - Every fact shown to a driver carries an implicit trust level: "confirmed by multiple visits" vs. "reported once, unverified." This is the difference between tribal knowledge and institutional knowledge.

5. **Manual/automatic forgetting**
   - Stale facts age out automatically after a defined window unless reconfirmed.
   - Ops admins can manually purge a customer's data on request (privacy/compliance story).

6. **Ops dashboard (lightweight)**
   - A simple view for the delivery-ops buyer: which addresses generate the most failed attempts, what the system has learned about them, and the estimated redelivery cost avoided.

### 5.2 Post-hackathon roadmap (mention in submission, don't build)

- Integration adapters for existing dispatch platforms (so this plugs into an operator's stack rather than replacing it)
- Cross-operator anonymized pattern sharing (e.g., "this apartment complex is known to require call-ahead" learned once, useful to every courier network serving that building — a genuine network-effect moat)
- Predictive risk scoring: flag addresses likely to fail before dispatch, not just after
- Voice-note ingestion at the point of delivery (driver speaks instead of types)
- Freight/dock variant: same architecture applied to warehouse dock appointment intelligence (detention fee reduction)

---

## 6. User Flows (feature-level, no UI mockups needed for hackathon)

**Flow A — Driver logs a note after a delivery**
Delivery marked complete/failed → prompt for a short note (optional but incentivized) → note is ingested into memory, tied to address + driver + timestamp.

**Flow B — Driver receives a briefing before a delivery**
New delivery assigned → system queries memory for that address → returns a synthesized 1–3 line briefing → driver sees it in their app before departure or on arrival.

**Flow C — Ops reviews impact**
Ops opens dashboard → sees addresses with recurring failure patterns → sees what the system has learned and how confidence has changed over time → sees estimated cost impact.

---

## 7. Why Cognee Specifically (the "Best Use of Cognee" argument)

This problem is a poor fit for a plain vector database and a poor fit for a plain relational database — it needs both:

- **Graph structure** captures the real-world relationships that matter: address ↔ unit ↔ customer ↔ driver ↔ note ↔ delivery event. Questions like "has anyone else reported a conflicting fact about this address in the last 30 days" are graph-traversal questions, not similarity questions.
- **Vector similarity** matters for the cold-start problem: an address with zero history still needs a useful answer, drawn from semantically similar situations elsewhere in the graph.
- **improve()/memify is not decorative here** — it's the mechanism that turns "one driver said something once" into "this is now a confirmed operating fact," and the mechanism that ages out stale facts. This is the single most defensible technical differentiator versus a team that just wraps remember/recall around a chatbot.
- **forget() has a real justification** — data retention and customer-privacy purges are a genuine operational requirement for any company handling residential delivery data, not a checkbox.

---

## 8. Tech Stack & Rationale

| Layer | Choice | Rationale |
|---|---|---|
| Memory layer | **Cognee** (self-hosted for hackathon, note Cognee Cloud path for scale prize track) | Sponsor requirement; hybrid graph-vector is the actual right architecture here, not just a mandate |
| Backend/API | **Python + FastAPI** | Cognee's native SDK is Python-first; FastAPI is fast to stand up and demo-friendly |
| Vector store | Cognee's default (or **Qdrant** if you want to show configurability) | Keep default unless you have a specific reason to swap — configuring it is a distraction from the core demo |
| Graph store | Cognee's default (or **Neo4j** if you want a visual graph demo for judges) | Neo4j is worth it *only* if you plan to visually show the graph live — that's a strong demo beat |
| Frontend (driver view) | **Streamlit or a simple React/Next.js app** | Streamlit is faster to build for a hackathon; React/Next.js looks more like a real product if you have time. Pick based on remaining hours, not ambition |
| Frontend (ops dashboard) | Same stack as driver view, second view/page | Don't build a separate app — one app, two views |
| Data for demo | **Synthetic dataset**: a few dozen addresses, simulated multi-driver note history over "time" | You will not have real delivery data — design the seed dataset carefully, it *is* your demo |
| Hosting | Local for build, deploy to something like **Render/Railway/Vercel** only if time allows for a live link | A working local demo video/recording is acceptable and lower-risk than a live deployed app breaking during judging |

**Deliberate non-choices:** no routing/optimization engine, no map integration, no real-time GPS tracking. Those are the crowded, "typical" parts of last-mile AI — this project is explicitly about the memory layer, not the logistics engine. Resist scope creep toward building "yet another dispatch tool."

---

## 9. Implementation Guide (phased, for a multi-day hackathon)

**Phase 1 — Data model & seed data**
Define the entities (address, unit, customer, driver, note, delivery event) and relationships conceptually. Write a synthetic dataset simulating 2–3 weeks of delivery history across ~20–30 addresses, including at least a few addresses with conflicting/aging notes — this is what makes the improve()/forget() demo credible.

**Phase 2 — Core memory loop**
Wire up remember() for note ingestion and recall() for briefing generation. Get this working end-to-end before touching any UI — this is the technical core the judges will probe.

**Phase 3 — Reconciliation & confidence logic**
Implement the improve()/memify step that resolves conflicting notes and assigns confidence levels. This is your strongest differentiation point — budget real time for it, don't leave it for the last hour.

**Phase 4 — Forget/retention logic**
Implement automatic staleness decay and a manual purge action. Small in effort, disproportionately valuable for judging since so few teams will bother with forget() at all.

**Phase 5 — Driver-facing UI**
Build the minimal screen: address in, briefing out. Keep it ruthlessly simple — this should look like a real driver app screen, not an admin tool.

**Phase 6 — Ops dashboard**
Build the second view showing failure-pattern insight and estimated cost impact. This is what makes the "revenue" story land with judges, not just the "impact" story.

**Phase 7 — Narrative & demo prep**
Script a 3-part demo: (1) a driver arriving at an address with zero history gets a similarity-based fallback, (2) a driver arriving at an address with rich, confirmed history gets a precise briefing, (3) ops dashboard showing the aggregate cost-avoidance story. This sequence directly demonstrates all four lifecycle APIs and both buyer-side and user-side value in under 3 minutes.

---

## 10. Business Model (for the pitch, not the build)

- **Model:** B2B SaaS API / per-seat pricing sold to delivery operators, courier networks, and last-mile aggregators (not sold to individual drivers or consumers).
- **Pricing logic:** priced against the cost it displaces — even a modest percentage reduction in failed-first-attempt rate is real, recurring savings for an operator running thousands of deliveries a week, which supports a defensible per-driver or per-delivery fee.
- **Wedge:** regional/mid-market couriers and delivery-network aggregators who feel this cost acutely and don't have the engineering resources to build proprietary infrastructure for it.
- **Moat over time:** the cross-operator pattern-sharing idea in the roadmap (learn once, benefit every courier serving that building) is a genuine network effect — worth one slide in the pitch even though it's not built for the hackathon.

---

## 11. Risks & Open Questions

| Risk | Mitigation |
|---|---|
| Synthetic demo data feels unconvincing to judges | Design it deliberately around a few clear "stories" (a fixed buzzer, a conflicting report, a cold-start address) rather than generic filler |
| Scope creep toward building a full dispatch/routing product | Explicitly exclude routing/maps from the build — state this as a deliberate boundary in the submission, not an omission |
| Cognee lifecycle usage looks superficial if rushed | Prioritize Phase 3 (reconciliation) and Phase 4 (forget) even if it means a simpler UI |
| Judges question real-world data-privacy handling | Have a one-paragraph answer ready: notes are operational (access instructions), not sensitive personal data, and forget() supports retention/purge requirements |

---

## 12. Submission Checklist Mapping (from hackathon resources)

- [ ] Working implementation of remember() **and** recall() (required minimum) — plus improve() and forget() for differentiation
- [ ] Clean GitHub repo with README explaining the problem, not just the code
- [ ] Short demo video following the 3-part narrative in Section 9
- [ ] Documentation explicitly explaining *why* graph+vector hybrid memory is the right architecture for this problem (Section 7 content, condensed)
- [ ] One paragraph on business model/revenue potential in the README — most teams skip this, and it strengthens "Potential Impact" and "Presentation Quality" scoring