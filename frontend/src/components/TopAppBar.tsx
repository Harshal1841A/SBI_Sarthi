import React from 'react';
import { useTheme } from '../hooks/ThemeContext';

export const TopAppBar: React.FC = () => {
  const { theme, toggleTheme } = useTheme();

  return (
    <header
      className="fixed top-0 w-full z-50 flex justify-between items-center px-4 h-16 border-b glass"
      style={{
        background: theme === 'dark'
          ? 'rgba(15, 25, 40, 0.92)'
          : 'rgba(244, 246, 252, 0.88)',
        borderColor: theme === 'dark'
          ? 'rgba(58, 70, 96, 0.4)'
          : 'rgba(194, 198, 209, 0.4)',
      }}
    >
      {/* Brand */}
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-full bg-primary flex items-center justify-center shadow-md">
          <span className="text-white font-bold text-sm select-none">S</span>
        </div>
        <div>
          <h1
            className="font-headline-md text-[18px] font-bold tracking-tight leading-none"
            style={{ color: theme === 'dark' ? '#a3c9ff' : '#00447C' }}
          >
            SARTHI
          </h1>
          <p className="text-[10px] font-medium tracking-widest"
            style={{ color: theme === 'dark' ? '#4fdbc8' : '#006b5f' }}>
            SBI AI BANKING
          </p>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1">
        {/* Theme toggle */}
        <button
          id="theme-toggle-btn"
          onClick={toggleTheme}
          title={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
          className="w-9 h-9 flex items-center justify-center rounded-full transition-colors duration-200 active:scale-95"
          style={{
            color: theme === 'dark' ? '#a3c9ff' : '#00447C',
            background: 'transparent',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = theme === 'dark' ? 'rgba(163,201,255,0.1)' : 'rgba(0,68,124,0.08)')}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
        >
          <span className="material-symbols-outlined text-[22px]">
            {theme === 'light' ? 'dark_mode' : 'light_mode'}
          </span>
        </button>

        {/* Trust badge */}
        <button
          id="trust-badge-btn"
          className="w-9 h-9 flex items-center justify-center rounded-full transition-colors duration-200 active:scale-95"
          style={{ color: theme === 'dark' ? '#4fdbc8' : '#006b5f' }}
          title="RBI Compliance Verified"
        >
          <span className="material-symbols-outlined text-[22px]" style={{ fontVariationSettings: "'FILL' 1" }}>
            verified_user
          </span>
        </button>
      </div>
    </header>
  );
};
