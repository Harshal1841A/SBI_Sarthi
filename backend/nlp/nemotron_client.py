"""
NemotronClient — Google Gemma-4-31B-IT via NVIDIA Integrate API.

Uses the official `openai` SDK (OpenAI-compatible endpoint) exactly as shown
in the NVIDIA playground, with async streaming for low-latency responses.

Key design decisions:
- chat()   → collects streaming tokens internally → avoids ReadTimeout on big model
- stream() → yields tokens as they arrive (best for voice/UI)
- Intent classification uses max_tokens=128, no thinking → fast path
- GroqClient alias kept for zero-change backwards compat
"""

import os, json, re, asyncio, structlog
from typing import AsyncGenerator
from openai import AsyncOpenAI
from utils.circuit_breaker import CircuitBreaker

logger = structlog.get_logger()
cb = CircuitBreaker(failure_threshold=5, recovery_timeout=60)

_BASE_URL  = "https://integrate.api.nvidia.com/v1"
_MODEL     = "google/gemma-4-31b-it"
_THINK_RE  = re.compile(r"<think>.*?</think>", re.DOTALL)


def _strip_thinking(text: str) -> str:
    """Remove <think>…</think> reasoning blocks — not shown to users."""
    return _THINK_RE.sub("", text).strip()


def _get_client() -> AsyncOpenAI:
    key = os.environ.get("NIM_API_KEY", "")
    if not key:
        raise ValueError("NIM_API_KEY not configured")
    return AsyncOpenAI(base_url=_BASE_URL, api_key=key, timeout=10.0)


class NemotronClient:
    """
    Async client for NVIDIA Nemotron-3-Ultra-550B.
    Identical interface to the old GroqClient so all callers work unchanged.
    """

    def __init__(self):
        self.model = _MODEL

    # ── Non-streaming: collect stream internally to avoid ReadTimeout ──
    @cb.call
    async def chat(
        self,
        messages: list,
        temperature: float = 1.0,
        max_tokens: int = 512,
        enable_thinking: bool = False,
    ) -> str:
        """
        Returns the full response text (reasoning blocks stripped).
        Internally uses streaming so the 550B model doesn't time out.
        """
        client = _get_client()

        kwargs = dict(
            model=self.model,
            messages=messages,
            temperature=temperature,
            top_p=0.95,
            max_tokens=max_tokens,
            stream=True,
        )
        if enable_thinking:
            kwargs["extra_body"] = {
                "chat_template_kwargs": {"enable_thinking": True},
                "reasoning_budget": min(max_tokens, 16384),
            }

        visible_parts = []
        async with client as c:
            completion = await c.chat.completions.create(**kwargs)
            async for chunk in completion:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                # Skip internal reasoning tokens
                if getattr(delta, "reasoning_content", None):
                    continue
                if delta.content:
                    visible_parts.append(delta.content)

        return _strip_thinking("".join(visible_parts))

    # ── True streaming: yields tokens as they arrive ───────────────
    @cb.call
    async def stream(
        self,
        messages: list,
        enable_thinking: bool = False,
    ) -> AsyncGenerator[str, None]:
        """
        Yield visible content tokens in real-time.
        Reasoning tokens are silently dropped.
        """
        client = _get_client()

        kwargs = dict(
            model=self.model,
            messages=messages,
            temperature=1.0,
            top_p=0.95,
            max_tokens=4096,
            stream=True,
        )
        if enable_thinking:
            kwargs["extra_body"] = {
                "chat_template_kwargs": {"enable_thinking": True},
                "reasoning_budget": 4096,
            }

        async with client as c:
            completion = await c.chat.completions.create(**kwargs)
            async for chunk in completion:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if getattr(delta, "reasoning_content", None):
                    continue
                if delta.content:
                    yield delta.content


# ── Removed alias ──────────────────────────────────
