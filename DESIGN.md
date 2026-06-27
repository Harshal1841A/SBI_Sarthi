---
name: Sarthi Premium Fintech
colors:
  surface: '#FFFFFF'
  surface-dim: '#F8F6F3'
  surface-bright: '#FFFFFF'
  surface-container-lowest: '#FFFFFF'
  surface-container-low: '#F8F6F3'
  surface-container: '#F1F5F9'
  surface-container-high: '#E2E8F0'
  surface-container-highest: '#CBD5E1'
  on-surface: '#0A1628'
  on-surface-variant: '#475569'
  inverse-surface: '#111827'
  inverse-on-surface: '#F1F5F9'
  outline: '#E2E8F0'
  outline-variant: '#CBD5E1'
  surface-tint: '#00447C'
  primary: '#00447C'
  on-primary: '#FFFFFF'
  primary-container: '#002B52'
  on-primary-container: '#E0F2FE'
  inverse-primary: '#3B82F6'
  secondary: '#14B8A6'
  on-secondary: '#FFFFFF'
  secondary-container: '#0D9488'
  on-secondary-container: '#CCFBF1'
  tertiary: '#4F46E5'
  on-tertiary: '#FFFFFF'
  tertiary-container: '#4338CA'
  on-tertiary-container: '#E0E7FF'
  error: '#DC2626'
  on-error: '#FFFFFF'
  error-container: '#B91C1C'
  on-error-container: '#FEE2E2'
  primary-fixed: '#DBEAFE'
  primary-fixed-dim: '#93C5FD'
  on-primary-fixed: '#001E3C'
  on-primary-fixed-variant: '#003366'
  secondary-fixed: '#CCFBF1'
  secondary-fixed-dim: '#5EEAD4'
  on-secondary-fixed: '#042F2E'
  on-secondary-fixed-variant: '#115E59'
  tertiary-fixed: '#E0E7FF'
  tertiary-fixed-dim: '#A5B4FC'
  on-tertiary-fixed: '#1E1B4B'
  on-tertiary-fixed-variant: '#312E81'
  background: '#F8F6F3'
  on-background: '#0A1628'
  surface-variant: '#F1F5F9'
typography:
  display-lg:
    fontFamily: Outfit
    fontSize: 56px
    fontWeight: '700'
    lineHeight: '1.1'
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Outfit
    fontSize: 36px
    fontWeight: '600'
    lineHeight: '1.2'
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Outfit
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.3'
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: '1.6'
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.6'
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.6'
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: '1.4'
  label-sm:
    fontFamily: Inter
    fontSize: 10px
    fontWeight: '500'
    lineHeight: '1.4'
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 1rem
  lg: 1.5rem
  xl: 2rem
  full: 9999px
spacing:
  unit: 4px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 48px
  container-max: 1280px
---

## 1. Overview & Creative North Star

**Context:** You are designing a **world-class, premium fintech experience** that communicates "Government-grade trust meets next-generation AI." 

**Design Principles:**
- Premium fintech minimalism (not generic banking)
- Voice-first, AI-first visual language
- Agent orchestration as a central concept
- Light mode (Cream/Surface) and Dark mode readiness
- RBI compliance communicated through UI trust signals
- Purposeful motion design (not decorative)

## 2. Colors: Trust and Intelligence

Our palette is anchored in Trust (SBI Blue & Deep Navy) with accents of AI Intelligence (Indigo & Teal).

*   **Primary (SBI Blue - `#00447C`):** Used for primary structure and trust anchors.
*   **Secondary (Teal - `#14B8A6`):** Represents AI acquisition, health, and positive financial trajectories.
*   **Tertiary (Indigo - `#4F46E5`):** Used for advanced AI features, thinking states, and orchestration mapping.
*   **The Glass Rule:** Primary panels should utilize backdrop blurs (Glassmorphism) over the cream/slate backgrounds to create a layered, multi-dimensional workspace.
*   **Dark Mode Support:** The system gracefully degrades to a `surface-dark` (`#111827`) canvas for night-time or low-light financial monitoring.

## 3. Typography: Editorial Clarity

We use **Outfit** for distinctive headers and **Inter** for dense, readable financial data.

*   **Display & Headlines (Outfit):** Brings a slight geometric, modern tech feel without losing financial seriousness. 
*   **Body & Labels (Inter):** Highly legible. For financial data, ensure tabular lining for numbers so decimals align perfectly.
*   **Contrast:** Ensure WCAG AA compliance across all text layers.

## 4. Elevation & Depth

*   **Shadows:** We use soft, diffused shadows (`0 4px 24px -4px rgba(0, 0, 0, 0.08)`) to lift cards gently off the cream background.
*   **Glows:** For AI agents or active states, use a localized glow (e.g., `#14B8A6` at 15% opacity) to indicate activity or "thinking" states.

## 5. Components

*   **Voice Waveform Orb:** A glowing, undulating orb that reacts to listening/speaking states using Canvas or complex CSS animations.
*   **KYC Wizard:** A clean, horizontal scroll of steps. Current step gets a blue ring; completed steps get a soft green fill.
*   **Compliance Center:** A tabular/card view showing Hash-Chain Integrity and immutable consent logs. Uses monospace fonts for Hash IDs.
*   **Financial Wellness Hub:** A 4-column grid of metrics (Savings, Spending, Goals, Risk) with trend arrows and colored icons.
*   **Buttons:** Generous touch targets (min 48px). Smooth scale-down on active press.

## 6. Do's and Don'ts

### Do
*   Use significant whitespace to reduce cognitive load on complex financial screens.
*   Use Glassmorphism (`backdrop-filter: blur(20px)`) to create depth.
*   Animate state transitions (fade-in, slide-up, checkmark draws).

### Don't
*   Don't use thin, hard-to-tap targets. Everything must be mobile-touch friendly.
*   Don't use generic stock illustrations. Rely on typography, data visualization, and iconography.
*   Don't use jerky animations; ensure all motion uses smooth easing (`cubic-bezier(0.4, 0, 0.2, 1)`).
