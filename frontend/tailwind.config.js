/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // ── Light mode tokens ──────────────────────────────────────
        "background":                "#f4f6fc",
        "on-background":             "#0d1b2e",
        "surface":                   "#f4f6fc",
        "surface-dim":               "#d0d9f0",
        "surface-bright":            "#ffffff",
        "surface-variant":           "#dce5f7",
        "on-surface":                "#0d1b2e",
        "on-surface-variant":        "#44505f",
        "surface-container-lowest":  "#ffffff",
        "surface-container-low":     "#ecf0ff",
        "surface-container":         "#e3eaff",
        "surface-container-high":    "#d7e3fb",
        "surface-container-highest": "#ccd8f5",
        "inverse-surface":           "#1c2b43",
        "inverse-on-surface":        "#e8eeff",
        "inverse-primary":           "#a3c9ff",
        "surface-tint":              "#2d6099",

        // ── Primary ────────────────────────────────────────────────
        "primary":                   "#00447C",
        "on-primary":                "#ffffff",
        "primary-container":         "#d3e6ff",
        "on-primary-container":      "#001d3a",
        "primary-fixed":             "#d3e6ff",
        "primary-fixed-dim":         "#a3c9ff",
        "on-primary-fixed":          "#001c39",
        "on-primary-fixed-variant":  "#094880",

        // ── Secondary (teal) ───────────────────────────────────────
        "secondary":                 "#006b5f",
        "on-secondary":              "#ffffff",
        "secondary-container":       "#80f5e4",
        "on-secondary-container":    "#003731",
        "secondary-fixed":           "#9df9e7",
        "secondary-fixed-dim":       "#4fdbc8",
        "on-secondary-fixed":        "#00201c",
        "on-secondary-fixed-variant":"#005048",

        // ── Tertiary ───────────────────────────────────────────────
        "tertiary":                  "#5651cd",
        "on-tertiary":               "#ffffff",
        "tertiary-container":        "#e2dfff",
        "on-tertiary-container":     "#0e0071",
        "tertiary-fixed":            "#e2dfff",
        "tertiary-fixed-dim":        "#c3c0ff",
        "on-tertiary-fixed":         "#0f0069",
        "on-tertiary-fixed-variant": "#3323cc",

        // ── Error ──────────────────────────────────────────────────
        "error":                     "#DC2626",
        "on-error":                  "#ffffff",
        "error-container":           "#ffdad6",
        "on-error-container":        "#93000a",

        // ── Outline ────────────────────────────────────────────────
        "outline":                   "#727781",
        "outline-variant":           "#c2c6d1",

        // ── Dark mode explicit surface tokens ─────────────────────
        // (used with dark: prefix in components)
        "dark-background":           "#0a0f1e",
        "dark-surface":              "#0f1928",
        "dark-surface-dim":          "#080e1b",
        "dark-surface-container":    "#131f35",
        "dark-surface-container-high":"#1a2840",
        "dark-on-surface":           "#e4eafc",
        "dark-on-surface-variant":   "#b0bcd6",
        "dark-outline":              "#8a95aa",
        "dark-outline-variant":      "#3a4660",
      },
      borderRadius: {
        "DEFAULT": "0.25rem",
        "lg": "0.5rem",
        "xl": "0.75rem",
        "2xl": "1rem",
        "full": "9999px"
      },
      spacing: {
        "margin-desktop": "48px",
        "gutter": "24px",
        "container-max": "1280px",
        "unit": "4px",
        "margin-mobile": "16px"
      },
      fontFamily: {
        "headline-md":       ["Outfit", "sans-serif"],
        "label-sm":          ["Inter", "sans-serif"],
        "headline-lg-mobile":["Outfit", "sans-serif"],
        "body-sm":           ["Inter", "sans-serif"],
        "headline-lg":       ["Outfit", "sans-serif"],
        "body-md":           ["Inter", "sans-serif"],
        "label-md":          ["Inter", "sans-serif"],
        "body-lg":           ["Inter", "sans-serif"],
        "display-lg":        ["Outfit", "sans-serif"]
      },
      fontSize: {
        "headline-md":        ["24px", {"lineHeight": "1.3",  "fontWeight": "600"}],
        "label-sm":           ["10px", {"lineHeight": "1.4",  "fontWeight": "500"}],
        "headline-lg-mobile": ["28px", {"lineHeight": "33.6px","fontWeight": "600"}],
        "body-sm":            ["14px", {"lineHeight": "1.6",  "fontWeight": "400"}],
        "headline-lg":        ["33px", {"lineHeight": "1.2",  "letterSpacing": "-0.01em","fontWeight": "600"}],
        "body-md":            ["16px", {"lineHeight": "1.6",  "fontWeight": "400"}],
        "label-md":           ["12px", {"lineHeight": "1.4",  "fontWeight": "500"}],
        "body-lg":            ["18px", {"lineHeight": "1.6",  "fontWeight": "400"}],
        "display-lg":         ["56px", {"lineHeight": "1.1",  "letterSpacing": "-0.02em","fontWeight": "700"}]
      },
      animation: {
        "fade-in":    "fadeIn 0.2s ease-out",
        "slide-up":   "slideUp 0.3s ease-out",
        "orb-pulse":  "orbPulse 2s ease-in-out infinite",
        "waveform":   "waveform 1.2s ease-in-out infinite",
      },
      keyframes: {
        fadeIn:   { "0%": {opacity: "0", transform: "translateY(4px)"}, "100%": {opacity: "1", transform: "translateY(0)"}},
        slideUp:  { "0%": {opacity: "0", transform: "translateY(16px)"}, "100%": {opacity: "1", transform: "translateY(0)"}},
        orbPulse: { "0%,100%": {opacity: "0.3", transform: "scale(1)"}, "50%": {opacity: "0.6", transform: "scale(1.15)"}},
        waveform: { "0%,100%": {height: "6px"}, "50%": {height: "18px"}},
      }
    },
  },
  plugins: [],
}
