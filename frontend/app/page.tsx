'use client';

import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';

function ColoredJson({ data, isDarkMode }: { data: any; isDarkMode: boolean }) {
  const json = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
  const colorize = (str: string) => {
    return str.replace(
      /("(?:[^"\\]|\\.)*")(\s*:)?|\b(true|false|null)\b|(-?\d+\.?\d*(?:[eE][+-]?\d+)?)/g,
      (match, strVal, colon, boolNull, num) => {
        if (strVal) {
          if (colon) {
            // key
            const cls = isDarkMode ? 'color:#7dd3fc' : 'color:#0550ae';
            return `<span style="${cls}">${strVal}</span>${colon}`;
          }
          // string value
          const cls = isDarkMode ? 'color:#86efac' : 'color:#0a3069';
          return `<span style="${cls}">${strVal}</span>`;
        }
        if (boolNull) {
          const cls = isDarkMode ? 'color:#c4b5fd' : 'color:#6f42c1';
          return `<span style="${cls}">${match}</span>`;
        }
        if (num) {
          const cls = isDarkMode ? 'color:#fca5a5' : 'color:#0550ae';
          return `<span style="${cls}">${match}</span>`;
        }
        return match;
      }
    );
  };
  return (
    <span dangerouslySetInnerHTML={{ __html: colorize(json) }} />
  );
}

interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  debug?: any;
  toolCalls?: Array<{
    call_id?: string;
    tool_name: string;
    arguments: any;
    result?: any;
    debug?: any;
  }>;
}

interface EventData {
  type: 'message' | 'message_chunk' | 'tool_call' | 'tool_result' | 'thinking' | 'pii_result' | 'error' | 'done';
  data: any;
  debug?: any;
}

interface User {
  customer_id: string;
  name: string;
  email: string;
  phone: string;
  registration_date: string;
  portfolio: any[];
}

