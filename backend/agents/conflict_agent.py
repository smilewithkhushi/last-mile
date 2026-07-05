"""
Conflict Resolution Agent

Replaces the keyword heuristic in memory.py with genuine LLM reasoning.
Given all recent notes for an address, the agent:
  1. Detects whether a real conflict exists
  2. Reasons which version is most likely current (using recency + driver count)
  3. Writes a resolved ground-truth note back into Cognee via remember()
  4. Returns a structured verdict for the caller
"""

import logging
from datetime import datetime, timedelta
from dataclasses import dataclass

import cognee

from ._llm import call_llm
from ._cloud import cloud_remember

logger = logging.getLogger("last_mile.agents.conflict")

SYSTEM_PROMPT = """You are a delivery-operations analyst reviewing driver notes about a specific address.
Your job is to detect factual conflicts and decide which version reflects current ground truth.
Be concise and practical. Drivers' most recent notes carry more weight than older ones.
Always respond in the exact JSON format requested."""


@dataclass
class ConflictVerdict:
    has_conflict: bool
    conflicting_facts: list[str]
    resolved_truth: str
    reasoning: str
    confidence: str  # "high" | "medium" | "low"


class ConflictResolutionAgent:
    """
    Agent 1: Detects and resolves conflicting driver notes using LLM reasoning.
    Stores the resolution back into Cognee so future recall() sees it.
    """

    def __init__(self, stale_days: int = 30):
        self.stale_days = stale_days

    async def run(self, address_id: str, address_text: str, notes: list[dict]) -> ConflictVerdict:
        if len(notes) < 2:
            return ConflictVerdict(
                has_conflict=False,
                conflicting_facts=[],
                resolved_truth="",
                reasoning="Fewer than 2 notes — no conflict possible.",
                confidence="low",
            )

        cutoff = datetime.utcnow() - timedelta(days=self.stale_days)
        recent = [n for n in notes if datetime.fromisoformat(n["timestamp"]) > cutoff]
        if not recent:
            recent = notes[:6]

        notes_block = self._format_notes(recent)

        prompt = f"""Address: {address_text}

Driver notes (most recent first):
{notes_block}

Analyse these notes and respond with a JSON object in this exact format:
{{
  "has_conflict": true or false,
  "conflicting_facts": ["fact A that was contradicted", "fact B that was contradicted"],
  "resolved_truth": "One paragraph stating what is currently true about this address based on the most recent evidence.",
  "reasoning": "Brief explanation of why you chose this resolution.",
  "confidence": "high" or "medium" or "low"
}}

Only flag a conflict if drivers genuinely disagree about a current fact (e.g. buzzer broken vs fixed).
Ignore conflicts that are clearly time-sequenced improvements (e.g. broken then repaired)."""

        raw = await call_llm(prompt, system=SYSTEM_PROMPT, temperature=0.2)
        verdict = self._parse_verdict(raw)

        if verdict.has_conflict and verdict.resolved_truth:
            await self._store_resolution(address_id, address_text, verdict)

        return verdict

    def _format_notes(self, notes: list[dict]) -> str:
        lines = []
        for n in notes:
            ts = n.get("timestamp", "unknown")[:10]
            lines.append(
                f"[{ts}] Driver {n['driver_name']} ({n['status']}): {n['note_text']}"
            )
        return "\n".join(lines)

    def _parse_verdict(self, raw: str) -> ConflictVerdict:
        import json, re
        try:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            data = json.loads(match.group()) if match else {}
            return ConflictVerdict(
                has_conflict=bool(data.get("has_conflict", False)),
                conflicting_facts=data.get("conflicting_facts", []),
                resolved_truth=data.get("resolved_truth", ""),
                reasoning=data.get("reasoning", ""),
                confidence=data.get("confidence", "low"),
            )
        except Exception as e:
            logger.warning("ConflictAgent parse failed: %s | raw: %s", e, raw[:200])
            return ConflictVerdict(
                has_conflict=False,
                conflicting_facts=[],
                resolved_truth="",
                reasoning="Parse error — could not interpret LLM response.",
                confidence="low",
            )

    async def _store_resolution(self, address_id: str, address_text: str, verdict: ConflictVerdict):
        doc = (
            f"CONFLICT RESOLUTION for {address_text}\n"
            f"Date: {datetime.utcnow().date().isoformat()}\n"
            f"Source: Conflict Resolution Agent\n"
            f"Conflicting facts: {'; '.join(verdict.conflicting_facts)}\n"
            f"Resolved ground truth: {verdict.resolved_truth}\n"
            f"Confidence: {verdict.confidence}\n"
            f"Reasoning: {verdict.reasoning}\n"
        )
        try:
            await cognee.remember(doc, dataset_name=address_id, self_improvement=False)
            logger.info("ConflictAgent stored resolution for %s", address_id)
        except Exception as e:
            logger.error("ConflictAgent failed to store resolution: %s", e)

        # Mirror to Cognee Cloud so this agent run appears in the Sessions dashboard
        await cloud_remember(doc, agent_name="conflict-agent", address_id=address_id)
