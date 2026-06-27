import { useChat } from '../hooks/useChat';
import { Send, Mic, User, Bot, Shield, AlertTriangle, Loader2 } from 'lucide-react';
import { useState, useRef, useEffect } from 'react';

interface ChatInterfaceProps {
  // FIX L-5: onVoiceClick allows the parent (App.tsx) to switch to the Voice tab
  // when the user taps the mic icon in the chat bar.
  // Previously the button had no onClick and was silently dead UI.
  onVoiceClick?: () => void;
}

export default function ChatInterface({ onVoiceClick }: ChatInterfaceProps) {
  const { messages, isLoading, sendMessage, clearChat } = useChat();
  const [input, setInput] = useState('');
  const [language, setLanguage] = useState('hi');
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    sendMessage(input.trim(), language);
    setInput('');
  };

  const getQuickReplies = () => {
    switch (language) {
      case 'hi':
        return [
          { text: 'अकाउंट खोलो', lang: 'hi' },
          { text: 'बैलेंस कितना है?', lang: 'hi' },
          { text: 'लोन चाहिए', lang: 'hi' },
          { text: 'कार्ड ब्लॉक करो', lang: 'hi' },
        ];
      case 'mr':
        return [
          { text: 'खाते उघडा', lang: 'mr' },
          { text: 'बॅलन्स किती आहे?', lang: 'mr' },
          { text: 'कर्ज हवे आहे', lang: 'mr' },
          { text: 'कार्ड ब्लॉक करा', lang: 'mr' },
        ];
      default:
        return [
          { text: 'Open account', lang: 'en' },
          { text: 'Check balance', lang: 'en' },
          { text: 'Need a loan', lang: 'en' },
          { text: 'Block card', lang: 'en' },
        ];
    }
  };

  const quickReplies = getQuickReplies();

  return (
    <div className="flex flex-col h-full bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden">
      {/* Header */}
      <div className="bg-[#00447C] text-white px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bot className="w-5 h-5" />
          <span className="font-semibold">Sarthi Chat</span>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="bg-white/20 text-white text-sm rounded px-2 py-1 border-none outline-none"
          >
            <option className="text-gray-900 bg-white" value="hi">Hindi</option>
            <option className="text-gray-900 bg-white" value="mr">Marathi</option>
            <option className="text-gray-900 bg-white" value="en">English</option>
          </select>
          <button
            onClick={clearChat}
            className="text-xs bg-white/20 hover:bg-white/30 px-2 py-1 rounded transition"
          >
            Clear
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex gap-2 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
          >
            <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
              msg.role === 'user' ? 'bg-[#00447C] text-white' : 'bg-gray-100'
            }`}>
              {msg.role === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
            </div>
            <div className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
              msg.role === 'user'
                ? 'bg-[#00447C] text-white'
                : msg.role === 'system'
                ? 'bg-red-50 text-red-700 border border-red-200'
                : 'bg-gray-100 text-gray-800'
            }`}>
              <p className="whitespace-pre-wrap">{msg.content}</p>
              {msg.shieldFlags && msg.shieldFlags.length > 0 && (
                <div className="mt-1 flex items-center gap-1 text-xs text-amber-600">
                  <Shield className="w-3 h-3" />
                  <span>Shield: {msg.shieldFlags.join(', ')}</span>
                </div>
              )}
              {msg.riskScore !== undefined && msg.riskScore > 0.5 && (
                <div className="mt-1 flex items-center gap-1 text-xs text-red-500">
                  <AlertTriangle className="w-3 h-3" />
                  <span>Risk: {(msg.riskScore * 100).toFixed(0)}%</span>
                </div>
              )}
              {msg.timestamp && (
                <div className="text-xs opacity-50 mt-1">
                  {new Date(msg.timestamp).toLocaleTimeString()}
                </div>
              )}
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="flex gap-2">
            <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center">
              <Loader2 className="w-4 h-4 animate-spin" />
            </div>
            <div className="bg-gray-100 rounded-lg px-3 py-2">
              <div className="flex gap-1">
                <div className="w-2 h-2 bg-gray-400 rounded-full typing-dot" />
                <div className="w-2 h-2 bg-gray-400 rounded-full typing-dot" />
                <div className="w-2 h-2 bg-gray-400 rounded-full typing-dot" />
              </div>
            </div>
          </div>
        )}
        <div ref={scrollRef} />
      </div>

      {/* Quick Replies */}
      <div className="px-4 py-2 flex gap-2 overflow-x-auto border-t border-gray-100">
        {quickReplies.map((qr, i) => (
          <button
            key={i}
            onClick={() => {
              setLanguage(qr.lang);
              sendMessage(qr.text, qr.lang);
            }}
            className="text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 px-3 py-1 rounded-full whitespace-nowrap transition"
          >
            {qr.text}
          </button>
        ))}
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-3 border-t border-gray-200 flex gap-2">
        <button
          type="button"
          aria-label="Switch to voice input"
          title="Switch to Voice tab for microphone input"
          onClick={() => {
            if (onVoiceClick) {
              onVoiceClick();
            } else {
              // Fallback: guide user if no handler is wired
              console.warn('Voice mode: wire onVoiceClick prop to switch to the Voice tab');
            }
          }}
          className="p-2 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-600 transition active:scale-90"
        >
          <Mic className="w-5 h-5" />
        </button>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your message in Hindi, Marathi, or English..."
          className="flex-1 px-3 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-[#00447C] text-sm"
          disabled={isLoading}
        />
        <button
          type="submit"
          disabled={isLoading || !input.trim()}
          className="p-2 rounded-lg bg-[#00447C] hover:bg-[#003366] text-white disabled:opacity-50 transition"
        >
          <Send className="w-5 h-5" />
        </button>
      </form>
    </div>
  );
}
