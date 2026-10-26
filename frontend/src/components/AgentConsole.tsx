import React, { useState, useRef, useEffect } from 'react';
import {
  Bot,
  Send,
  Sparkles,
  ShieldAlert,
  MapPin,
  Wrench,
  DollarSign,
  Cpu,
  Trash2,
  CheckCircle2,
  ArrowRight,
} from 'lucide-react';
import { analyticsApi } from '../services/api';
import { errorMessage } from '../hooks/useAsync';
import { ChatMessage, AgentToolExecution } from '../types';

export const AgentConsole: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome-1',
      sender: 'agent',
      text: 'Sawubona! I am the SmartFleet assistant. I can review your cash flow, fuel geofence audits and maintenance alerts, and look up corridor reference data. I can only propose maintenance - a person must approve it.',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const quickPrompts = [
    {
      label: 'Audit Fuel Siphoning & Geofences',
      prompt: 'Audit recent fuel fill-ups against our authorised stations and list any outside their geofences.',
      icon: ShieldAlert,
      color: 'text-amber-600 bg-amber-50 hover:bg-amber-100 border-amber-200',
    },
    {
      label: 'Plan N3 Corridor Freight to Durban',
      prompt: 'Give me the corridor reference data (distance, drive time, toll) between JOHANNESBURG_CITY_DEEP and DURBAN_HARBOUR.',
      icon: MapPin,
      color: 'text-blue-600 bg-blue-50 hover:bg-blue-100 border-blue-200',
    },
    {
      label: 'Roadworthiness & COF Due Alerts',
      prompt: 'Check roadworthiness certificates, PrDP status, and vehicles within 500km of scheduled maintenance.',
      icon: Wrench,
      color: 'text-rose-600 bg-rose-50 hover:bg-rose-100 border-rose-200',
    },
    {
      label: 'Financial Health & Cash-Flow Review',
      prompt: 'Retrieve live MTD financial KPIs, freight revenues, fuel costs, and net operational margins.',
      icon: DollarSign,
      color: 'text-emerald-600 bg-emerald-50 hover:bg-emerald-100 border-emerald-200',
    },
  ];

  const handleSend = async (messageText?: string) => {
    const textToSend = messageText || input.trim();
    if (!textToSend || loading) return;

    const userMsg: ChatMessage = {
      id: `usr-${Date.now()}`,
      sender: 'user',
      text: textToSend,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await analyticsApi.sendAgentMessage(textToSend);
      const agentMsg: ChatMessage = {
        id: `agent-${Date.now()}`,
        sender: 'agent',
        text: res.response,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        engine: res.model ?? res.engine,
        toolExecutions: res.toolExecutions,
      };
      setMessages((prev) => [...prev, agentMsg]);
    } catch (err) {
      const errorMsg: ChatMessage = {
        id: `agent-${Date.now()}`,
        sender: 'agent',
        text: errorMessage(err),
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        isError: true,
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const clearChat = () => {
    setMessages([
      {
        id: 'welcome-reset',
        sender: 'agent',
        text: 'Chat history cleared. How can I assist with your fleet operations today?',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ]);
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 flex flex-col h-[650px] overflow-hidden">
      {/* Header */}
      <div className="px-5 py-3.5 bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 border-b border-slate-800 text-white flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-indigo-600/30 border border-indigo-400/40 rounded-lg text-indigo-300">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="font-semibold text-sm">SmartFleet Assistant</h3>
            </div>
            <p className="text-[11px] text-slate-400 flex items-center gap-1 mt-0.5">
              <Cpu className="w-3 h-3 text-indigo-400" />
              Strands Agents SDK &bull; Amazon Bedrock
            </p>
          </div>
        </div>

        <button
          onClick={clearChat}
          title="Clear Conversation"
          className="p-1.5 rounded text-slate-400 hover:text-white hover:bg-slate-800 transition"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>

      {/* Quick Prompts Bar */}
      <div className="px-4 py-2.5 bg-slate-50 border-b border-slate-200">
        <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5 flex items-center gap-1">
          <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
          Ask the assistant
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {quickPrompts.map((p, idx) => {
            const Icon = p.icon;
            return (
              <button
                key={idx}
                onClick={() => handleSend(p.prompt)}
                disabled={loading}
                className={`flex items-center space-x-2 p-2 rounded-lg border text-left text-xs font-medium transition ${p.color} disabled:opacity-50`}
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span className="truncate">{p.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50/50">
        {messages.map((msg) => {
          const isUser = msg.sender === 'user';
          return (
            <div key={msg.id} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 shadow-sm ${
                  isUser
                    ? 'bg-indigo-600 text-white rounded-br-none'
                    : msg.isError
                    ? 'bg-rose-50 text-rose-900 border border-rose-200 rounded-bl-none'
                    : 'bg-white text-slate-800 border border-slate-200 rounded-bl-none'
                }`}
              >
                <div className="flex items-center justify-between text-[11px] mb-1 opacity-75 gap-3">
                  <span className="font-semibold">{isUser ? 'Fleet Controller' : 'SmartFleet Agent'}</span>
                  <span>{msg.timestamp}</span>
                </div>

                <p className="text-xs md:text-sm whitespace-pre-wrap leading-relaxed">{msg.text}</p>

                {/* Agent Tool Execution Badges */}
                {msg.toolExecutions && msg.toolExecutions.length > 0 && (
                  <div className="mt-2.5 pt-2 border-t border-slate-100 flex flex-wrap gap-1.5 items-center">
                    <span className="text-[10px] text-slate-400 font-medium">Tools Invoked:</span>
                    {msg.toolExecutions.map((t: AgentToolExecution, i: number) => (
                      <span
                        key={i}
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-indigo-50 text-indigo-700 border border-indigo-200"
                      >
                        <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                        {t.tool}
                      </span>
                    ))}
                  </div>
                )}

                {/* Engine stamp */}
                {msg.engine && (
                  <div className="mt-1 text-[10px] text-slate-400 font-mono flex items-center gap-1">
                    <span>Model: {msg.engine}</span>
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-white border border-slate-200 rounded-2xl rounded-bl-none px-4 py-3 shadow-sm text-slate-700 flex items-center space-x-2 text-xs">
              <Bot className="w-4 h-4 text-indigo-600 animate-spin" />
              <span>Working on it - reading your fleet data...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Box */}
      <div className="p-3 bg-white border-t border-slate-200">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="flex items-center space-x-2"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask: 'Audit fuel fill-ups', 'Which services are overdue?', 'How is my cash flow?'"
            disabled={loading}
            className="flex-1 px-4 py-2.5 bg-slate-50 border border-slate-300 rounded-lg text-xs md:text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white"
          />
          <button
            type="submit"
            disabled={!input.trim() || loading}
            className="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-300 text-white rounded-lg transition font-medium flex items-center space-x-1.5 text-xs md:text-sm"
          >
            <span>Send</span>
            <Send className="w-3.5 h-3.5" />
          </button>
        </form>
        <div className="mt-1.5 flex items-center justify-between text-[11px] text-slate-400">
          <span>ZAR (R) &bull; Litres (L) &bull; km</span>
          <span className="flex items-center gap-1 text-indigo-600 font-medium">
            AI responses can be wrong - verify before acting <ArrowRight className="w-3 h-3" />
          </span>
        </div>
      </div>
    </div>
  );
};
