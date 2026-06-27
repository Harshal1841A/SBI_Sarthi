import { useState, useEffect } from 'react';
import { useDemoMode } from '../hooks/DemoModeContext';
import { OnboardingStep } from '../types';
import { 
  CreditCard, FileCheck, Shield, Video, 
  Banknote, UserCheck, Fingerprint, ChevronRight, Lock
} from 'lucide-react';

const ONBOARDING_STEPS: OnboardingStep[] = [
  {
    id: 'create_profile',
    label: 'Profile Created',
    description: 'Sarthi initializes the session and creates a new customer profile.',
    status: 'completed',
    icon: 'user',
    agent: 'acquisition'
  },
  {
    id: 'collect_aadhaar',
    label: 'Aadhaar Verification',
    description: 'User provides 12-digit Aadhaar. Verhoeff checksum validates format.',
    status: 'completed',
    icon: 'fingerprint',
    agent: 'acquisition'
  },
  {
    id: 'collect_pan',
    label: 'PAN Collection',
    description: 'User provides PAN number. Format validated via regex.',
    status: 'active',
    icon: 'credit_card',
    agent: 'acquisition'
  },
  {
    id: 'e_kyc',
    label: 'e-KYC Validation',
    description: 'Document upload + OCR (Claude Vision). Face match against Aadhaar.',
    status: 'pending',
    icon: 'file_check',
    agent: 'acquisition'
  },
  {
    id: 'consent_collection',
    label: 'DPDP Consent',
    description: '4 granular consents: onboarding, analytics, marketing, credit bureau.',
    status: 'pending',
    icon: 'shield',
    agent: 'acquisition'
  },
  {
    id: 'v_kyc',
    label: 'Video KYC (V-KYC)',
    description: 'Live video interview with RBI-authorized officer.',
    status: 'pending',
    icon: 'video',
    agent: 'hitl_pause'
  },
  {
    id: 'fund_account',
    label: 'Account Funding',
    description: 'Initial deposit via UPI / IMPS / NEFT. Account activated.',
    status: 'pending',
    icon: 'banknote',
    agent: 'acquisition'
  }
];

const ICON_MAP: Record<string, React.ReactNode> = {
  user: <UserCheck className="w-5 h-5" />,
  fingerprint: <Fingerprint className="w-5 h-5" />,
  credit_card: <CreditCard className="w-5 h-5" />,
  file_check: <FileCheck className="w-5 h-5" />,
  shield: <Shield className="w-5 h-5" />,
  video: <Video className="w-5 h-5" />,
  banknote: <Banknote className="w-5 h-5" />,
};

