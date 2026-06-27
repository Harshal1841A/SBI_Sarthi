import React from 'react';
import { useTheme } from '../hooks/ThemeContext';

type NavTab = 'home' | 'assistant' | 'supervisor' | 'security' | 'workflow' | 'voice' | 'audit';

interface BottomNavBarProps {
  activeTab: NavTab;
  onTabChange: (tab: NavTab) => void;
}

const NAV_ITEMS: { id: NavTab; icon: string; label: string }[] = [
  { id: 'home',       icon: 'account_balance_wallet', label: 'Wealth' },
  { id: 'assistant',  icon: 'graphic_eq',             label: 'Assistant' },
  { id: 'workflow',   icon: 'account_tree',           label: 'Workflow' },
  { id: 'voice',      icon: 'mic',                    label: 'Voice' },
  { id: 'supervisor', icon: 'fact_check',             label: 'Supervisor' },
  { id: 'audit',      icon: 'receipt_long',           label: 'Audit' },
  { id: 'security',   icon: 'shield',                 label: 'Security' },
];

export const BottomNavBar: React.FC<BottomNavBarProps> = ({ activeTab, onTabChange }) => {
  const { theme } = useTheme();
  const dark = theme === 'dark';

  return (
    <nav
      className="fixed bottom-0 left-0 w-full flex justify-around items-center px-4 pb-4 pt-2 glass border-t z-50 shadow-2xl"
      style={{
        background: dark ? 'rgba(10,15,30,0.96)' : 'rgba(244,246,252,0.95)',
        borderColor: dark ? 'rgba(42,58,85,0.5)' : 'rgba(194,198,209,0.4)',
      }}
    >
      {NAV_ITEMS.map((item) => {
        const isActive = activeTab === item.id;
        return (
          <button
            key={item.id}
            id={`nav-${item.id}`}
            onClick={() => onTabChange(item.id)}
            className="flex flex-col items-center justify-center gap-0.5 px-3 py-1.5 rounded-xl transition-all duration-200 active:scale-90"
            style={{
              background: isActive ? '#00447C' : 'transparent',
              color: isActive
                ? '#ffffff'
                : (dark ? '#8a9ab8' : '#44505f'),
              opacity: isActive ? 1 : 0.75,
              boxShadow: isActive ? '0 2px 8px rgba(0,68,124,0.35)' : 'none',
            }}
          >
            <span
              className="material-symbols-outlined text-[22px]"
              style={isActive ? { fontVariationSettings: "'FILL' 1" } : {}}
            >
              {item.icon}
            </span>
            <span className="font-label-sm text-[10px]">{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
};
