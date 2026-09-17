"""Minimal STEP 1.6 OpenAI connectivity test."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from apps.api.app.config import settings
from apps.api.app.llm.openai_provider import generate_diagnosis


def main() -> None:
    print(f"Model: {settings.openai_model}")

    result = generate_diagnosis(
        user_prompt="Quelle est la cause probable du reload ?",
        evidence={
            "application": "Demo_App",
            "reload_id": 123,
            "relevant_logs": [
                {
                    "level": "WARN",
                    "error_code": "NETWORK_TIMEOUT",
                    "message": "Network timeout while reaching remote service",
                },
                {
                    "level": "ERROR",
                    "error_code": "RELOAD_ABORTED",
                    "message": "Reload aborted",
                },
            ],
        },
    )

    print("\nResponse:")
    print(result.text)
    print("\nUsage:")
    print(f"Input tokens : {result.input_tokens}")
    print(f"Output tokens: {result.output_tokens}")
    print(f"Total tokens : {result.total_tokens}")
    print(f"Cost USD     : {result.estimated_cost_usd:.8f}")
    print("\nSTEP 1.6 OpenAI connection test complete.")


if __name__ == "__main__":
    main()