export default function LoanWorkflow() {
  const { isDemo } = useDemoMode();
  const [steps, setSteps] = useState<OnboardingStep[]>(ONBOARDING_STEPS);
  const [activeIndex, setActiveIndex] = useState(2);
  const [isAnimating, setIsAnimating] = useState(false);

  // Simulate progression when in demo mode
  useEffect(() => {
    if (!isDemo) return;
    const interval = setInterval(() => {
      setActiveIndex(prev => {
        if (prev >= steps.length - 1) return 2; // Reset for loop
        return prev + 1;
      });
    }, 3000);
    return () => clearInterval(interval);
  }, [isDemo, steps.length]);

  useEffect(() => {
    setSteps(prev => prev.map((step, idx) => ({
      ...step,
      status: idx < activeIndex ? 'completed' : idx === activeIndex ? 'active' : 'pending' as any
    })));
  }, [activeIndex]);

  const handleStepClick = (index: number) => {
    setIsAnimating(true);
    setActiveIndex(index);
    setTimeout(() => setIsAnimating(false), 500);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-headline-md text-headline-md text-primary dark:text-primary-fixed-dim">
            Onboarding Workflow
          </h2>
          <p className="text-sm text-on-surface-variant dark:text-[#8a9ab8] mt-1">
            Visual state machine: Aadhaar → PAN → eKYC → Consent → V-KYC → Funding
          </p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-secondary/10 text-secondary text-xs font-medium">
          <Lock className="w-3.5 h-3.5" />
          RBI KYC Norms Compliant
        </div>
      </div>

      {/* Progress Bar */}
      <div className="relative h-2 bg-surface-container-highest dark:bg-[#1a2840] rounded-full overflow-hidden">
        <div 
          className="absolute top-0 left-0 h-full bg-gradient-to-r from-primary to-secondary rounded-full transition-all duration-1000 ease-out"
          style={{ width: `${((activeIndex + 1) / steps.length) * 100}%` }}
        />
      </div>

      {/* Steps */}
      <div className="space-y-3">
        {steps.map((step, index) => {
          const isActive = index === activeIndex;
          const isCompleted = index < activeIndex;
          // isPending = index > activeIndex (expressed by the else branch below)

          return (
            <div
              key={step.id}
              onClick={() => handleStepClick(index)}
              className={`
                relative flex items-start gap-4 p-4 rounded-xl border transition-all duration-300 cursor-pointer
                ${isActive 
                  ? 'bg-primary/5 dark:bg-[#0d2137] border-primary/30 dark:border-[#00447C]/40 shadow-lg shadow-primary/5' 
                  : isCompleted
                    ? 'bg-surface dark:bg-[#131f35]/80 border-outline-variant/30 dark:border-[#2a3a55]/40 opacity-75'
                    : 'bg-surface/50 dark:bg-[#131f35]/40 border-outline-variant/20 dark:border-[#2a3a55]/30'
                }
                ${isAnimating && isActive ? 'animate-pulse' : ''}
              `}
            >
              {/* Step Number / Status */}
              <div className={`
                flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center
                ${isActive 
                  ? 'bg-primary text-white' 
                  : isCompleted 
                    ? 'bg-secondary/20 text-secondary' 
                    : 'bg-surface-container-highest dark:bg-[#1a2840] text-on-surface-variant'
                }
              `}>
                {isCompleted ? (
                  <FileCheck className="w-5 h-5" />
                ) : (
                  ICON_MAP[step.icon] || <ChevronRight className="w-5 h-5" />
                )}
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between mb-1">
                  <h3 className={`
                    font-semibold text-sm
                    ${isActive ? 'text-primary dark:text-primary-fixed-dim' : 'text-on-surface dark:text-[#e4eafc]'}
                  `}>
                    {step.label}
                  </h3>
                  <span className={`
                    text-[10px] font-medium px-2 py-0.5 rounded-full
                    ${isActive 
                      ? 'bg-primary/10 text-primary' 
                      : isCompleted 
                        ? 'bg-secondary/10 text-secondary' 
                        : 'bg-surface-container text-on-surface-variant'
                    }
                  `}>
                    {isActive ? 'ACTIVE' : isCompleted ? 'DONE' : 'PENDING'}
                  </span>
                </div>
                <p className="text-xs text-on-surface-variant dark:text-[#8a9ab8] leading-relaxed">
                  {step.description}
                </p>
                <div className="flex items-center gap-2 mt-2">
                  <span className="text-[10px] text-on-surface-variant dark:text-[#8a9ab8]">
                    Agent: <span className="font-medium text-primary dark:text-primary-fixed-dim">{step.agent}</span>
                  </span>
                  {step.id === 'v_kyc' && (
                    <span className="text-[10px] text-amber-500 font-medium">
                      HITL Breakpoint
                    </span>
                  )}
                  {step.id === 'consent_collection' && (
                    <span className="text-[10px] text-tertiary font-medium">
                      DPDP 2023
                    </span>
                  )}
                </div>
              </div>

              {/* Arrow */}
              <div className="flex-shrink-0 self-center">
                <ChevronRight className={`
                  w-4 h-4 transition-transform
                  ${isActive ? 'text-primary rotate-90' : 'text-on-surface-variant'}
                `} />
              </div>
            </div>
          );
        })}
      </div>

      {/* Agent Legend */}
      <div className="glass bg-surface/80 dark:bg-[#131f35]/90 border border-outline-variant/30 rounded-xl p-4">
        <h4 className="text-xs font-semibold text-on-surface-variant dark:text-[#8a9ab8] mb-3 uppercase tracking-wider">
          Agent Routing Legend
        </h4>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-primary" />
            <span>acquisition — Onboarding & KYC</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-amber-500" />
            <span>hitl_pause — Human approval</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-secondary" />
            <span>adoption — Cross-sell</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-tertiary" />
            <span>shield — Security audit</span>
          </div>
        </div>
      </div>
    </div>
  );
}
