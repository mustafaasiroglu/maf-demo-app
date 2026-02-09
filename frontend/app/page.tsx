'use client';

import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';

interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  debug?: any;
  toolCalls?: Array<{
    tool_name: string;
    arguments: any;
    result?: any;
    debug?: any;
  }>;
}

interface EventData {
  type: 'message' | 'message_chunk' | 'tool_call' | 'tool_result' | 'thinking' | 'error' | 'done';
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

  // Load theme preference from localStorage
  useEffect(() => {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
      setIsDarkMode(true);
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
      const response = await fetch(`${apiUrl}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: input,
          session_id: sessionId,
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
                setThinkingMessage(null);
                setStreamingContent(prev => prev + event.data.content);
              } else if (event.type === 'tool_call') {
                setCurrentToolCalls(prev => [
                  ...prev,
                  {
                    tool_name: event.data.tool_name,
                    arguments: event.data.arguments,
                    status: event.data.status,
                    debug: event.debug,
                  },
                ]);
              } else if (event.type === 'tool_result') {
                setCurrentToolCalls(prev =>
                  prev.map(tc =>
                    tc.tool_name === event.data.tool_name
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
      const response = await fetch(`${apiUrl}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: question,
          session_id: 'default',
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
                setThinkingMessage(null);
                setStreamingContent(prev => prev + event.data.content);
              } else if (event.type === 'tool_call') {
                setCurrentToolCalls(prev => [
                  ...prev,
                  {
                    tool_name: event.data.tool_name,
                    arguments: event.data.arguments,
                    status: event.data.status,
                    debug: event.debug,
                  },
                ]);
              } else if (event.type === 'tool_result') {
                setCurrentToolCalls(prev =>
                  prev.map(tc =>
                    tc.tool_name === event.data.tool_name
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
            {user && (
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

          {/* LLM Model Selection */}
          <div className="mb-6">
            <label className={`block text-sm font-semibold mb-3 ${isDarkMode ? 'text-dark-text' : 'text-gray-700'}`}>
              LLM Model
            </label>
            <div className="space-y-2">
              {llmModels.map((model) => (
                <button
                  key={model}
                  onClick={() => setSelectedModel(model)}
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

          {/* Current Selection Info */}
          <div className={`mt-auto p-4 rounded-lg ${isDarkMode ? 'bg-dark-card' : 'bg-gray-100'}`}>
            <div className={`text-xs ${isDarkMode ? 'text-dark-muted' : 'text-gray-500'}`}>Current Configuration</div>
            <div className={`text-sm font-semibold mt-1 ${isDarkMode ? 'text-dark-text' : 'text-gray-800'}`}>
              Model: {selectedModel}
            </div>
            <div className={`text-sm font-semibold ${isDarkMode ? 'text-dark-text' : 'text-gray-800'}`}>
              Theme: {isDarkMode ? 'Dark' : 'Light'}
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
              <div className={`flex-1 rounded-lg p-4 ${isDarkMode ? 'bg-dark-surface' : 'bg-white'}`}>
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
                      {message.debug.timeline_events && message.debug.timeline_events.length > 0 && (
                        <div className={`mb-3 rounded border overflow-hidden ${isDarkMode ? 'border-dark-card' : 'border-gray-200'}`}>
                          <table className="w-full text-xs">
                            <thead>
                              <tr className={isDarkMode ? 'bg-dark-card' : 'bg-gray-100'}>
                                <th className="text-left px-2 py-1 w-8">#</th>
                                <th className="text-left px-2 py-1">Event</th>
                                <th className="text-right px-2 py-1 w-20">Duration</th>
                              </tr>
                            </thead>
                            <tbody>
                              {message.debug.timeline_events.map((event: any, idx: number) => (
                                <tr key={idx} className={`border-t ${isDarkMode ? 'border-dark-card' : 'border-gray-200'}`}>
                                  <td className={`px-2 py-1 ${isDarkMode ? 'text-dark-muted' : 'text-gray-500'}`}>{event.order}.</td>
                                  <td className="px-2 py-1">
                                    <span className={event.event_type === 'llm_request' ? (isDarkMode ? 'text-blue-300' : 'text-blue-600') : (isDarkMode ? 'text-orange-300' : 'text-orange-600')}>
                                      {event.event_type === 'llm_request' ? '✨' : '🌐'}
                                    </span>
                                    {' '}
                                    <span className={isDarkMode ? 'text-dark-text' : 'text-gray-800'}>{event.label}</span>
                                  </td>
                                  <td className={`px-2 py-1 text-right font-mono font-semibold ${isDarkMode ? 'text-primary-lighter' : 'text-primary'}`}>
                                    {event.duration_ms.toFixed(0)} ms
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                          
                          {/* Summary */}
                          <div className={`px-2 py-2 border-t ${isDarkMode ? 'bg-dark-card border-dark-card' : 'bg-gray-100 border-gray-200'}`}>
                            <div className="flex justify-between mb-1">
                              <span className={isDarkMode ? 'text-dark-muted' : 'text-gray-600'}>Total LLM Duration:</span>
                              <span className={`font-mono font-semibold ${isDarkMode ? 'text-blue-300' : 'text-blue-600'}`}>{message.debug.total_llm_time_ms?.toFixed(0)} ms</span>
                            </div>
                            <div className="flex justify-between mb-1">
                              <span className={isDarkMode ? 'text-dark-muted' : 'text-gray-600'}>Total Tool Duration:</span>
                              <span className={`font-mono font-semibold ${isDarkMode ? 'text-orange-300' : 'text-orange-600'}`}>{message.debug.total_tool_time_ms?.toFixed(0)} ms</span>
                            </div>
                    
                            <div className="flex justify-between pt-1 border-t border-current/20">
                              <span className={`font-semibold ${isDarkMode ? 'text-dark-text' : 'text-gray-800'}`}>Total Request Duration:</span>
                              <span className={`font-mono font-semibold ${isDarkMode ? 'text-green-400' : 'text-green-600'}`}>{message.debug.total_request_time_ms?.toFixed(0)} ms</span>
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
          👤
        </div>
      )}
    </div>
  );
}
