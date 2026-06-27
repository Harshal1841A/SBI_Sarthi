import asyncio
import numpy as np
from typing import Optional, Tuple, Dict, List
from collections import defaultdict
from voice.asr import ASRClient

_asr = ASRClient()

# ────────────────────────────────────────────────────────────────
# Voice Activity Detection (VAD) — Silero VAD Server-Side
# Detects speech start/end in PCM audio streams.
# Latency target: < 50ms per chunk
# ────────────────────────────────────────────────────────────────

# FIX#5: Module-level session buffer dict keyed by session_id
# WebSocket objects have no .session_id attribute
session_buffers: Dict[str, List[float]] = {}

# VAD model placeholder — loaded on first use
_vad_model = None

async def load_vad_model():
    """Lazy-load Silero VAD model."""
    global _vad_model
    if _vad_model is None:
        try:
            from silero_vad import load_silero_vad
            _vad_model = load_silero_vad()
        except ImportError:
            # Fallback: simple energy-based VAD
            _vad_model = "energy_fallback"
    return _vad_model


def _energy_vad(audio_array: np.ndarray, threshold: float = 0.01) -> bool:
    """Simple energy-based VAD fallback when Silero is unavailable."""
    energy = np.sqrt(np.mean(audio_array ** 2))
    return energy > threshold


async def process_audio_chunk(session_id: str, pcm_bytes: bytes) -> Optional[dict]:
    """Process a raw PCM Int16 audio chunk from the browser.
    
    Accumulates into per-session buffer, runs VAD when buffer >= 8000 samples
    (500ms at 16kHz), returns transcript placeholder if speech detected.
    
    Args:
        session_id: Unique session identifier
        pcm_bytes: Raw PCM Int16 audio data
        
    Returns:
        None if buffer accumulating, or dict with transcript if speech detected.
        Format: {"text": str, "needs_repeat": bool, "confidence": float}
    """
    # Convert Int16 PCM to float32 [-1.0, 1.0]
    audio_array = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    
    # FIX#5: Keyed by session_id, not websocket object
    if session_id not in session_buffers:
        session_buffers[session_id] = []
    
    session_buffers[session_id].extend(audio_array.tolist())
    
    # Check if we have enough audio (8000 samples = 500ms at 16kHz)
    if len(session_buffers[session_id]) >= 8000:
        buffer_array = np.array(session_buffers[session_id])
        
        # Run VAD
        vad_model = await load_vad_model()
        
        if vad_model == "energy_fallback":
            speech_detected = _energy_vad(buffer_array)
            confidence = 0.85 if speech_detected else 0.0
        else:
            try:
                from silero_vad import get_speech_timestamps
                speech_timestamps = get_speech_timestamps(
                    buffer_array, vad_model,
                    sampling_rate=16000,
                    threshold=0.5
                )
                speech_detected = len(speech_timestamps) > 0
                confidence = 0.90 if speech_detected else 0.0
            except Exception:
                speech_detected = _energy_vad(buffer_array)
                confidence = 0.80 if speech_detected else 0.0
        
        if speech_detected:
            # Clear buffer for next utterance
            session_buffers[session_id].clear()
            
            try:
                asr_result = await _asr.transcribe(buffer_array.tobytes(), "hi")
                return {
                    "text": asr_result["text"],
                    "needs_repeat": asr_result["confidence"] < 0.7,
                    "confidence": asr_result["confidence"],
                    "audio_buffer": buffer_array.tobytes()
                }
            except Exception as e:
                # Fallback on failure
                return {
                    "text": None,
                    "needs_repeat": True,
                    "confidence": confidence,
                    "audio_buffer": buffer_array.tobytes(),
                    "error": str(e)
                }
        else:
            # No speech detected — trim buffer (keep last 1000 samples for overlap)
            session_buffers[session_id] = session_buffers[session_id][-1000:]
            return None
    
    return None


def cleanup_session_buffer(session_id: str) -> None:
    """Clean up session buffer on disconnect."""
    session_buffers.pop(session_id, None)


def get_active_sessions() -> List[str]:
    """Get list of active voice session IDs."""
    return list(session_buffers.keys())


def get_buffer_size(session_id: str) -> int:
    """Get current buffer size for a session."""
    return len(session_buffers.get(session_id, []))
