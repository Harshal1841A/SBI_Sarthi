import React from 'react';
import { useTheme } from '../hooks/ThemeContext';

const CARDS = [
  { icon: 'account_balance_wallet', iconColor: '#14B8A6', label: 'Savings',      value: '₹4.2L',  sub: '+12.4%', subColor: '#14B8A6', subIcon: 'trending_up' },
  { icon: 'receipt_long',           iconColor: '#a3c9ff', label: 'Spending',     value: '₹24.8K', sub: '-4.2%',  subColor: '#f87171', subIcon: 'trending_down' },
  { icon: 'ads_click',              iconColor: '#c3c0ff', label: 'Goals',        value: '85%',    sub: 'progress', subColor: '#14B8A6', subIcon: '' },
  { icon: 'shield_with_heart',      iconColor: '#4fdbc8', label: 'Risk Profile', value: 'Low',    sub: 'Optimal',  subColor: '#4fdbc8', subIcon: 'check_circle' },
];

export const WellnessHub: React.FC = () => {
  const { theme } = useTheme();
  const dark = theme === 'dark';

  return (
    <section>
      <div className="flex items-center justify-between mb-3 px-1">
        <h3 style={{ color: dark ? '#a3c9ff' : '#00447C' }} className="font-headline-md text-body-lg font-semibold">
          Wellness Hub
        </h3>
        <span style={{ color: dark ? '#4fdbc8' : '#006b5f' }} className="font-label-md flex items-center gap-1">
          Excellent <span className="material-symbols-outlined text-[16px]" style={{ fontVariationSettings: "'FILL' 1" }}>stars</span>
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {CARDS.map((card) => (
          <div
            key={card.label}
            className="glass rounded-xl p-4 flex flex-col gap-2"
            style={{
              background: dark ? 'rgba(19,31,53,0.88)' : 'rgba(255,255,255,0.75)',
              border: `1px solid ${dark ? 'rgba(42,58,85,0.6)' : 'rgba(194,198,209,0.4)'}`,
            }}
          >
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-[20px]" style={{ color: card.iconColor }}>{card.icon}</span>
              <span className="font-label-md" style={{ color: dark ? '#b0bcd6' : '#44505f' }}>{card.label}</span>
            </div>
            <div className="mt-1">
              <div className="text-headline-md font-bold" style={{ color: dark ? '#a3c9ff' : '#00447C' }}>{card.value}</div>
              {card.label === 'Goals' ? (
                <div className="w-full rounded-full h-1.5 mt-2 overflow-hidden" style={{ background: dark ? '#1a2840' : '#e3eaff' }}>
                  <div className="h-full rounded-full" style={{ width: '85%', background: dark ? '#a3c9ff' : '#00447C' }} />
                </div>
              ) : (
                <div className="flex items-center gap-1 font-label-sm" style={{ color: card.subColor }}>
                  {card.sub}
                  {card.subIcon && <span className="material-symbols-outlined text-[14px]">{card.subIcon}</span>}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
};
