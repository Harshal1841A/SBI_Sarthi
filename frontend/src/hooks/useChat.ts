import { useState, useCallback, useRef } from 'react';
import { chatApi } from '../services/api';
import { ChatMessage, ChatResponse } from '../types';

// FIX M-3: SESSION_ID was a module-level constant evaluated ONCE when the
// module loads. In multi-tab scenarios (or React strict-mode double-mount),
// all tabs share the same SESSION_ID — their messages end up in the same
// LangGraph thread, causing conversation cross-contamination.
//
// Fix: generate SESSION_ID inside the hook with useRef so that:
// 1. Each hook instance (each mounted component) gets a unique ID.
// 2. The ID is stable across renders (useRef, not useState).
// 3. Multiple browser tabs each get independent LangGraph threads.

export function useChat() {
  // useRef ensures the ID is stable across re-renders without triggering them
  const sessionIdRef = useRef<string>(
    `session_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
  );

  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      content: 'Namaste! Main Sarthi hoon, aapka SBI digital banking saathi. Aaj main aapki kya madad kar sakta hoon?',
      timestamp: new Date().toISOString()
    }
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const [lastResponse, setLastResponse] = useState<ChatResponse | null>(null);

  const sendMessage = useCallback(async (content: string, language: string = 'hi') => {
    const userMessage: ChatMessage = {
      role: 'user',
      content,
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const response = await chatApi.sendMessage(sessionIdRef.current, content, language);
      setLastResponse(response);

      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: response.response,
        timestamp: new Date().toISOString(),
        intent: response.intent,
        confidence: response.confidence,
        shieldFlags: response.shield_flags,
        riskScore: response.risk_score
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Chat error:', error);
      const errorMessage: ChatMessage = {
        role: 'system',
        content: 'Sorry, there was an error processing your request. Please try again or contact SBI at 1800-11-2211.',
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }, []); // stable — sessionIdRef.current is accessed at call time, not captured

  const clearChat = useCallback(() => {
    // Also generate a fresh session ID on chat clear — new conversation context
    sessionIdRef.current = `session_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    setMessages([
      {
        role: 'assistant',
        content: 'Chat cleared. Namaste! How can I help you today?',
        timestamp: new Date().toISOString()
      }
    ]);
    setLastResponse(null);
  }, []);

  return {
    messages,
    isLoading,
    lastResponse,
    sessionId: sessionIdRef.current, // expose for debugging
    sendMessage,
    clearChat
  };
}
