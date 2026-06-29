"""
NemotronClient & GemmaClient — Dual-Model Architecture via NVIDIA Integrate API.

Primary: NVIDIA Nemotron-3-Ultra-550B (nvidia/nemotron-3-ultra-550b-a55b)
Fallback / Secondary: Google Gemma-4-31B-IT (google/gemma-4-31b-it) [Replaces Groq]

Uses the official `openai` SDK (OpenAI-compatible endpoint) exactly as shown
in the NVIDIA playground, with async streaming for low-latency responses.
"""

import os, json, re, asyncio, structlog
from typing import AsyncGenerator
from openai import AsyncOpenAI
from utils.circuit_breaker import CircuitBreaker

logger = structlog.get_logger()
cb_nemotron = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
cb_gemma = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
cb_nemotron_stream = CircuitBreaker(failure_threshold=3, recovery_timeout=60)  # FIX C4: separate CB for streaming path

_BASE_URL       = "https://integrate.api.nvidia.com/v1"
_NEMOTRON_MODEL = "nvidia/nemotron-3-ultra-550b-a55b"
_GEMMA_MODEL    = "google/gemma-4-31b-it"
_THINK_RE       = re.compile(r"<think>.*?</think>", re.DOTALL)


def _strip_thinking(text: str) -> str:
    """Remove <think>…</think> reasoning blocks — not shown to users."""
    return _THINK_RE.sub("", text).strip()


def _get_client() -> AsyncOpenAI:
    key = os.environ.get("NIM_API_KEY", "")
    if not key:
        raise ValueError("NIM_API_KEY not configured")
    return AsyncOpenAI(base_url=_BASE_URL, api_key=key, timeout=12.0)


class GemmaClient:
    """
    Async client for Google Gemma-4-31B-IT via NVIDIA NIM.
    Acts as the high-speed secondary / fallback model (replacing Groq).
    """
    def __init__(self):
        self.model = _GEMMA_MODEL

    @cb_gemma.call
    async def chat(
        self,
        messages: list,
        temperature: float = 1.0,
        max_tokens: int = 512,
        enable_thinking: bool = False,
    ) -> str:
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
                if getattr(delta, "reasoning_content", None):
                    continue
                if delta.content:
                    visible_parts.append(delta.content)

        return _strip_thinking("".join(visible_parts))


class NemotronClient:
    """
    Primary async client for NVIDIA Nemotron-3-Ultra-550B.
    Automatically falls back to GemmaClient (Gemma-4-31B-IT) if Nemotron fails or times out.
    """
    def __init__(self):
        self.model = _NEMOTRON_MODEL
        self.gemma_fallback = GemmaClient()

    async def chat(
        self,
        messages: list,
        temperature: float = 1.0,
        max_tokens: int = 512,
        enable_thinking: bool = False,
    ) -> str:
        """
        Attempts execution on Nemotron-3-Ultra-550B. If an error occurs,
        seamlessly falls back to Gemma-4-31B-IT.
        """
        try:
            return await self._nemotron_chat(messages, temperature, max_tokens, enable_thinking)
        except Exception as e:
            logger.warning("Nemotron chat failed, falling back to Gemma-4-31B-IT", error=str(e))
            return await self.gemma_fallback.chat(messages, temperature, max_tokens, enable_thinking)

    @cb_nemotron.call
    async def _nemotron_chat(
        self,
        messages: list,
        temperature: float = 1.0,
        max_tokens: int = 512,
        enable_thinking: bool = False,
    ) -> str:
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
                if getattr(delta, "reasoning_content", None):
                    continue
                if delta.content:
                    visible_parts.append(delta.content)

        return _strip_thinking("".join(visible_parts))

    @cb_nemotron_stream.call
    async def stream(
        self,
        messages: list,
        enable_thinking: bool = False,
    ) -> AsyncGenerator[str, None]:
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
