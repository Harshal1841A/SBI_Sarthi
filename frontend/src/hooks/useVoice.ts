import { useState, useCallback, useRef, useEffect } from 'react';
import { VoiceSession } from '../types';

const SAMPLE_RATE = 16000;
const CHUNK_SIZE = 160; // AudioWorklet buffer size

// FIX H-7: AudioWorklet processor code (inlined as blob URL).
// ScriptProcessorNode is deprecated and will be removed from Chrome.
// AudioWorkletProcessor runs in a dedicated audio thread — no main-thread jank.
const WORKLET_CODE = `
class PCMCaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buffer = [];
    this._chunkSize = ${CHUNK_SIZE};
  }

  process(inputs) {
    const channel = inputs[0]?.[0];
    if (!channel) return true;

    for (let i = 0; i < channel.length; i++) {
      this._buffer.push(channel[i]);
    }

    while (this._buffer.length >= this._chunkSize) {
      const chunk = this._buffer.splice(0, this._chunkSize);
      const int16 = new Int16Array(this._chunkSize);
      for (let i = 0; i < this._chunkSize; i++) {
        const s = Math.max(-1, Math.min(1, chunk[i]));
        int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }
      // Transfer ownership to avoid copy overhead
      this.port.postMessage(int16.buffer, [int16.buffer]);
    }
    return true; // Keep processor alive
  }
}

registerProcessor('pcm-capture-processor', PCMCaptureProcessor);
`;

function createWorkletURL(): string {
  const blob = new Blob([WORKLET_CODE], { type: 'application/javascript' });
  return URL.createObjectURL(blob);
}

export function useVoice() {
  const [session, setSession] = useState<VoiceSession>({
    session_id: '',
    is_connected: false,
    is_listening: false,
    is_speaking: false
  });
  const [transcript, setTranscript] = useState('');
  // FIX L-4: Don't accumulate audio blobs in state — they are played immediately and GC'd.
  // Keeping an ever-growing Blob[] array exhausts memory in long voice sessions.
  // Expose a simple counter for external components that need to know something was received.
  const [audioChunkCount, setAudioChunkCount] = useState(0);

  const wsRef            = useRef<WebSocket | null>(null);
  const audioContextRef  = useRef<AudioContext | null>(null);
  const workletNodeRef   = useRef<AudioWorkletNode | null>(null);
  const workletUrlRef    = useRef<string | null>(null); // track blob URL for cleanup
  const streamRef        = useRef<MediaStream | null>(null);
  const tokenRef         = useRef<string>(localStorage.getItem('sarthi_token') || '');

  const playAudio = useCallback((blob: Blob) => {
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.onplay = () => {
      setSession(prev => ({ ...prev, is_speaking: true, is_listening: false }));
    };
    audio.onended = () => {
      setSession(prev => ({ ...prev, is_speaking: false, is_listening: true }));
      URL.revokeObjectURL(url); // FIX L-4: revoke immediately after playback
    };
    audio.onerror = () => {
      URL.revokeObjectURL(url);
      setSession(prev => ({ ...prev, is_speaking: false, is_listening: true }));
    };
    audio.play().catch(err => console.error('Audio playback error:', err));
  }, []);

  const startVoiceSession = useCallback(async () => {
    const token = tokenRef.current;
    if (!token) {
      throw new Error('API token not configured');
    }

    // Connect WebSocket
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const wsUrl = `${proto}://${window.location.host}/ws/voice?token=${token}`;
    const ws = new WebSocket(wsUrl);
    ws.binaryType = 'arraybuffer';

    ws.onopen = () => {
      setSession(prev => ({ ...prev, is_connected: true }));
    };

    ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        // Audio response received — play immediately, don't accumulate in state
        const blob = new Blob([event.data], { type: 'audio/wav' });
        setAudioChunkCount(c => c + 1); // lightweight counter, not blob storage
        playAudio(blob);
      } else {
        try {
          const data = JSON.parse(event.data as string);
          if (data.type === 'session_init') {
            setSession(prev => ({
              ...prev,
              session_id: data.session_id,
              is_connected: true
            }));
          } else if (data.type === 'response_meta') {
            setSession(prev => ({
              ...prev,
              is_speaking: false,
              is_listening: true
            }));
          } else if (data.type === 'transcript') {
            setTranscript(data.text || '');
          }
        } catch (e) {
          console.error('Voice WS JSON parse error:', e);
        }
      }
    };

    ws.onclose = () => {
      setSession(prev => ({
        ...prev,
        is_connected: false,
        is_listening: false,
        is_speaking: false
      }));
    };

    ws.onerror = (err) => {
      console.error('Voice WebSocket error:', err);
      setSession(prev => ({ ...prev, is_connected: false }));
    };

    wsRef.current = ws;

    // Initialize audio capture using AudioWorklet (FIX H-7)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: SAMPLE_RATE,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });
      streamRef.current = stream;

      const audioContext = new AudioContext({ sampleRate: SAMPLE_RATE });
      audioContextRef.current = audioContext;

      // Create worklet from inline code as blob URL
      const workletUrl = createWorkletURL();
      workletUrlRef.current = workletUrl;
      await audioContext.audioWorklet.addModule(workletUrl);

      const workletNode = new AudioWorkletNode(audioContext, 'pcm-capture-processor');
      workletNodeRef.current = workletNode;

      // Receive PCM chunks from the worklet thread and send over WS
      workletNode.port.onmessage = (event: MessageEvent<ArrayBuffer>) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(event.data);
        }
      };

      const source = audioContext.createMediaStreamSource(stream);
      source.connect(workletNode);
      // Do NOT connect to destination — prevents echo / feedback loop

      setSession(prev => ({ ...prev, is_listening: true }));
    } catch (err) {
      console.error('Audio capture error:', err);
      throw new Error('Could not access microphone');
    }
  }, [playAudio]);

  const stopVoiceSession = useCallback(() => {
    // Stop AudioWorklet and audio capture
    if (workletNodeRef.current) {
      workletNodeRef.current.port.close();
      workletNodeRef.current.disconnect();
      workletNodeRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    // Revoke worklet blob URL to prevent memory leak
    if (workletUrlRef.current) {
      URL.revokeObjectURL(workletUrlRef.current);
      workletUrlRef.current = null;
    }

    // Close WebSocket
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setSession({
      session_id: '',
      is_connected: false,
      is_listening: false,
      is_speaking: false
    });
    setTranscript('');
    setAudioChunkCount(0);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopVoiceSession();
    };
  }, [stopVoiceSession]);

  return {
    session,
    transcript,
    audioChunkCount, // replaces audioQueue — prevents memory leak
    startVoiceSession,
    stopVoiceSession
  };
}
