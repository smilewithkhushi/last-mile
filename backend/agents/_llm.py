"""Thin wrapper around litellm using the same env config as Cognee."""

import os
import litellm

litellm.suppress_debug_info = True


async def call_llm(prompt: str, system: str = "", temperature: float = 0.3) -> str:
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    api_base = os.getenv("LLM_ENDPOINT") or None
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or "none"

    resp = await litellm.acompletion(
        model=model,
        api_base=api_base,
        api_key=api_key,
        messages=[
            *([ {"role": "system", "content": system}] if system else []),
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
        max_tokens=1024,
    )
    return resp.choices[0].message.content.strip()
