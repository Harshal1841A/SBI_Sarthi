import os, httpx, structlog, numpy as np
from utils.circuit_breaker import CircuitBreaker

logger = structlog.get_logger()
cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30)

class ASRClient:
    def __init__(self):
        self.api_key = os.environ.get("NIM_API_KEY", "")
        self.base_url = "https://ai.api.nvidia.com/v1/speech/parakeet-ctc-1.1b-asr"
        self.timeout = 5.0  # 5s per TRD
    
    @cb.call
    async def transcribe(self, audio_bytes: bytes, language: str = "hi") -> dict:
        """Transcribe audio using NVIDIA Parakeet CTC 1.1B."""
        if not self.api_key:
            raise ValueError("NIM_API_KEY not configured")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                self.base_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                files={"audio": ("audio.wav", audio_bytes, "audio/wav")},
                data={"language": language}
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "text": data.get("text", ""),
                "confidence": data.get("confidence", 0.0),
                "language": language,
                "word_timings": data.get("word_timings", [])
            }
