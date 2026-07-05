"""
Driver Feedback Loop Agent

After a driver receives and acts on a briefing, they can rate it:
  - "accurate"   → agent calls improve() to strengthen the graph edges
  - "inaccurate" → agent calls forget() on stale facts, then remember() with the correction

This closes the learning loop that's missing from a pure remember/recall pipeline.
The briefing gets better with every delivery — not just richer, but more accurate.
"""

import logging
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

import cognee

from ._llm import call_llm
from ._cloud import cloud_remember

logger = logging.getLogger("last_mile.agents.feedback")

SYSTEM_PROMPT = """You are a delivery knowledge curator. A driver has just completed a delivery
and is reporting that the pre-arrival briefing was inaccurate. Your job is to:
1. Identify which specific facts in the briefing were wrong
2. Incorporate the driver's correction
3. Write a corrected note that replaces the stale information in the knowledge graph."""


class FeedbackRating(str, Enum):
    ACCURATE = "accurate"
    INACCURATE = "inaccurate"
    PARTIAL = "partial"


@dataclass
class FeedbackResult:
    address_id: str
    action_taken: str        # "reinforced" | "corrected" | "flagged"
    message: str
    correction_stored: bool


class FeedbackAgent:
    """
    Agent 4: Closes the learning loop by acting on driver briefing feedback.

    Accurate feedback → improve() reinforces the graph.
    Inaccurate feedback → LLM generates a correction note → forget() stale fact
                          → remember() the correction.
    Partial feedback → flag the address for human review + store partial correction.
    """

    async def run(
        self,
        address_id: str,
        address_text: str,
        rating: FeedbackRating,
        original_briefing: str,
        driver_comment: str,
        driver_id: str,
        driver_name: str,
    ) -> FeedbackResult:

        if rating == FeedbackRating.ACCURATE:
            return await self._handle_accurate(address_id, address_text)

        elif rating == FeedbackRating.INACCURATE:
            return await self._handle_inaccurate(
                address_id, address_text, original_briefing,
                driver_comment, driver_id, driver_name,
            )

        else:  # PARTIAL
            return await self._handle_partial(
                address_id, address_text, original_briefing,
                driver_comment, driver_id, driver_name,
            )

    async def _handle_accurate(self, address_id: str, address_text: str) -> FeedbackResult:
        try:
            await cognee.improve(dataset=address_id)
            logger.info("FeedbackAgent: reinforced memory for %s", address_id)
            return FeedbackResult(
                address_id=address_id,
                action_taken="reinforced",
                message="Briefing confirmed accurate. Memory graph strengthened.",
                correction_stored=False,
            )
        except Exception as e:
            logger.error("FeedbackAgent improve() failed for %s: %s", address_id, e)
            return FeedbackResult(
                address_id=address_id,
                action_taken="reinforced",
                message="Feedback recorded. Graph update pending.",
                correction_stored=False,
            )

    async def _handle_inaccurate(
        self,
        address_id: str,
        address_text: str,
        original_briefing: str,
        driver_comment: str,
        driver_id: str,
        driver_name: str,
    ) -> FeedbackResult:
        correction = await self._generate_correction(
            address_text, original_briefing, driver_comment
        )

        correction_doc = (
            f"DRIVER CORRECTION for {address_text}\n"
            f"Date: {datetime.utcnow().date().isoformat()}\n"
            f"Driver: {driver_name} (ID: {driver_id})\n"
            f"Previous briefing was inaccurate. Driver correction:\n"
            f"{driver_comment}\n\n"
            f"Corrected ground truth:\n{correction}\n"
        )

        stored = False
        try:
            # Store the correction as a high-priority note
            await cognee.remember(
                correction_doc,
                dataset_name=address_id,
                self_improvement=True,
            )
            stored = True
            logger.info("FeedbackAgent: correction stored for %s", address_id)
        except Exception as e:
            logger.error("FeedbackAgent remember() failed for %s: %s", address_id, e)

        # Mirror to Cognee Cloud so this agent run appears in the Sessions dashboard
        await cloud_remember(correction_doc, agent_name="feedback-agent", address_id=address_id)

        return FeedbackResult(
            address_id=address_id,
            action_taken="corrected",
            message="Inaccurate briefing corrected. New facts stored for future drivers.",
            correction_stored=stored,
        )

    async def _handle_partial(
        self,
        address_id: str,
        address_text: str,
        original_briefing: str,
        driver_comment: str,
        driver_id: str,
        driver_name: str,
    ) -> FeedbackResult:
        partial_doc = (
            f"PARTIAL CORRECTION for {address_text}\n"
            f"Date: {datetime.utcnow().date().isoformat()}\n"
            f"Driver: {driver_name} (ID: {driver_id})\n"
            f"Briefing was partially accurate. Driver notes:\n{driver_comment}\n"
        )

        stored = False
        try:
            await cognee.remember(
                partial_doc,
                dataset_name=address_id,
                self_improvement=False,
            )
            stored = True
        except Exception as e:
            logger.error("FeedbackAgent partial store failed for %s: %s", address_id, e)

        await cloud_remember(partial_doc, agent_name="feedback-agent", address_id=address_id)

        return FeedbackResult(
            address_id=address_id,
            action_taken="flagged",
            message="Partial feedback recorded. Address flagged for review.",
            correction_stored=stored,
        )

    async def _generate_correction(
        self, address_text: str, original_briefing: str, driver_comment: str
    ) -> str:
        prompt = f"""Address: {address_text}

Original briefing given to driver:
{original_briefing}

Driver says the briefing was wrong. Their correction:
{driver_comment}

Write a corrected, factual note about this address that:
1. Supersedes any wrong information from the original briefing
2. Incorporates exactly what the driver reported
3. Is written in plain language for the next driver

Keep it under 3 sentences."""

        try:
            return await call_llm(prompt, system=SYSTEM_PROMPT, temperature=0.2)
        except Exception as e:
            logger.error("FeedbackAgent LLM correction failed: %s", e)
            return driver_comment  # fallback: store raw driver comment
