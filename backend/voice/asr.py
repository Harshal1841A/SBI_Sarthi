import os
import base64
import httpx
import structlog
from utils.circuit_breaker import CircuitBreaker

logger = structlog.get_logger()
cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30)

class ASRClient:
    def __init__(self):
        self.api_key = os.environ.get("BHASHINI_API_KEY", "") or os.environ.get("NIM_API_KEY", "")
        self.base_url = "https://dhruva-api.bhashini.gov.in/services/inference/asr"
        self.parakeet_rnnt_url = "https://ai.api.nvidia.com/v1/speech/parakeet-rnnt-1.1b-asr"
        self.timeout = 5.0  # 5s per TRD
    
    @cb.call
    async def transcribe(self, audio_bytes: bytes, language: str = "hi") -> dict:
        """Transcribe audio using Bhashini ASR API (primary) or NVIDIA Parakeet RNNT 1.1B (fallback)."""
        bhashini_key = os.environ.get("BHASHINI_API_KEY", "")
        if bhashini_key:
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(
                        self.base_url,
                        headers={"Authorization": bhashini_key},
                        json={
                            "audioContent": base64.b64encode(audio_bytes).decode(),
                            "config": {"language": {"sourceLanguage": language}}
                        }
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    return {
                        "text": data.get("output", [{}])[0].get("source", ""),
                        "confidence": 0.90,
                        "language": language,
                        "word_timings": []
                    }
            except Exception as e:
                logger.warning("bhashini_asr_failed", error=str(e), fallback="parakeet_rnnt")
        
        nim_key = os.environ.get("NIM_API_KEY", "")
        if not nim_key:
            raise ValueError("Neither BHASHINI_API_KEY nor NIM_API_KEY configured")
            
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                self.parakeet_rnnt_url,
                headers={"Authorization": f"Bearer {nim_key}"},
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

