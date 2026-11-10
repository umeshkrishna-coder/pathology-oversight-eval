"""API cost in USD from token counts.

Prices per million tokens, standard (non-batch) rates; Haiku 5.5's rate applies to prompts up to
100,000 tokens, which every drafting prompt is. Checked against
https://platform.claude.com/docs/en/about-claude/pricing on 2026-11-10.
"""

from __future__ import annotations

PRICES: dict[str, dict[str, float]] = {
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50},
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00},
}


def _price(model: str) -> dict[str, float]:
    # The API may return a longer model string; match the longest known prefix.
    matches = [name for name in PRICES if model.startswith(name)]
    if not matches:
        raise ValueError(f"no price for model {model!r}")
    return PRICES[max(matches, key=len)]


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    price = _price(model)
    return (input_tokens * price["input"] + output_tokens * price["output"]) / 1_000_000