// Generate unique session ID for each page load
const generateSessionId = () => {
  return `session_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
};

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [currentToolCalls, setCurrentToolCalls] = useState<any[]>([]);
  const [thinkingMessage, setThinkingMessage] = useState<string | null>(null);
  const [streamingContent, setStreamingContent] = useState<string>('');
  const [user, setUser] = useState<User | null>(null);
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [selectedModel, setSelectedModel] = useState('gpt-5.1-chat');
  const [piiMaskingEnabled, setPiiMaskingEnabled] = useState(false);
  const [sessionId] = useState<string>(() => generateSessionId());
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const llmModels = ['gpt-5.1-chat', 'gpt-5.1', 'gpt-5.2-mini'];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, thinkingMessage, streamingContent]);

  // Load theme and PII preferences from localStorage
  useEffect(() => {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
      setIsDarkMode(true);
    }
    const savedPii = localStorage.getItem('piiMaskingEnabled');
    if (savedPii === 'true') {
      setPiiMaskingEnabled(true);
    }
    const savedModel = localStorage.getItem('selectedModel');
    if (savedModel && llmModels.includes(savedModel)) {
      setSelectedModel(savedModel);
    }
  }, []);

  // Focus input on page load
  useEffect(() => {
    inputRef.current?.focus();
    
    // Fetch user info
    const fetchUser = async () => {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || '';
        const response = await fetch(`${apiUrl}/user/me`);
        if (response.ok) {
          const userData = await response.json();
          setUser(userData);
        }
      } catch (error) {
        console.error('Failed to fetch user:', error);
      }
    };
    fetchUser();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      role: 'user',
      content: input,
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);
    setCurrentToolCalls([]);
    setThinkingMessage(null);
    setStreamingContent('');

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || '';
      const requestStartTime = performance.now();
      let ttftMs: number | null = null;
      const response = await fetch(`${apiUrl}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: input,
          session_id: sessionId,
          pii_masking_enabled: piiMaskingEnabled,
          model: selectedModel,
        }),
      });

      if (!response.ok) {
        throw new Error('Network response was not ok');
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('No reader available');
      }

      let assistantMessage = '';
      let messageDebug: any = null;
      const toolCallsData: any[] = [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const jsonStr = line.substring(6);
            try {
              const event: EventData = JSON.parse(jsonStr);

              if (event.type === 'thinking') {
                setThinkingMessage(event.data.message);
              } else if (event.type === 'message_chunk') {
                if (ttftMs === null) ttftMs = Math.round(performance.now() - requestStartTime);
                setThinkingMessage(null);
                setStreamingContent(prev => prev + event.data.content);
              } else if (event.type === 'tool_call') {
                const callId = event.debug?.call_id || `tool_${Date.now()}`;
                setCurrentToolCalls(prev => [
                  ...prev,
                  {
                    call_id: callId,
                    tool_name: event.data.tool_name,
                    arguments: event.data.arguments,
                    status: event.data.status,
                    debug: event.debug,
                  },
                ]);
              } else if (event.type === 'tool_result') {
                const resultCallId = event.debug?.call_id;
                setCurrentToolCalls(prev =>
                  prev.map(tc =>
                    (resultCallId && tc.call_id === resultCallId) || (!resultCallId && tc.tool_name === event.data.tool_name)
                      ? { ...tc, result: event.data.result, debug: event.debug, status: 'completed' }
                      : tc
                  )
                );
                toolCallsData.push({
                  tool_name: event.data.tool_name,
                  arguments: event.data,
                  result: event.data.result,
                  debug: event.debug,
                });
              } else if (event.type === 'message') {
                assistantMessage = event.data.content;
                messageDebug = event.debug;
                setThinkingMessage(null);
                setStreamingContent('');
              } else if (event.type === 'error') {
                console.error('Error from agent:', event.data.error);
                assistantMessage = event.data.message || 'Bir hata oluştu.';
                messageDebug = event.debug;
              } else if (event.type === 'done') {
                break;
              }
            } catch (err) {
              console.error('Error parsing SSE data:', err);
            }
          }
        }
      }

      if (assistantMessage) {
        if (messageDebug && ttftMs !== null) {
          messageDebug = { ...messageDebug, ttft_ms: ttftMs };
        }
        const newAssistantMessage: Message = {
          role: 'assistant',
          content: assistantMessage,
          timestamp: new Date().toISOString(),
          debug: messageDebug,
          toolCalls: toolCallsData.length > 0 ? toolCallsData : undefined,
        };
        setMessages(prev => [...prev, newAssistantMessage]);
      }
    } catch (error) {
      console.error('Error:', error);
      const errorMessage: Message = {
        role: 'assistant',
        content: 'Üzgünüm, bir hata oluştu. Lütfen tekrar deneyin.',
        timestamp: new Date().toISOString(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
      setCurrentToolCalls([]);
      setThinkingMessage(null);
      setStreamingContent('');
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  };

  const exampleQuestions = [
    'GTA Fonu nedir?',
    'Getirisi en yüksek fonları sırala',
    'GOL, GTA, GTL fonlarının son 1 haftaki sonuçlarını kıyaslar mısın?',
    'Ben kimim?',
  ];

  const handleExampleClick = async (question: string) => {
    if (isLoading) return;
    setInput(question);
    // Simulate form submit with the question
    const userMessage: Message = {
      role: 'user',
      content: question,
      timestamp: new Date().toISOString(),
    };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);
    setCurrentToolCalls([]);
    setThinkingMessage(null);
    setStreamingContent('');

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || '';
      const requestStartTime = performance.now();
      let ttftMs: number | null = null;
      const response = await fetch(`${apiUrl}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: question,
          session_id: sessionId,
          pii_masking_enabled: piiMaskingEnabled,
        }),
      });

      if (!response.ok) {
        throw new Error('Network response was not ok');
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('No reader available');
      }

      let assistantMessage = '';
      let messageDebug: any = null;
      const toolCallsData: any[] = [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const jsonStr = line.substring(6);
            try {
              const event: EventData = JSON.parse(jsonStr);

              if (event.type === 'thinking') {
                setThinkingMessage(event.data.message);
              } else if (event.type === 'message_chunk') {
                if (ttftMs === null) ttftMs = Math.round(performance.now() - requestStartTime);
                setThinkingMessage(null);
                setStreamingContent(prev => prev + event.data.content);
              } else if (event.type === 'tool_call') {
                const callId = event.debug?.call_id || `tool_${Date.now()}`;
                setCurrentToolCalls(prev => [
                  ...prev,
                  {
                    call_id: callId,
                    tool_name: event.data.tool_name,
                    arguments: event.data.arguments,
                    status: event.data.status,
                    debug: event.debug,
                  },
                ]);
              } else if (event.type === 'tool_result') {
                const resultCallId = event.debug?.call_id;
                setCurrentToolCalls(prev =>
                  prev.map(tc =>
                    (resultCallId && tc.call_id === resultCallId) || (!resultCallId && tc.tool_name === event.data.tool_name)
                      ? { ...tc, result: event.data.result, debug: event.debug, status: 'completed' }
                      : tc
                  )
                );
                toolCallsData.push({
                  tool_name: event.data.tool_name,
                  arguments: event.data,
                  result: event.data.result,
                  debug: event.debug,
                });
              } else if (event.type === 'message') {
                assistantMessage = event.data.content;
                messageDebug = event.debug;
                setThinkingMessage(null);
                setStreamingContent('');
              } else if (event.type === 'error') {
                console.error('Error from agent:', event.data.error);
                assistantMessage = event.data.message || 'Bir hata oluştu.';
                messageDebug = event.debug;
              } else if (event.type === 'done') {
                break;
              }
            } catch (err) {
              console.error('Error parsing SSE data:', err);
            }
          }
        }
      }

      if (assistantMessage) {
        if (messageDebug && ttftMs !== null) {
          messageDebug = { ...messageDebug, ttft_ms: ttftMs };
        }
        const newAssistantMessage: Message = {
          role: 'assistant',
          content: assistantMessage,
          timestamp: new Date().toISOString(),
          debug: messageDebug,
          toolCalls: toolCallsData.length > 0 ? toolCallsData : undefined,
        };
        setMessages(prev => [...prev, newAssistantMessage]);
      }
    } catch (error) {
      console.error('Error:', error);
      const errorMessage: Message = {
        role: 'assistant',
        content: 'Üzgünüm, bir hata oluştu. Lütfen tekrar deneyin.',
        timestamp: new Date().toISOString(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
      setCurrentToolCalls([]);
      setThinkingMessage(null);
      setStreamingContent('');
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  };

  return (
    <div className={`flex flex-col h-screen ${isDarkMode ? 'dark bg-gradient-to-br from-dark-bg via-dark-surface to-dark-bg' : 'bg-gradient-to-br from-white via-primary/5 to-white'}`}>
      {/* Header */}
      <header className="bg-primary text-white p-4 shadow-md flex-shrink-0">
        <div className="container mx-auto flex justify-between items-center">
          <div 
            className="cursor-pointer hover:opacity-80 transition-opacity"
            onClick={() => window.location.reload()}
          >
            <h1 className="text-2xl font-bold">Investing Agent</h1>
            <p className="text-sm text-gray-100">Garanti Yatırım Asistanı</p>
          </div>
          <div className="flex items-center space-x-4">
            {false && user && (
              <div className="flex items-center space-x-3" title={user.name}>
                {/* <div className="text-right">
                  <div className="font-semibold">{user.name}</div>
                  <div className={`text-xs ${isDarkMode ? 'text-dark-muted' : 'text-gray-200'}`}>{user.customer_id}</div>
                </div> */}
                <svg className="w-10 h-10" viewBox="0 0 40 40">
                  <circle cx="20" cy="20" r="20" fill="white" />
                  <text 
                    x="20" 
                    y="20" 
                    textAnchor="middle" 
                    dominantBaseline="central" 
                    fill="#00875a" 
                    fontSize="14" 
                    fontWeight="bold"
                    fontFamily="system-ui, sans-serif"
                  >
                    {user.name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)}
                  </text>
                </svg>
              </div>
            )}
            {/* Settings Button */}
            <button
              onClick={() => setIsSettingsOpen(true)}
              className="p-2 rounded-lg hover:bg-white/20 transition-colors duration-200"
              aria-label="Settings"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </button>
          </div>
        </div>
      </header>

      {/* Settings Panel Overlay */}
      {isSettingsOpen && (
        <div 
          className="fixed inset-0 bg-black/50 z-40 transition-opacity duration-300"
          onClick={() => setIsSettingsOpen(false)}
        />
      )}

      {/* Settings Panel */}
      <div 
        className={`fixed top-0 right-0 h-full w-80 z-50 transform transition-transform duration-300 ease-in-out ${isSettingsOpen ? 'translate-x-0' : 'translate-x-full'} ${isDarkMode ? 'bg-dark-surface' : 'bg-white'} shadow-2xl`}
      >
        <div className="p-6 h-full flex flex-col">
          {/* Panel Header */}
          <div className="flex justify-between items-center mb-6">
            <h2 className={`text-xl font-bold ${isDarkMode ? 'text-dark-text' : 'text-gray-800'}`}>Test Settings</h2>
            <button
              onClick={() => setIsSettingsOpen(false)}
              className={`p-2 rounded-lg hover:bg-gray-200 transition-colors ${isDarkMode ? 'hover:bg-dark-card text-dark-text' : ''}`}
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* PII Masking Toggle */}
          <div className="mb-6">
            <label className={`block text-sm font-semibold mb-3 ${isDarkMode ? 'text-dark-text' : 'text-gray-700'}`}>
              PII Masking
            </label>
            <button
              onClick={() => { const next = !piiMaskingEnabled; setPiiMaskingEnabled(next); localStorage.setItem('piiMaskingEnabled', String(next)); }}
              className={`w-full p-3 text-left rounded-lg border-2 transition-all duration-200 flex items-center justify-between ${
                piiMaskingEnabled
                  ? isDarkMode
                    ? 'border-emerald-400 bg-emerald-400/10 text-emerald-300 font-semibold'
                    : 'border-primary bg-primary/10 text-primary font-semibold'
                  : isDarkMode
                    ? 'border-emerald-400/30 bg-dark-card text-emerald-200 hover:border-emerald-400/60'
                    : 'border-gray-200 hover:border-primary/50'
              }`}
            >
              <div className="flex items-center space-x-2">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
                <span>Mask PII Data</span>
              </div>
              <div className={`w-10 h-6 rounded-full transition-colors duration-200 flex items-center ${
                piiMaskingEnabled
                  ? isDarkMode ? 'bg-emerald-400 justify-end' : 'bg-primary justify-end'
                  : isDarkMode ? 'bg-dark-bg justify-start' : 'bg-gray-300 justify-start'
              }`}>
                <div className="w-4 h-4 bg-white rounded-full mx-1 shadow-sm"></div>
              </div>
            </button>

          </div>

          {/* LLM Model Selection */}
          <div className="mb-6">
            <label className={`block text-sm font-semibold mb-3 ${isDarkMode ? 'text-dark-text' : 'text-gray-700'}`}>
              LLM Model
            </label>
            <div className="space-y-2">
              {llmModels.map((model) => (
                <button
                  key={model}
                  onClick={() => { setSelectedModel(model); localStorage.setItem('selectedModel', model); }}
                  className={`w-full p-3 text-left rounded-lg border-2 transition-all duration-200 ${
                    selectedModel === model
                      ? isDarkMode
                        ? 'border-emerald-400 bg-emerald-400/10 text-emerald-300 font-semibold'
                        : 'border-primary bg-primary/10 text-primary font-semibold'
                      : isDarkMode 
                        ? 'border-emerald-400/30 bg-dark-card text-emerald-200 hover:border-emerald-400/60' 
                        : 'border-gray-200 hover:border-primary/50'
                  }`}
                >
                  {model}
                </button>
              ))}
            </div>
          </div>

          {/* Theme Selection */}
          <div className="mb-6">
            <label className={`block text-sm font-semibold mb-3 ${isDarkMode ? 'text-dark-text' : 'text-gray-700'}`}>
              Theme
            </label>
            <div className="flex space-x-2">
              <button
                onClick={() => {
                  setIsDarkMode(false);
                  localStorage.setItem('theme', 'light');
                }}
                className={`flex-1 p-3 rounded-lg border-2 transition-all duration-200 flex items-center justify-center space-x-2 ${
                  !isDarkMode
                    ? 'border-primary bg-primary/10 text-primary font-semibold'
                    : 'border-emerald-400/30 bg-dark-card text-emerald-200 hover:border-emerald-400/60'
                }`}
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2.25a.75.75 0 01.75.75v2.25a.75.75 0 01-1.5 0V3a.75.75 0 01.75-.75zM7.5 12a4.5 4.5 0 119 0 4.5 4.5 0 01-9 0zM18.894 6.166a.75.75 0 00-1.06-1.06l-1.591 1.59a.75.75 0 101.06 1.061l1.591-1.59zM21.75 12a.75.75 0 01-.75.75h-2.25a.75.75 0 010-1.5H21a.75.75 0 01.75.75zM17.834 18.894a.75.75 0 001.06-1.06l-1.59-1.591a.75.75 0 10-1.061 1.06l1.59 1.591zM12 18a.75.75 0 01.75.75V21a.75.75 0 01-1.5 0v-2.25A.75.75 0 0112 18zM7.758 17.303a.75.75 0 00-1.061-1.06l-1.591 1.59a.75.75 0 001.06 1.061l1.591-1.59zM6 12a.75.75 0 01-.75.75H3a.75.75 0 010-1.5h2.25A.75.75 0 016 12zM6.697 7.757a.75.75 0 001.06-1.06l-1.59-1.591a.75.75 0 00-1.061 1.06l1.59 1.591z" />
                </svg>
                <span>Light</span>
              </button>
              <button
                onClick={() => {
                  setIsDarkMode(true);
                  localStorage.setItem('theme', 'dark');
                }}
                className={`flex-1 p-3 rounded-lg border-2 transition-all duration-200 flex items-center justify-center space-x-2 ${
                  isDarkMode
                    ? 'border-emerald-400 bg-emerald-400/10 text-emerald-300 font-semibold'
                    : 'border-gray-200 hover:border-primary/50'
                }`}
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M21.752 15.002A9.718 9.718 0 0118 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 003 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 009.002-5.998z" />
                </svg>
                <span>Dark</span>
              </button>
            </div>
          </div>

        </div>
      </div>

      {/* Messages Container */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <div className="container mx-auto max-w-4xl">
          {messages.length === 0 && (
            <div className="text-center py-12">
              <div className="text-primary text-6xl mb-4">🍀</div>
              <h2 className={`text-2xl font-semibold mb-4 ${isDarkMode ? 'text-primary-lighter' : 'text-primary'}`}>
                Hoş Geldiniz!
              </h2>
              <p className={`mb-8 ${isDarkMode ? 'text-dark-muted' : 'text-gray-600'}`}>
                Size nasıl yardımcı olabilirim? İşte bazı örnek sorular:
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-2xl mx-auto">
                {exampleQuestions.map((question, index) => (
                  <button
                    key={index}
                    onClick={() => handleExampleClick(question)}
                    className={`p-3 text-left border-2 rounded-lg transition-all duration-200 ${isDarkMode ? 'bg-dark-surface border-primary/30 text-dark-text hover:border-primary hover:bg-dark-card' : 'bg-white border-primary/20 hover:border-primary hover:bg-primary/5'}`}
                  >
                    {question}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((message, index) => (
            <MessageBubble key={index} message={message} isDarkMode={isDarkMode} />
          ))}

          {/* Thinking/Loading State or Streaming Content */}
          {(thinkingMessage || isLoading || streamingContent) && (
            <div className="flex items-start space-x-3">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white flex-shrink-0 ${isDarkMode ? 'bg-dark-card' : 'bg-primary'}`}>
                🍀
              </div>
              <div className={`flex-1 max-w-[80%] rounded-lg p-4 ${isDarkMode ? 'bg-dark-surface' : 'bg-white'}`}>
                {/* Show streaming content if available */}
                {streamingContent ? (
                  <div className={`prose prose-sm max-w-none break-words ${isDarkMode ? 'prose-invert' : ''}`}>
                    <ReactMarkdown>{streamingContent}</ReactMarkdown>
                    <span className="inline-block w-2 h-4 bg-primary animate-pulse ml-1"></span>
                  </div>
                ) : (
                  <div className="flex items-center space-x-2">
                    <div className="flex space-x-1">
                      <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                      <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                      <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                    </div>
                    <span className={`text-sm ${isDarkMode ? 'text-dark-muted' : 'text-gray-600'}`}>
                      {thinkingMessage || ''}
                    </span>
                  </div>
                )}

                {/* Show tool calls */}
                {false && currentToolCalls.length > 0 && !streamingContent && (
                  <div className="mt-3 space-y-2">
                    {currentToolCalls.map((tc, idx) => (
                      <div key={idx} className={`text-xs rounded p-2 ${isDarkMode ? 'bg-dark-card/50' : 'bg-white/50'}`}>
                        <div className="flex items-center space-x-2">
                          <span className={`font-semibold ${isDarkMode ? 'text-dark-text' : 'text-gray-800'}`}>🔧 {tc.tool_name}</span>
                          {tc.status === 'executing' && (
                            <span className={isDarkMode ? 'text-yellow-400' : 'text-yellow-600'}>⏳ Çalışıyor...</span>
                          )}
                          {tc.status === 'completed' && (
                            <span className={isDarkMode ? 'text-green-400' : 'text-green-600'}>✓ Tamamlandı</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Container */}
      <div className={`sticky bottom-0 border-t p-4 flex-shrink-0 ${isDarkMode ? 'bg-dark-surface border-dark-card' : 'bg-white'}`}>
        <div className="container mx-auto max-w-4xl">
          <form onSubmit={handleSubmit} className="flex space-x-3">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Size nasıl yardımcı olabilirim?"
              disabled={isLoading}
              className={`flex-1 p-3 border-2 rounded-lg focus:outline-none focus:border-primary disabled:cursor-not-allowed ${isDarkMode ? 'bg-dark-bg border-dark-card text-dark-text placeholder-dark-muted disabled:bg-dark-card' : 'border-primary/20 disabled:bg-gray-100'}`}
            />
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              className={`p-3 bg-primary text-white rounded-lg hover:bg-primary-dark disabled:cursor-not-allowed transition-colors duration-200 ${isDarkMode ? 'disabled:bg-dark-bg disabled:text-dark-muted' : 'disabled:bg-gray-300'}`}
            >
              {isLoading ? (
                <svg className="w-6 h-6 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              ) : (
                <svg fill="#ffffff" version="1.1" id="Capa_1" xmlns="http://www.w3.org/2000/svg" 
                  width="20px" height="20px" viewBox="0 0 31.806 31.806"
                >
                <g>
                  <g>
                    <path d="M1.286,12.465c-0.685,0.263-1.171,0.879-1.268,1.606c-0.096,0.728,0.213,1.449,0.806,1.88l6.492,4.724L30.374,2.534
                      L9.985,22.621l8.875,6.458c0.564,0.41,1.293,0.533,1.964,0.33c0.67-0.204,1.204-0.713,1.444-1.368l9.494-25.986
                      c0.096-0.264,0.028-0.559-0.172-0.756c-0.199-0.197-0.494-0.259-0.758-0.158L1.286,12.465z"/>
                    <path d="M5.774,22.246l0.055,0.301l1.26,6.889c0.094,0.512,0.436,0.941,0.912,1.148c0.476,0.206,1.025,0.162,1.461-0.119
                      c1.755-1.132,4.047-2.634,3.985-2.722L5.774,22.246z"/>
                  </g>
                </g>
                </svg>
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ message, isDarkMode }: { message: Message; isDarkMode: boolean }) {
  const [showDebug, setShowDebug] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<any>(null);
  const isUser = message.role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} items-start space-x-3`}>
      {!isUser && (
        <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white flex-shrink-0 ${isDarkMode ? 'bg-dark-card' : 'bg-primary'}`}>
          🍀
        </div>
      )}
      <div className={`flex-1 max-w-[80%] ${isUser ? 'order-first' : ''}`}>
        <div
          className={`rounded-lg p-4 ${
            isUser
              ? isDarkMode ? 'bg-primary/30 text-dark-text ml-auto' : 'bg-primary-lighter text-gray-800 ml-auto'
              : isDarkMode ? 'bg-dark-surface text-dark-text' : 'bg-white text-gray-800'
          }`}
        >
          <div className={`prose prose-sm max-w-none break-words ${isDarkMode ? 'prose-invert' : ''}`}>
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>

          {/* Debug Info Button */}
          {(message.debug || message.toolCalls) && (
            <div className="mt-3 pt-3 border-t border-current/20">
              <button
                onClick={() => setShowDebug(!showDebug)}
                className="flex items-center space-x-1 text-xs opacity-70 hover:opacity-100 transition-opacity"
              >
                <span>ℹ️</span>
                <span>{showDebug ? 'Detayları Gizle' : 'Detayları Göster'}</span>
              </button>

              {showDebug && (
                <div className={`mt-3 p-3 rounded text-xs ${isDarkMode ? 'bg-dark-bg/50' : 'bg-gray-50'}`}>
                  {message.debug && (
                    <div>
                      <div className="font-semibold mb-2">📊 Response Timeline:</div>
                      
                      {/* Unified Timeline Table */}
                      {message.debug.timeline_events && message.debug.timeline_events.length > 0 && (() => {
                        // Pre-compute timeline bar positions using timestamp_start from backend
                        const events = message.debug.timeline_events as any[];
                        const totalSpan = message.debug.total_request_time_ms || Math.max(...events.map((e: any) => (e.timestamp_end || (e.timestamp_start || 0) + (e.duration_ms || 0)))) || 1;

                        return (
                        <div className={`mb-3 rounded border overflow-hidden ${isDarkMode ? 'border-dark-card' : 'border-gray-200'}`}>
                          <table className="w-full text-xs table-fixed">
                            <thead>
                              <tr className={isDarkMode ? 'bg-dark-card' : 'bg-gray-100'}>
                                <th className="text-left px-2 py-1 w-3">#</th>
                                <th className="text-left px-2 py-1" style={{ width: '20%' }}>Agent</th>
                                <th className="text-left px-2 py-1" style={{ width: '30%' }}>Step</th>
                                <th className="text-left px-2 py-1" style={{ width: '30%' }}>Timeline</th>
                                <th className="text-right px-2 py-1 w-10">Duration</th>
                              </tr>
                            </thead>
                            <tbody>
                              {events.map((event: any, idx: number) => {
                                const colorClass = event.event_type === 'llm_request'
                                  ? (isDarkMode ? 'text-blue-300' : 'text-blue-600')
                                  : event.event_type === 'pii_masking'
                                    ? (isDarkMode ? 'text-purple-300' : 'text-purple-600')
                                    : (isDarkMode ? 'text-orange-300' : 'text-orange-600');
                                const barColor = event.event_type === 'llm_request'
                                  ? (isDarkMode ? 'bg-blue-400' : 'bg-blue-500')
                                  : event.event_type === 'pii_masking'
                                    ? (isDarkMode ? 'bg-purple-400' : 'bg-purple-500')
                                    : (isDarkMode ? 'bg-orange-400' : 'bg-orange-500');
                                
                                // Timeline bar position from timestamp_start offset
                                const leftPct = ((event.timestamp_start || 0) / totalSpan) * 100;
                                const widthPct = Math.max(((event.duration_ms || 0) / totalSpan) * 100, 0.5); // min 0.5% for visibility
                                const agent_name = event.agent_id ? event.agent_id : '-';
                                return (
                                <tr key={idx} className={`border-t ${isDarkMode ? 'border-dark-card' : 'border-gray-200'}`}>
                                  <td className={`px-2 py-1 ${isDarkMode ? 'text-dark-muted' : 'text-gray-500'}`}>{event.order}.</td>
                                  <td className={`px-2 py-1 ${isDarkMode ? 'text-dark-muted' : 'text-gray-500'}`}>{agent_name}</td>
                                  <td className="px-2 py-1 truncate">
                                    <span className={`${colorClass} ${isDarkMode ? 'text-dark-text' : ''}`}>{event.label}</span>
                                    {' '}
                                    <button
                                      onClick={() => {
                                        setSelectedEvent(event);
                                      }}
                                      className={`cursor-pointer hover:opacity-80 ${colorClass}`}
                                    >
                                      🔍
                                    </button>
                                     
                                  </td>
                                  <td className="px-2 py-1">
                                    <div className={`relative w-full h-4 rounded ${isDarkMode ? 'bg-dark-bg/60' : 'bg-gray-200/60'}`}>
                                      <div
                                        className={`absolute top-0 h-full rounded ${barColor} opacity-80`}
                                        style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
                                        title={`${event.duration_ms?.toFixed(0)} ms`}
                                      />
                                      {event.ttft_ms != null && (() => {
                                        const markerPct = ((event.timestamp_start || 0) + event.ttft_ms) / totalSpan * 100;
                                        return (
                                          <div
                                            className="absolute top-0 h-full w-0.5 bg-dark-card z-10"
                                            style={{ left: `${markerPct}%` }}
                                            title={`TTFT: ${Math.round(event.ttft_ms)} ms`}
                                          />
                                        );
                                      })()}
                                    </div>
                                  </td>
                                  <td className={`px-2 py-1 text-right font-mono font-semibold ${isDarkMode ? 'text-white' : 'text-gray-800'}`}>
                                    {event.duration_ms.toFixed(0)} ms
        
                                  </td>
                                </tr>
                                );
                              })}
                            </tbody>
                          </table>
                          
                          {/* Summary */}
                          <div className={`px-2 py-2 border-t ${isDarkMode ? 'bg-dark-card border-dark-card' : 'bg-gray-100 border-gray-200'}`}>
                            
                            <div className="flex justify-between">
                              <span className={`font-bold ${isDarkMode ? 'text-dark-text' : 'text-gray-900'}`}>Total Request Duration:</span>
                              <span className={`font-mono font-bold ${isDarkMode ? 'text-dark-text' : 'text-gray-900'}`}>{message.debug.total_request_time_ms?.toFixed(0)} ms</span>
                            </div>
                            <hr className={`my-2 border ${isDarkMode ? 'border-dark-border' : 'border-gray-300'}`} />
                            <div className="flex justify-between">
                              <span className={`font-bold ${isDarkMode ? 'text-dark-text' : 'text-primary-dark'}`}>Time to First Token (Frontend):</span>
                              <span className={`font-bold font-mono ${isDarkMode ? 'text-dark-text' : 'text-primary-dark'}`}>
                                {message.debug.ttft_ms != null ? `${message.debug.ttft_ms} ms` : '-'}
                              </span>
                            </div>
                          </div>
                        </div>
                        );
                      })()}

                      {/* Event Detail Popup (triggered from any timeline row) */}
                      {selectedEvent && (
                        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setSelectedEvent(null)}>
                          <div
                            className={`relative w-[600px] max-w-[90vw] max-h-[80vh] overflow-auto rounded-lg shadow-xl p-5 ${isDarkMode ? 'bg-dark-surface text-dark-text' : 'bg-white text-gray-800'}`}
                            onClick={(e) => e.stopPropagation()}
                          >
                            <button
                              onClick={() => setSelectedEvent(null)}
                              className={`absolute top-2 right-3 text-lg hover:opacity-70 ${isDarkMode ? 'text-dark-muted' : 'text-gray-400'}`}
                            >✕</button>
                            <h3 className="font-semibold text-sm mb-4">{selectedEvent.icon ?? '📋'} {selectedEvent.label} – Request Details</h3>

                            {/* Request Input */}
                            <div className="mb-4">
                              <div className={`text-xs font-semibold mb-1 ${isDarkMode ? 'text-dark-muted' : 'text-gray-500'}`}>Request Input</div>
                              <pre className={`text-xs p-3 rounded overflow-auto max-h-48 whitespace-pre-wrap break-all ${isDarkMode ? 'bg-dark-bg' : 'bg-gray-50 border border-gray-200'}`}>
                                {selectedEvent.request_input ? <ColoredJson data={selectedEvent.request_input} isDarkMode={isDarkMode} /> : 'N/A'}
                              </pre>
                            </div>

                            {/* Request Output */}
                            <div>
                              <div className={`text-xs font-semibold mb-1 ${isDarkMode ? 'text-dark-muted' : 'text-gray-500'}`}>Request Output</div>
                              <pre className={`text-xs p-3 rounded overflow-auto max-h-48 whitespace-pre-wrap break-all ${isDarkMode ? 'bg-dark-bg' : 'bg-gray-50 border border-gray-200'}`}>
                                {selectedEvent.request_output ? <ColoredJson data={selectedEvent.request_output} isDarkMode={isDarkMode} /> : 'N/A'}
                              </pre>
                            </div>

                            {/* Duration */}
                            <div className={`mt-3 pt-3 border-t text-xs ${isDarkMode ? 'border-dark-card text-dark-muted' : 'border-gray-200 text-gray-500'}`}>
                              Duration: <span className="font-mono font-semibold">{selectedEvent.duration_ms?.toFixed(0) ?? '–'} ms</span>
                              {selectedEvent.ttft_ms != null && (
                                <span className="ml-3">TTFT: <span className="font-mono font-semibold">{Math.round(selectedEvent.ttft_ms)} ms</span></span>
                              )}
                              <br />
                              <span className={isDarkMode ? 'text-dark-muted' : 'text-gray-400'}>
                                Start: <span className="font-mono">{selectedEvent.timestamp_start?.toFixed(2) ?? '–'} ms</span>
                                <span className="mx-2">→</span>
                                End: <span className="font-mono">{selectedEvent.timestamp_end?.toFixed(2) ?? '–'} ms</span>
                              </span>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        <div className={`text-xs mt-1 ${isUser ? 'text-right' : 'text-left'} ${isDarkMode ? 'text-dark-muted' : 'text-gray-500'}`}>
          {new Date(message.timestamp).toLocaleTimeString('tr-TR')}
        </div>
      </div>

      {isUser && (
        <div className="w-8 h-8 rounded-full bg-gray-300 flex items-center justify-center flex-shrink-0">
          <svg width="18" height="18" viewBox="0 0 60.671 60.671" fill="white" xmlns="http://www.w3.org/2000/svg">
            <ellipse cx="30.336" cy="12.097" rx="11.997" ry="12.097"/>
            <path d="M35.64,30.079H25.031c-7.021,0-12.714,5.739-12.714,12.821v17.771h36.037V42.9C48.354,35.818,42.661,30.079,35.64,30.079z"/>
          </svg>
        </div>
      )}
    </div>
  );
}
