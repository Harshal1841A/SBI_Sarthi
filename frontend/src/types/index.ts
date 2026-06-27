export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp?: string;
  intent?: string;
  confidence?: number;
  shieldFlags?: string[];
  riskScore?: number;
}

export interface ChatResponse {
  response: string;
  intent: string;
  confidence: number;
  requires_hitl: boolean;
  shield_flags: string[];
  risk_score: number;
  language: string;
}

export interface HITLThread {
  thread_id: string;
  customer_context: any[];
  interrupt_reason: string;
  risk_score: number;
  intent: string;
  language: string;
  channel: string;
  timestamp: string;
  onboarding_step?: string;
  user_id?: string;
}

export interface HITLDecision {
  approved: boolean;
  reason?: string;
  approver_id: string;
}

export interface ConsentArtifact {
  user_id: string;
  purpose_id: string;
  language: string;
  granted: boolean;
  timestamp: number;
  artifact_hash: string;
}

export interface VoiceSession {
  session_id: string;
  is_connected: boolean;
  is_listening: boolean;
  is_speaking: boolean;
}

export interface SystemStats {
  version: string;
  active_sessions: number;
  hitl_pending: number;
  // FIX H-9: matches get_cache_stats() in backend/utils/cache.py
  cache: {
    memory_entries: number;
    disk_entries: number;
    demo_entries?: number;
  };
  audit: {
    total_events: number;
    chain_integrity: boolean;
  };
}

export interface AuditLogEntry {
  event_type: string;
  session_id: string;
  agent_name: string;
  decision: Record<string, any>;
  timestamp: number;
  timestamp_iso: string;
  hash: string;
  prev_hash: string;
}

export interface OnboardingStep {
  id: string;
  label: string;
  description: string;
  status: 'pending' | 'active' | 'completed' | 'blocked';
  icon: string;
  agent: string;
}

export interface VoiceDemoResult {
  transcript: string;
  intent: string;
  confidence: number;
  entities: Record<string, any>;
  routed_to: string;
  language: string;
}
