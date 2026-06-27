import { useDemoMode } from '../hooks/DemoModeContext';
import { Play, X, Loader2, User } from 'lucide-react';

export default function DemoBanner() {
  const { isDemo, demoUser, isLoading, activateDemo, deactivateDemo, error } = useDemoMode();

  if (isDemo) {
    return (
      <div className="fixed top-16 left-0 right-0 z-50 flex justify-center px-4 pointer-events-none">
        <div className="flex items-center gap-3 bg-secondary/90 text-white text-xs font-medium px-4 py-2 rounded-full shadow-lg pointer-events-auto animate-fade-in">
          <div className="w-2 h-2 rounded-full bg-white animate-pulse" />
          <span className="font-semibold">DEMO MODE</span>
          {demoUser && (
            <div className="flex items-center gap-1 border-l border-white/30 pl-3">
              <User className="w-3 h-3" />
              <span>{demoUser.name}</span>
              <span className="opacity-75">({demoUser.user_id})</span>
            </div>
          )}
          <button 
            onClick={deactivateDemo}
            className="ml-2 p-1 rounded-full hover:bg-white/20 transition"
            title="Exit Demo Mode"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed top-16 left-0 right-0 z-50 flex justify-center px-4 pointer-events-none">
      <div className="flex items-center gap-3 bg-primary/90 text-white text-xs font-medium px-4 py-2 rounded-full shadow-lg pointer-events-auto animate-fade-in">
        <span className="material-symbols-outlined text-[14px]">info</span>
        <span>Welcome to Sarthi — activate demo mode for investors</span>
        <button
          onClick={activateDemo}
          disabled={isLoading}
          className="flex items-center gap-1 ml-2 bg-white/20 hover:bg-white/30 px-3 py-1 rounded-full transition disabled:opacity-50"
        >
          {isLoading ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Play className="w-3.5 h-3.5" />
          )}
          {isLoading ? 'Loading...' : 'Start Demo'}
        </button>
      </div>
      {error && (
        <div className="fixed top-24 left-0 right-0 flex justify-center px-4 pointer-events-none">
          <div className="bg-error/90 text-white text-xs px-4 py-2 rounded-full shadow-lg pointer-events-auto">
            {error}
          </div>
        </div>
      )}
    </div>
  );
}
