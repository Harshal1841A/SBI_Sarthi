import React from 'react';
import { useVoice } from '../hooks/useVoice';

export const VoiceWaveformOrb: React.FC = () => {
  const { session, startVoiceSession, stopVoiceSession } = useVoice();

  const isActive   = session.is_connected && session.is_listening;
  const isSpeaking = session.is_speaking;

  const handleToggle = async () => {
    if (session.is_connected) {
      stopVoiceSession();
    } else {
      try {
        await startVoiceSession();
      } catch (err: any) {
        console.error('Voice session error:', err.message);
      }
    }
  };

  const label = isSpeaking
    ? 'Sarthi is speaking…'
    : isActive
    ? 'Listening…'
    : session.is_connected
    ? 'Processing…'
    : 'Tap to Ask Sarthi';

  /* waveform speed: fast when active/speaking, slow when idle */
  const barDuration = isActive || isSpeaking ? '0.45s' : '1.4s';

  return (
    <div className="fixed bottom-24 right-6 z-40 flex flex-col items-center">
      <div className="relative w-20 h-20 flex items-center justify-center">
        {/* Outer glow — pulses when connected */}
        <div
          className={`absolute inset-0 rounded-full blur-xl transition-opacity duration-500 ${
            session.is_connected ? 'opacity-40 orb-glow' : 'opacity-10'
          }`}
          style={{ background: 'radial-gradient(circle, #14B8A6, #00447C)' }}
        />

        {/* Spinning ring — only while connected */}
        {session.is_connected && (
          <div
            className="absolute inset-2 rounded-full border border-teal-400/40 animate-spin"
            style={{ animationDuration: '6s' }}
          />
        )}

        {/* Center button */}
        <button
          id="voice-orb-btn"
          onClick={handleToggle}
          aria-label={label}
          className={`relative w-14 h-14 rounded-full shadow-lg flex items-center justify-center
            border-2 transition-all duration-200 active:scale-90
            ${session.is_connected
              ? 'bg-primary border-primary-fixed-dim shadow-primary/30'
              : 'bg-white dark:bg-[#131f35] border-outline-variant/40 dark:border-[#2a3a55]'
            }`}
        >
          {/* Waveform bars */}
          <div className="flex gap-0.5 items-end h-5">
            {[0.1, 0.3, 0.2, 0.4, 0.15].map((delay, i) => (
              <div
                key={i}
                className="waveform-bar"
                style={{
                  animationDelay: `${delay}s`,
                  animationDuration: barDuration,
                  background: session.is_connected ? '#ffffff' : '#14B8A6',
                }}
              />
            ))}
          </div>
        </button>
      </div>

      {/* Label */}
      <p className={`text-label-md font-semibold mt-2 transition-opacity duration-300 ${
        session.is_connected ? 'opacity-100 text-primary dark:text-primary-fixed-dim' : 'opacity-60 text-on-surface-variant dark:text-outline-variant'
      }`}>
        {label}
      </p>

      {/* Status dot */}
      {session.is_connected && (
        <div className="flex items-center gap-1 mt-0.5">
          <div className={`w-1.5 h-1.5 rounded-full ${isSpeaking ? 'bg-secondary animate-pulse' : 'bg-teal-400 animate-pulse'}`} />
          <span className="text-[10px] font-medium text-on-surface-variant dark:text-outline-variant">
            {isSpeaking ? 'SPEAKING' : 'LIVE'}
          </span>
        </div>
      )}
    </div>
  );
};
