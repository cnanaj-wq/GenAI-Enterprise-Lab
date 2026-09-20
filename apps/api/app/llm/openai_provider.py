"""OpenAI Responses API adapter for the AI Ops Investigator."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from apps.api.app.config import settings

# Current STEP 1.6 pricing table in USD per 1M tokens.
# Keep pricing explicit and version-controlled so cost calculations are auditable.
MODEL_PRICING_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    "gpt-5.6-luna": (0.20, 1.20),
    "gpt-5.6-terra": (2.00, 12.00),
    "gpt-5.6-sol": (4.00, 20.00),
    "gpt-5.6": (4.00, 20.00),
}


@dataclass(frozen=True)
class LLMResult:
    text: str
    provider: str
    model: str
    response_id: str | None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float


SYSTEM_INSTRUCTIONS = """You are the AI Ops Investigator for an enterprise data platform.

Your job is to answer the user's operational question using ONLY the evidence
provided in the request.

Rules:
- Never invent an incident, ticket, error code, dependency, date, metric or cause.
- Distinguish the root cause from downstream symptoms.
- Treat RELOAD_ABORTED as a symptom when a more specific upstream error exists.
- If evidence is insufficient, say exactly what is missing.
- Keep the answer concise, operational and suitable for an on-call engineer.
- Respond in French.
- Use these sections:
  1. Diagnostic
  2. Preuves
  3. Impact
  4. Action corrective
  5. Confiance
"""


def _estimate_cost_usd(
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    pricing = MODEL_PRICING_USD_PER_MTOK.get(model)
    if pricing is None:
        return 0.0

    input_rate, output_rate = pricing
    return round(
        (input_tokens / 1_000_000) * input_rate + (output_tokens / 1_000_000) * output_rate,
        8,
    )


def generate_diagnosis(
    *,
    user_prompt: str,
    evidence: dict[str, Any],
) -> LLMResult:
    """Generate a grounded diagnosis from structured operational evidence."""
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is missing. Add it to the project .env file.")

    client = OpenAI(
        api_key=settings.openai_api_key,
        timeout=settings.openai_timeout_seconds,
        max_retries=settings.openai_max_retries,
    )

    model = settings.openai_model

    input_text = (
        "QUESTION UTILISATEUR\n"
        f"{user_prompt}\n\n"
        "EVIDENCE JSON\n"
        f"{json.dumps(evidence, ensure_ascii=False, default=str, indent=2)}"
    )

    response = client.responses.create(
        model=model,
        instructions=SYSTEM_INSTRUCTIONS,
        input=input_text,
        max_output_tokens=settings.openai_max_output_tokens,
    )

    usage = response.usage
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    total_tokens = int(getattr(usage, "total_tokens", 0) or 0)

    return LLMResult(
        text=response.output_text,
        provider="openai",
        model=model,
        response_id=getattr(response, "id", None),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=_estimate_cost_usd(
            model,
            input_tokens,
            output_tokens,
        ),
    )
