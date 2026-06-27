/// <reference types="vite/client" />
import axios from 'axios';
import { ChatResponse, HITLThread, HITLDecision, ConsentArtifact, SystemStats } from '../types';

// FIX L-6: Honour VITE_API_BASE_URL if set (useful when Vite proxy is NOT available,
// e.g. direct connections in Electron or server-to-server dev).
// Falls back to '/api' (Vite proxy route) for standard local dev.
const API_BASE = import.meta.env.VITE_API_BASE_URL
  ? `${import.meta.env.VITE_API_BASE_URL}/api`
  : '/api';

// Read token from environment or localStorage
// VITE_SARTHI_API_TOKEN matches the backend SARTHI_API_TOKEN naming convention
const getToken = (): string => {
  return localStorage.getItem('sarthi_token') || import.meta.env.VITE_SARTHI_API_TOKEN || import.meta.env.VITE_SARTHI_TOKEN || '';
};

// Supervisor token is fetched from a secure backend endpoint or login flow.
// NEVER embed supervisor tokens in client-side env vars.
const getSupervisorToken = (): string => {
  return localStorage.getItem('sarthi_supervisor_token') || import.meta.env.VITE_SARTHI_SUPERVISOR_TOKEN || '';
};

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json'
  }
});

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const chatApi = {
  sendMessage: async (sessionId: string, message: string, language: string = 'en', userId?: string): Promise<ChatResponse> => {
    const response = await api.post('/chat/message', {
      session_id: sessionId,
      message,
      language,
      channel: 'chat',
      user_id: userId
    });
    return response.data;
  }
};

export const supervisorApi = {
  getPendingThreads: async (): Promise<HITLThread[]> => {
    const isDemo = localStorage.getItem('sarthi_demo_active') === 'true';
    if (isDemo) {
      const token = getToken();
      const response = await axios.get(`${API_BASE}/demo/supervisor/pending`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      return response.data.pending || [];
    }
    const token = getSupervisorToken();
    const response = await axios.get(`${API_BASE}/supervisor/pending`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  approveThread: async (threadId: string, decision: HITLDecision): Promise<any> => {
    const token = getSupervisorToken();
    const response = await axios.post(`${API_BASE}/supervisor/approve/${threadId}`, decision, {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  getAllThreads: async (limit: number = 50): Promise<any[]> => {
    const token = getSupervisorToken();
    const response = await axios.get(`${API_BASE}/supervisor/threads`, {
      headers: { Authorization: `Bearer ${token}` },
      params: { limit }
    });
    return response.data;
  }
};

export const consentApi = {
  requestConsent: async (userId: string, purposeId: string, language: string = 'en') => {
    const response = await api.post('/consent/request', {
      user_id: userId,
      purpose_id: purposeId,
      language,
      channel: 'chat'
    });
    return response.data;
  },

  grantConsent: async (artifact: ConsentArtifact) => {
    const response = await api.post('/consent/grant', artifact);
    return response.data;
  },

  getUserConsents: async (userId: string) => {
    const response = await api.get(`/consent/${userId}`);
    return response.data;
  },

  revokeConsent: async (userId: string, purposeId: string) => {
    const response = await api.delete(`/consent/${userId}/${purposeId}`);
    return response.data;
  }
};

export const systemApi = {
  getHealth: async () => {
    const response = await axios.get(`${API_BASE}/health`);
    return response.data;
  },

  getStats: async (): Promise<SystemStats> => {
    const response = await api.get('/v1/stats');
    return response.data;
  },

  getAuditLogs: async (sessionId?: string, limit: number = 100) => {
    const response = await api.get('/audit/logs', {
      params: { session_id: sessionId, limit }
    });
    return response.data;
  },

  getDemoToken: async () => {
    const response = await axios.get(`${API_BASE}/demo/token`);
    return response.data;
  },

  seedDemoData: async () => {
    const response = await api.post('/demo/seed');
    return response.data;
  },

  shieldCheck: async (text: string) => {
    const response = await api.post('/shield/check', { text });
    return response.data;
  }
};

export const kycApi = {
  uploadDocument: async (file: File, userId: string, docType: 'aadhaar' | 'pan') => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('user_id', userId);
    formData.append('doc_type', docType);

    const response = await api.post('/kyc/document', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data;
  }
};
