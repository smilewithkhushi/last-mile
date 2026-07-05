"""
Pre-dispatch Risk Agent

Before a driver is dispatched, this agent analyses the address history and
planned delivery time to produce a risk score and actionable recommendation.

Goes beyond the ops dashboard (which is retrospective) by proactively flagging:
  - Time-of-day failure patterns
  - Unresolved conflicts
  - Stale or low-confidence memory
  - Addresses with persistently high failure rates
"""

import logging
from datetime import datetime, timedelta
from dataclasses import dataclass

import cognee

from ._llm import call_llm

logger = logging.getLogger("last_mile.agents.risk")

SYSTEM_PROMPT = """You are a logistics risk analyst for a last-mile delivery network.
Given an address's delivery history and the planned delivery time, assess the risk of a failed delivery.
Be specific and actionable. Drivers act on your recommendations in real time."""


@dataclass
class RiskAssessment:
    address_id: str
    risk_level: str          # "low" | "medium" | "high" | "critical"
    risk_score: float        # 0.0–1.0
    reasons: list[str]
    recommendation: str
    best_time_window: str    # e.g. "after 17:30" or "any time"
    should_call_ahead: bool


class RiskAgent:
    """
    Agent 2: Assesses pre-dispatch delivery risk using history + LLM reasoning.
    Returns a risk level and concrete driver recommendation before departure.
    """

    def __init__(self, failed_cost: float = 15.0, stale_days: int = 30):
        self.failed_cost = failed_cost
        self.stale_days = stale_days

    async def run(
        self,
        address_id: str,
        address_text: str,
        notes: list[dict],
        planned_hour: int | None = None,
        conflict_flag: int = 0,
    ) -> RiskAssessment:

        if not notes:
            return RiskAssessment(
                address_id=address_id,
                risk_level="medium",
                risk_score=0.5,
                reasons=["No delivery history — cold start address."],
                recommendation="Proceed with standard approach. Note any access details for future drivers.",
                best_time_window="any time",
                should_call_ahead=False,
            )

        stats = self._compute_stats(notes)
        memory_context = await self._recall_context(address_id, address_text)
        notes_block = self._format_recent_notes(notes)

        planned_str = f"{planned_hour:02d}:00" if planned_hour is not None else "unspecified"

        prompt = f"""Address: {address_text}
Planned delivery time: {planned_str}

Delivery statistics:
- Total attempts: {stats['total']}
- Failed: {stats['failed']} ({stats['failure_rate']:.0%} failure rate)
- Unique drivers: {stats['unique_drivers']}
- Most common failure hour: {stats['common_fail_hour'] or 'unknown'}
- Active conflicts flagged: {conflict_flag}
- Memory freshness: {stats['freshness']}

Memory context (from Cognee):
{memory_context}

Recent driver notes:
{notes_block}

Respond with a JSON object in this exact format:
{{
  "risk_level": "low" or "medium" or "high" or "critical",
  "risk_score": 0.0 to 1.0,
  "reasons": ["reason 1", "reason 2"],
  "recommendation": "One concrete sentence telling the driver what to do.",
  "best_time_window": "specific time window or 'any time'",
  "should_call_ahead": true or false
}}"""

        raw = await call_llm(prompt, system=SYSTEM_PROMPT, temperature=0.2)
        assessment = self._parse_assessment(address_id, raw)
        return assessment

    def _compute_stats(self, notes: list[dict]) -> dict:
        total = len(notes)
        failed = sum(1 for n in notes if n.get("status") == "FAILED")
        cutoff = datetime.utcnow() - timedelta(days=self.stale_days)
        recent = [n for n in notes if datetime.fromisoformat(n["timestamp"]) > cutoff]

        fail_hours = []
        for n in notes:
            if n.get("status") == "FAILED":
                try:
                    h = datetime.fromisoformat(n["timestamp"]).hour
                    fail_hours.append(h)
                except Exception:
                    pass

        common_fail_hour = None
        if fail_hours:
            from collections import Counter
            common_fail_hour = f"{Counter(fail_hours).most_common(1)[0][0]:02d}:00"

        freshness = "fresh" if recent else "stale (all notes older than 30 days)"

        return {
            "total": total,
            "failed": failed,
            "failure_rate": failed / total if total else 0,
            "unique_drivers": len(set(n["driver_id"] for n in notes)),
            "common_fail_hour": common_fail_hour,
            "freshness": freshness,
        }

    async def _recall_context(self, address_id: str, address_text: str) -> str:
        try:
            results = await cognee.recall(
                query_text=f"delivery risk and access issues at {address_text}",
                datasets=[address_id],
            )
            if results:
                snippets = []
                for r in results[:3]:
                    text = getattr(r, "answer", None) or getattr(r, "text", None) or str(r)
                    if text and text != "None":
                        snippets.append(str(text).strip())
                return "\n".join(snippets) if snippets else "No specific memory retrieved."
        except Exception as e:
            logger.warning("RiskAgent recall failed for %s: %s", address_id, e)
        return "Memory unavailable."

    def _format_recent_notes(self, notes: list[dict]) -> str:
        recent = sorted(notes, key=lambda n: n["timestamp"], reverse=True)[:5]
        lines = []
        for n in recent:
            ts = n.get("timestamp", "")[:10]
            lines.append(f"[{ts}] {n['driver_name']} ({n['status']}): {n['note_text']}")
        return "\n".join(lines)

    def _parse_assessment(self, address_id: str, raw: str) -> RiskAssessment:
        import json, re
        try:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            data = json.loads(match.group()) if match else {}
            return RiskAssessment(
                address_id=address_id,
                risk_level=data.get("risk_level", "medium"),
                risk_score=float(data.get("risk_score", 0.5)),
                reasons=data.get("reasons", []),
                recommendation=data.get("recommendation", "Proceed with standard approach."),
                best_time_window=data.get("best_time_window", "any time"),
                should_call_ahead=bool(data.get("should_call_ahead", False)),
            )
        except Exception as e:
            logger.warning("RiskAgent parse failed: %s | raw: %s", e, raw[:200])
            return RiskAssessment(
                address_id=address_id,
                risk_level="medium",
                risk_score=0.5,
                reasons=["Could not parse risk assessment."],
                recommendation="Proceed with caution and note any access details.",
                best_time_window="any time",
                should_call_ahead=False,
            )
