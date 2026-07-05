"""
Cold Start Similarity Agent

When a driver is headed to an address with zero delivery history, this agent
chains multiple Cognee recall() calls to find similar addresses, extracts
patterns from their combined history, and synthesises a useful briefing.

This replaces the single-query fallback in memory.py with a proper multi-step
retrieval chain: search → rank → synthesise → brief.
"""

import logging
from dataclasses import dataclass

import cognee

from ._llm import call_llm

logger = logging.getLogger("last_mile.agents.cold_start")

GLOBAL_DATASET = "last_mile_global"

SYSTEM_PROMPT = """You are a delivery briefing assistant. A driver is about to visit an address
for the first time — there is no prior delivery history for it.
Using patterns from similar addresses, give the driver a practical, specific pre-arrival briefing.
Be concrete. Generic advice wastes a driver's time."""


@dataclass
class ColdStartBriefing:
    briefing: str
    key_facts: list[str]
    similar_patterns_found: int
    source_note: str   # explains where the advice came from


class ColdStartAgent:
    """
    Agent 3: Multi-step retrieval chain for addresses with no delivery history.
    Chains 3 targeted recall() queries against the global dataset, then synthesises
    a briefing from the combined results.
    """

    async def run(self, address_text: str) -> ColdStartBriefing:
        queries = [
            f"access instructions and entry codes for addresses similar to: {address_text}",
            f"common delivery failures and timing issues near: {address_text}",
            f"landmarks, parking, and special notes for deliveries similar to: {address_text}",
        ]

        all_snippets: list[str] = []
        for query in queries:
            snippets = await self._recall(query)
            all_snippets.extend(snippets)

        all_snippets = list(dict.fromkeys(all_snippets))  # deduplicate, preserve order

        if not all_snippets:
            return ColdStartBriefing(
                briefing=(
                    "No prior history for this address and no similar patterns found. "
                    "Attempt buzzer/intercom first. If no answer, leave a card and check "
                    "for a safe-drop location visible from the entrance."
                ),
                key_facts=["No prior history — standard protocol applies"],
                similar_patterns_found=0,
                source_note="Default fallback — global dataset returned no results.",
            )

        context = "\n".join(f"• {s}" for s in all_snippets[:8])

        prompt = f"""A driver is delivering to: {address_text}
This address has no delivery history. Based on patterns from similar addresses:

{context}

Write a practical pre-arrival briefing for the driver. Include:
1. Most likely access method
2. Any timing considerations
3. Where to leave the package if no answer
4. One key watch-out

Then list 3-4 key facts as a JSON array under "key_facts".

Format your response exactly like this:
BRIEFING:
<your briefing here>

KEY_FACTS:
["fact 1", "fact 2", "fact 3"]"""

        raw = await call_llm(prompt, system=SYSTEM_PROMPT, temperature=0.3)
        briefing, key_facts = self._parse_response(raw, all_snippets)

        return ColdStartBriefing(
            briefing=briefing,
            key_facts=key_facts,
            similar_patterns_found=len(all_snippets),
            source_note=f"Derived from {len(all_snippets)} similar delivery patterns in the network.",
        )

    async def _recall(self, query: str) -> list[str]:
        try:
            results = await cognee.recall(query_text=query, datasets=[GLOBAL_DATASET])
            snippets = []
            for r in (results or [])[:3]:
                text = getattr(r, "answer", None) or getattr(r, "text", None) or str(r)
                text = str(text).strip()
                if text and text != "None" and len(text) > 10:
                    snippets.append(text)
            return snippets
        except Exception as e:
            logger.warning("ColdStartAgent recall failed for query '%s': %s", query[:50], e)
            return []

    def _parse_response(self, raw: str, fallback_snippets: list[str]) -> tuple[str, list[str]]:
        import json, re
        briefing = ""
        key_facts = []

        briefing_match = re.search(r"BRIEFING:\s*(.*?)(?=KEY_FACTS:|$)", raw, re.DOTALL)
        if briefing_match:
            briefing = briefing_match.group(1).strip()

        facts_match = re.search(r"KEY_FACTS:\s*(\[.*?\])", raw, re.DOTALL)
        if facts_match:
            try:
                key_facts = json.loads(facts_match.group(1))
            except Exception:
                pass

        if not briefing:
            briefing = (
                "No prior history for this address. Based on similar deliveries in this network:\n"
                + "\n".join(f"• {s}" for s in fallback_snippets[:3])
            )
        if not key_facts:
            key_facts = fallback_snippets[:3]

        return briefing, key_facts
