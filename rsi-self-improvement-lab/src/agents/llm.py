"""Optional real-LLM proposer (any OpenAI-compatible chat-completions endpoint).

No result in this repository's committed experiments uses it: the measured
numbers come from the offline :class:`MutationProposer`. This path exists so the
same harness can be driven by a real model. It fails loudly if credentials or
the SDK are missing, and never falls back to fabricated output.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

import numpy as np

from src.agents.proposer import ImproverConfig
from src.core import candidate as cand
from src.core.candidate import EditRecord, Expr

DEFAULT_MODEL = "gpt-4o-mini"  # any chat model served by the configured endpoint
DEFAULT_BASE_URL = "https://api.openai.com/v1"

PROMPT = """You are improving a greedy TSP construction heuristic.
The function scores each unvisited city (d_cur: distance from the current city, d_start: distance to
the start, d_cent: distance to the centroid of unvisited cities, d_iso: distance to its nearest other
unvisited city, t: fraction of cities left); the highest score is visited next.
Grammar: expr := number | VAR | OP(expr, expr)
VAR in {vars}; OP in {ops} (pdiv is protected division).
Current program: {program}
Reply with ONE modified program on a single line, in exactly that grammar, and nothing else."""


class MissingCredentialsError(RuntimeError):
    pass


class LLMProposer:
    """Asks a hosted model for a modified program. Same interface as MutationProposer.

    Configure with LLM_API_KEY (required), LLM_BASE_URL and LLM_MODEL (optional).
    """

    def __init__(self, model: str | None = None, api_key: str | None = None, base_url: str | None = None) -> None:
        self.model = model or os.environ.get("LLM_MODEL", DEFAULT_MODEL)
        self.base_url = (base_url or os.environ.get("LLM_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
        self.api_key = api_key or os.environ.get("LLM_API_KEY")
        if not self.api_key:
            raise MissingCredentialsError(
                "LLM_API_KEY is not set. Copy .env.example to .env, add a key, and export it, "
                "or use the offline MutationProposer (the default)."
            )

    def propose(self, parent: Expr, rng: np.random.Generator, cfg: ImproverConfig) -> tuple[Expr, EditRecord]:
        del rng, cfg  # the model supplies its own randomness
        prompt = PROMPT.format(vars=list(cand.VARIABLES), ops=list(cand.OPERATORS), program=cand.to_str(parent))
        body = json.dumps({"model": self.model, "max_tokens": 200, "messages": [{"role": "user", "content": prompt}]})
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body.encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as resp:  # noqa: S310 - user-configured endpoint
                text = json.loads(resp.read())["choices"][0]["message"]["content"]
        except (urllib.error.URLError, KeyError, ValueError) as exc:
            raise RuntimeError(f"LLM request failed: {exc}") from exc
        child = parse_reply(text)
        return child, EditRecord("llm_edit", (), cand.diff_features(parent, child), self.model)


def parse_reply(text: str) -> Expr:
    """Parse a model reply; raises ValueError on anything outside the DSL."""
    lines = [ln.strip() for ln in text.strip().strip("`").splitlines() if ln.strip()]
    return cand.parse(lines[0] if lines else "")
