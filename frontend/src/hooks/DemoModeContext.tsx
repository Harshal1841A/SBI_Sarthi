import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const API_BASE = '/api';

export interface DemoUser {
  user_id: string;
  name: string;
  phone: string;
  account_id: string;
  balance: number;
  language: string;
}

interface DemoModeContextType {
  isDemo: boolean;
  demoUser: DemoUser | null;
  apiToken: string | null;
  supervisorToken: string | null;
  isLoading: boolean;
  activateDemo: () => Promise<void>;
  deactivateDemo: () => void;
  error: string | null;
}

const DemoModeContext = createContext<DemoModeContextType | undefined>(undefined);

export const DemoModeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isDemo, setIsDemo] = useState(false);
  const [demoUser, setDemoUser] = useState<DemoUser | null>(null);
  const [apiToken, setApiToken] = useState<string | null>(null);
  const [supervisorToken, setSupervisorToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Check if demo was previously activated
  useEffect(() => {
    const saved = localStorage.getItem('sarthi_demo_active');
    if (saved === 'true') {
      const savedToken = localStorage.getItem('sarthi_token');
      const savedSup = localStorage.getItem('sarthi_supervisor_token');
      const savedUser = localStorage.getItem('sarthi_demo_user');
      if (savedToken && savedUser) {
        setIsDemo(true);
        setApiToken(savedToken);
        setSupervisorToken(savedSup || savedToken);
        try {
          setDemoUser(JSON.parse(savedUser));
        } catch (e) {
          console.error('Failed to parse demo user');
        }
      }
    }
  }, []);

  const activateDemo = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await axios.get(`${API_BASE}/demo/token`);
      const data = response.data;
      if (!data.api_token) {
        throw new Error('No token returned from demo endpoint');
      }

      localStorage.setItem('sarthi_token', data.api_token);
      if (data.supervisor_token) {
        localStorage.setItem('sarthi_supervisor_token', data.supervisor_token);
      } else {
        localStorage.removeItem('sarthi_supervisor_token');
      }
      localStorage.setItem('sarthi_demo_active', 'true');
      if (data.demo_user) {
        localStorage.setItem('sarthi_demo_user', JSON.stringify(data.demo_user));
      }

      setApiToken(data.api_token);
      setSupervisorToken(data.supervisor_token || null);
      setDemoUser(data.demo_user || null);
      setIsDemo(true);

      // Seed demo data in the backend
      try {
        await axios.post(`${API_BASE}/demo/seed`, {}, {
          headers: { Authorization: `Bearer ${data.api_token}` }
        });
      } catch (e) {
        console.log('Seed demo data may have failed, continuing anyway');
      }

    } catch (e: any) {
      setError(e.message || 'Failed to activate demo mode');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const deactivateDemo = useCallback(() => {
    localStorage.removeItem('sarthi_demo_active');
    localStorage.removeItem('sarthi_demo_user');
    localStorage.removeItem('sarthi_token');
    localStorage.removeItem('sarthi_supervisor_token');
    setIsDemo(false);
    setDemoUser(null);
    setApiToken(null);
    setSupervisorToken(null);
    setError(null);
    // FIX M-4: do NOT call window.location.reload() — it skips React cleanup:
    // useEffect returns, WebSocket close(), MediaStream.getTracks().stop(), etc.
    // Without cleanup the browser keeps the mic indicator ON and audio resources leak.
    // React state updates above trigger natural re-renders that unmount/remount
    // components cleanly, running all useEffect cleanup functions.
  }, []);

  return (
    <DemoModeContext.Provider
      value={{ isDemo, demoUser, apiToken, supervisorToken, isLoading, activateDemo, deactivateDemo, error }}
    >
      {children}
    </DemoModeContext.Provider>
  );
};

export const useDemoMode = () => {
  const context = useContext(DemoModeContext);
  if (context === undefined) {
    throw new Error('useDemoMode must be used within a DemoModeProvider');
  }
  return context;
};
