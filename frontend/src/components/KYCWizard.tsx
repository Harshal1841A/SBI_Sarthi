import React, { useRef, useState } from 'react';
import { useTheme } from '../hooks/ThemeContext';
import { kycApi } from '../services/api';

const STEPS = ['Aadhaar Link', 'Identity Verify', 'Account Active'];

export const KYCWizard: React.FC = () => {
  const { theme } = useTheme();
  const dark = theme === 'dark';
  const [step, setStep] = useState(1);        // 0-indexed, current step done
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const progress = Math.round(((step + 1) / STEPS.length) * 100);
  const circumference = 2 * Math.PI * 20; // r=20
  const dashOffset = circumference * (1 - progress / 100);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    setUploadResult(null);
    try {
      const result = await kycApi.uploadDocument(file, 'demo_user', 'aadhaar');
      setUploadResult(`✓ ${result.validation_status} — ${result.doc_type} processed`);
      setStep(Math.min(step + 1, STEPS.length - 1));
    } catch (err: any) {
      setError('Upload failed — backend may be offline.');
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  return (
    <section
      className="glass rounded-xl p-5 shadow-sm"
      style={{
        background: dark ? 'rgba(19,31,53,0.88)' : 'rgba(255,255,255,0.8)',
        border: `1px solid ${dark ? 'rgba(42,58,85,0.6)' : 'rgba(194,198,209,0.35)'}`,
      }}
    >
      {/* Header row */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-headline-md text-body-lg font-semibold" style={{ color: dark ? '#a3c9ff' : '#00447C' }}>
            KYC Verification
          </h3>
          <p className="font-label-md text-label-md" style={{ color: dark ? '#b0bcd6' : '#44505f' }}>
            Step {step + 1} of {STEPS.length}: {STEPS[step]}
          </p>
        </div>

        {/* Progress ring */}
        <div className="relative w-12 h-12 flex items-center justify-center">
          <svg className="w-full h-full transform -rotate-90" viewBox="0 0 48 48">
            <circle cx="24" cy="24" fill="transparent" r="20" stroke={dark ? '#1a2840' : '#e3eaff'} strokeWidth="4" />
            <circle
              cx="24" cy="24" fill="transparent" r="20"
              stroke={dark ? '#a3c9ff' : '#00447C'}
              strokeWidth="4"
              strokeDasharray={circumference}
              strokeDashoffset={dashOffset}
              strokeLinecap="round"
              style={{ transition: 'stroke-dashoffset 0.4s ease' }}
            />
          </svg>
          <span className="absolute font-label-sm text-[10px] font-bold" style={{ color: dark ? '#a3c9ff' : '#00447C' }}>
            {progress}%
          </span>
        </div>
      </div>

      {/* Step pills */}
      <div className="flex gap-2 mb-4 overflow-x-auto pb-1">
        {STEPS.map((s, i) => (
          <div
            key={s}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold whitespace-nowrap"
            style={{
              background: i <= step
                ? (dark ? 'rgba(0,68,124,0.4)' : '#d3e6ff')
                : (dark ? 'rgba(255,255,255,0.05)' : '#f0f3ff'),
              color: i <= step
                ? (dark ? '#a3c9ff' : '#00447C')
                : (dark ? '#6a7a98' : '#aab3c8'),
            }}
          >
            <span className="material-symbols-outlined text-[14px]" style={{ fontVariationSettings: "'FILL' 1" }}>
              {i < step ? 'check_circle' : i === step ? 'radio_button_checked' : 'radio_button_unchecked'}
            </span>
            {s}
          </div>
        ))}
      </div>

      {/* Result/error feedback */}
      {uploadResult && (
        <div className="mb-3 text-xs px-3 py-2 rounded-lg animate-fade-in"
          style={{ background: dark ? 'rgba(20,184,166,0.15)' : '#f0fdf4', color: dark ? '#4fdbc8' : '#15803d', border: '1px solid rgba(20,184,166,0.3)' }}>
          {uploadResult}
        </div>
      )}
      {error && (
        <div className="mb-3 text-xs px-3 py-2 rounded-lg animate-fade-in"
          style={{ background: dark ? 'rgba(220,38,38,0.1)' : '#fef2f2', color: '#DC2626', border: '1px solid rgba(220,38,38,0.25)' }}>
          {error}
        </div>
      )}

      {/* Upload / CTA button */}
      <input
        ref={fileRef}
        type="file"
        accept="image/*,application/pdf"
        className="hidden"
        onChange={handleUpload}
        id="kyc-file-input"
      />
      <button
        id="kyc-upload-btn"
        onClick={() => fileRef.current?.click()}
        disabled={uploading || step >= STEPS.length - 1}
        className="w-full py-3 rounded-lg flex items-center justify-center gap-2 font-label-md font-semibold transition-all active:scale-[0.98] disabled:opacity-60"
        style={{
          background: step >= STEPS.length - 1
            ? (dark ? '#1a2840' : '#e3eaff')
            : (dark ? '#a3c9ff' : '#00447C'),
          color: step >= STEPS.length - 1
            ? (dark ? '#6a7a98' : '#a0aab8')
            : '#ffffff',
        }}
      >
        {uploading ? (
          <><span className="material-symbols-outlined text-[18px] animate-spin">progress_activity</span> Uploading…</>
        ) : step >= STEPS.length - 1 ? (
          <><span className="material-symbols-outlined text-[18px]" style={{ fontVariationSettings: "'FILL' 1" }}>check_circle</span> KYC Complete</>
        ) : (
          <><span className="material-symbols-outlined text-[18px]">upload_file</span> Upload & Continue</>
        )}
      </button>
    </section>
  );
};
