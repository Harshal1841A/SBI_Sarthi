"""
VisionClient — KYC document OCR via NVIDIA NIM vision model.

Uses meta/llama-3.2-11b-vision-instruct on the same NVIDIA endpoint
as Nemotron, so a single NIM_API_KEY covers both LLM + vision.
"""

import os
import json
import re
import structlog
from openai import AsyncOpenAI
from utils.circuit_breaker import CircuitBreaker

logger = structlog.get_logger()
cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30)

_BASE_URL     = "https://integrate.api.nvidia.com/v1"
_VISION_MODEL = "meta/llama-3.2-11b-vision-instruct"


class VisionClient:
    def __init__(self):
        self.api_key = os.environ.get("NIM_API_KEY", "")

    @cb.call
    async def extract_text(self, image_base64: str, doc_type: str) -> dict:
        """
        Extract structured fields from a KYC document image.
        Returns dict with: name, number, dob, address.
        """
        if not self.api_key:
            raise ValueError("NIM_API_KEY not configured for vision")

        prompt = (
            f"You are a KYC document OCR engine for an Indian bank. "
            f"Extract all text from this {doc_type} image. "
            f"Return ONLY valid JSON: "
            f'{{\"name\": null, \"number\": null, \"dob\": null, \"address\": null}}. '
            f"Replace null with extracted value if visible. No extra text outside JSON."
        )

        client = AsyncOpenAI(base_url=_BASE_URL, api_key=self.api_key)

        async with client as c:
            completion = await c.chat.completions.create(
                model=_VISION_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                },
                            },
                        ],
                    }
                ],
                temperature=0.0,
                max_tokens=512,
            )

        raw_text = completion.choices[0].message.content or ""

        json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        return {"raw_text": raw_text, "error": "No structured JSON in response"}
