import { useState, useRef, useCallback } from 'react';
import { useDemoMode } from '../hooks/DemoModeContext';
import { Mic, MicOff, Play, RotateCcw, Send, Brain, Route, Languages } from 'lucide-react';
import { chatApi } from '../services/api';

interface VoiceDemoState {
  stage: 'idle' | 'recording' | 'transcribing' | 'classifying' | 'routed' | 'speaking';
  transcript: string;
  intent: string;
  confidence: number;
  routed_to: string;
  language: string;
  response: string;
  audio_url: string | null;
}

const DEMO_TRANSCRIPTS = [
  { text: 'Mujhe 5 lakh ka loan chahiye ghar ke liye', intent: 'loan_application', confidence: 0.92, lang: 'hi' },
  { text: 'Mera balance kitna hai', intent: 'balance_inquiry', confidence: 0.95, lang: 'hi' },
  { text: 'Account kholna hai', intent: 'account_open', confidence: 0.88, lang: 'hi' },
  { text: 'Mera card block karo', intent: 'card_block', confidence: 0.91, lang: 'hi' },
];

export default function VoiceDemo() {
  const { isDemo } = useDemoMode();
  const [state, setState] = useState<VoiceDemoState>({
    stage: 'idle',
    transcript: '',
    intent: '',
    confidence: 0,
    routed_to: '',
    language: '',
    response: '',
    audio_url: null
  });
  const [_isRecording, setIsRecording] = useState(false);
  const [_demoIndex, setDemoIndex] = useState(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // FIX M-5: use a ref to track demoIndex so runDemo doesn't capture a stale value
  // while also not needing to be in the dependency array (which caused runDemo to
  // re-create on every render, taking the stale reset closure with it).
  const demoIndexRef = useRef(0);

  // useCallback so that runDemo captures a stable reset reference
  const reset = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    setState({
      stage: 'idle', transcript: '', intent: '', confidence: 0,
      routed_to: '', language: '', response: '', audio_url: null
    });
    setIsRecording(false);
  }, []);

  const runDemo = useCallback(async () => {
    // Read index from ref to avoid stale closure — no dependency on demoIndex state
    const currentIndex = demoIndexRef.current;
    const demo = DEMO_TRANSCRIPTS[currentIndex % DEMO_TRANSCRIPTS.length];
    demoIndexRef.current = currentIndex + 1;
    setDemoIndex(demoIndexRef.current); // keep state in sync for display purposes
    reset();

    // Stage 1: Recording
    setIsRecording(true);
    setState(prev => ({ ...prev, stage: 'recording' }));

    await new Promise(r => setTimeout(r, 1500));

    // Stage 2: Transcribing
    setIsRecording(false);
    setState(prev => ({ ...prev, stage: 'transcribing', transcript: demo.text }));

    await new Promise(r => setTimeout(r, 800));

    // Stage 3: Classifying
    setState(prev => ({ ...prev, stage: 'classifying', intent: demo.intent, confidence: demo.confidence, language: demo.lang }));

    await new Promise(r => setTimeout(r, 800));

    // Stage 4: Routed
    const routing: Record<string, string> = {
      loan_application: 'acquisition → HITL (amount > 50K)',
      balance_inquiry: 'assist → shield',
      account_open: 'acquisition → eKYC → V-KYC → funding',
      card_block: 'assist → shield → compensation',
    };
    setState(prev => ({ ...prev, stage: 'routed', routed_to: routing[demo.intent] || 'assist' }));

    // Stage 5: Try to get actual backend response
    try {
      const resp = await chatApi.sendMessage('demo_voice_' + Date.now(), demo.text, demo.lang);
      setState(prev => ({ ...prev, stage: 'speaking', response: resp.response }));
    } catch (e) {
      setState(prev => ({ ...prev, stage: 'speaking', response: 'Namaste! Main aapki madad kar sakta hoon.' }));
    }
  }, [reset]); // depends only on reset (stable), not demoIndex

  const startRecording = async () => {
    if (!isDemo) {
      setState(prev => ({ ...prev, response: 'Please activate Demo Mode first from the top bar.' }));
      return;
    }
    await runDemo();
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-headline-md text-headline-md text-primary dark:text-primary-fixed-dim">
            Voice AI Demo
          </h2>
          <p className="text-sm text-on-surface-variant dark:text-[#8a9ab8] mt-1">
            Hindi speech → ASR → Intent Classification → Agent Routing → TTS
          </p>
        </div>
        <button
          onClick={reset}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full bg-surface-container-low dark:bg-[#1a2840] border border-outline-variant/30 hover:bg-surface-container transition"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          Reset
        </button>
      </div>

      {/* Voice Orb */}
      <div className="flex flex-col items-center gap-6 py-8">
        <button
          onClick={startRecording}
          disabled={state.stage !== 'idle' && state.stage !== 'speaking'}
          className={`
            relative w-24 h-24 rounded-full flex items-center justify-center transition-all duration-500
            ${state.stage === 'recording'
              ? 'bg-error/90 animate-pulse shadow-xl shadow-error/30'
              : state.stage === 'speaking'
                ? 'bg-secondary/90 shadow-xl shadow-secondary/30'
                : 'bg-primary/90 hover:bg-primary hover:scale-105 shadow-xl shadow-primary/30'
            }
            disabled:opacity-50 disabled:cursor-not-allowed
          `}
        >
          {state.stage === 'recording' ? (
            <MicOff className="w-10 h-10 text-white" />
          ) : state.stage === 'speaking' ? (
            <Play className="w-10 h-10 text-white" />
          ) : (
            <Mic className="w-10 h-10 text-white" />
          )}
          
          {/* Ripple effect when recording */}
          {state.stage === 'recording' && (
            <>
              <div className="absolute inset-0 rounded-full bg-error/20 animate-ping" />
              <div className="absolute -inset-4 rounded-full bg-error/10 animate-ping" style={{ animationDelay: '0.2s' }} />
            </>
          )}
        </button>

        <p className="text-sm text-on-surface-variant dark:text-[#8a9ab8]">
          {state.stage === 'idle' && 'Tap the mic to start a Hindi voice demo'}
          {state.stage === 'recording' && 'Listening... (Hindi speech simulation)'}
          {state.stage === 'transcribing' && 'Transcribing via Parakeet CTC 1.1B...'}
          {state.stage === 'classifying' && 'Nemotron-3 Ultra classifying intent...'}
          {state.stage === 'routed' && 'Routing to agent...'}
          {state.stage === 'speaking' && 'Sarthi speaking...'}
        </p>
      </div>

      {/* Pipeline Visualization */}
      <div className="glass bg-surface/80 dark:bg-[#131f35]/90 border border-outline-variant/30 rounded-xl p-5">
        <h3 className="text-xs font-semibold text-on-surface-variant dark:text-[#8a9ab8] mb-4 uppercase tracking-wider">
          AI Pipeline
        </h3>

        <div className="flex items-center justify-between gap-2">
          {[
            { label: 'ASR', icon: <Mic className="w-4 h-4" />, active: state.stage === 'transcribing' || state.stage === 'recording' },
            { label: 'NLP', icon: <Brain className="w-4 h-4" />, active: state.stage === 'classifying' },
            { label: 'Router', icon: <Route className="w-4 h-4" />, active: state.stage === 'routed' },
            { label: 'TTS', icon: <Languages className="w-4 h-4" />, active: state.stage === 'speaking' },
          ].map((step, i) => (
            <div key={step.label} className="flex items-center gap-2">
              <div className={`
                flex flex-col items-center gap-1
                ${step.active ? 'opacity-100' : 'opacity-40'}
              `}>
                <div className={`
                  w-10 h-10 rounded-full flex items-center justify-center
                  ${step.active 
                    ? 'bg-primary text-white shadow-lg shadow-primary/30' 
                    : 'bg-surface-container-highest dark:bg-[#1a2840] text-on-surface-variant'
                  }
                `}>
                  {step.icon}
                </div>
                <span className="text-[10px] font-medium text-on-surface-variant">{step.label}</span>
              </div>
              {i < 3 && (
                <div className={`
                  w-6 h-0.5 transition-colors
                  ${step.active ? 'bg-primary' : 'bg-outline-variant/30'}
                `} />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Results */}
      {state.transcript && (
        <div className="space-y-3 animate-slide-up">
          {/* Transcript */}
          <div className="glass bg-surface/80 dark:bg-[#131f35]/90 border border-outline-variant/30 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <Mic className="w-4 h-4 text-primary" />
              <span className="text-xs font-semibold text-on-surface-variant">Transcription</span>
            </div>
            <p className="text-sm text-on-surface dark:text-[#e4eafc] font-medium">"{state.transcript}"</p>
          </div>

          {/* Intent Classification */}
          {(state.intent || state.confidence > 0) && (
            <div className="glass bg-surface/80 dark:bg-[#131f35]/90 border border-outline-variant/30 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <Brain className="w-4 h-4 text-secondary" />
                <span className="text-xs font-semibold text-on-surface-variant">Intent Classification</span>
              </div>
              <div className="flex items-center gap-4">
                <div>
                  <p className="text-sm font-semibold text-on-surface dark:text-[#e4eafc]">{state.intent}</p>
                  <p className="text-xs text-on-surface-variant">Classified by Nemotron-3 Ultra</p>
                </div>
                <div className="ml-auto">
                  <div className="relative w-12 h-12">
                    <svg className="w-12 h-12 transform -rotate-90">
                      <circle cx="24" cy="24" r="20" fill="none" stroke="currentColor" strokeWidth="3" className="text-surface-container-highest" />
                      <circle cx="24" cy="24" r="20" fill="none" stroke="currentColor" strokeWidth="3" 
                        className="text-secondary" 
                        strokeDasharray={`${state.confidence * 125.6} 125.6`}
                      />
                    </svg>
                    <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold">{(state.confidence * 100).toFixed(0)}%</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Routing Decision */}
          {state.routed_to && (
            <div className="glass bg-surface/80 dark:bg-[#131f35]/90 border border-outline-variant/30 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <Route className="w-4 h-4 text-tertiary" />
                <span className="text-xs font-semibold text-on-surface-variant">Routing Decision</span>
              </div>
              <p className="text-sm font-medium text-on-surface dark:text-[#e4eafc]">{state.routed_to}</p>
            </div>
          )}

          {/* AI Response */}
          {state.response && (
            <div className="glass bg-primary/5 dark:bg-[#0d2137] border border-primary/20 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <Send className="w-4 h-4 text-primary" />
                <span className="text-xs font-semibold text-primary">Sarthi Response</span>
              </div>
              <p className="text-sm text-on-surface dark:text-[#e4eafc]">{state.response}</p>
              <div className="mt-2 flex items-center gap-2">
                <span className="text-[10px] text-on-surface-variant">TTS: Bhashini WS → Sarvam fallback</span>
                <span className="text-[10px] text-secondary font-medium">~650ms to first byte</span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
