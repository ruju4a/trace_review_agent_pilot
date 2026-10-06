from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from openai import OpenAI


def parse_json_best_effort(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return {
                "decision": "PARSE_ERROR",
                "defects": [],
                "explanation": text[:2000],
            }
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {
                "decision": "PARSE_ERROR",
                "defects": [],
                "explanation": text[:2000],
            }


class OpenAIReviewer:
    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.getenv("OPENAI_MODEL")
        if not self.model:
            raise RuntimeError(
                "Set OPENAI_MODEL to a model available to your API account."
            )
        self.client = OpenAI()

    def review(self, prompt: str) -> dict[str, Any]:
        t0 = time.perf_counter()
        response = self.client.responses.create(
            model=self.model,
            input=prompt,
        )
        elapsed = time.perf_counter() - t0

        text = response.output_text
        parsed = parse_json_best_effort(text)
        if not isinstance(parsed, dict) or parsed.get("decision") not in ("APPROVE", "REJECT") or not isinstance(parsed.get("defects"), list) or not all(isinstance(d, str) for d in parsed.get("defects", [])) or not isinstance(parsed.get("explanation"), str):
            parsed = {"decision": "PARSE_ERROR", "defects": [], "explanation": text[:2000]}

        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "input_tokens", None) if usage else None
        output_tokens = getattr(usage, "output_tokens", None) if usage else None

        return {
            **parsed,
            "raw_output": text,
            "elapsed_seconds": elapsed,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "model": self.model,
            "response_id": response.id,
        }
