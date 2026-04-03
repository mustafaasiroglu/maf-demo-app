'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Language, getTranslations } from '../i18n';

// Dynamically import Speech SDK only on client side
import type * as SpeechSDKType from 'microsoft-cognitiveservices-speech-sdk';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

interface EventData {
  type: 'message' | 'message_chunk' | 'tool_call' | 'tool_result' | 'thinking' | 'pii_result' | 'error' | 'done';
  data: any;
  debug?: any;
}

/* Sentence-level punctuations used to split streamed text for TTS */
const SENTENCE_PUNCTUATIONS = ['.', '?', '!', ':', ';', '。', '？', '！', '：', '；'];

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function htmlEncode(text: string): string {
  const map: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;', '/': '&#x2F;' };
  return text.replace(/[&<>"'/]/g, (m) => map[m]);
}

const generateSessionId = () => `avatar_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function AvatarPage() {
  /* ---- Theme / i18n state (same as main page) ---- */
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [language, setLanguage] = useState<Language>('tr');
  const [colorTheme, setColorTheme] = useState<'green' | 'red' | 'navy' | 'gray'>('green');
  const [piiMaskingEnabled, setPiiMaskingEnabled] = useState(false);
  const [selectedModel, setSelectedModel] = useState('gpt-5.1-chat');
  const t = getTranslations(language);
  const [sessionId] = useState<string>(() => generateSessionId());

  /* ---- Avatar / Speech config ---- */
  const [ttsVoice, setTtsVoice] = useState('pt-BR-ThalitaMultilingualNeural');
  const [avatarCharacter, setAvatarCharacter] = useState('lisa');
  const [avatarStyle, setAvatarStyle] = useState('casual-sitting');
  const [sttLocales, setSttLocales] = useState('tr-TR,en-US,de-DE');
  const [showSubtitles, setShowSubtitles] = useState(false);
  const [continuousConversation, setContinuousConversation] = useState(true);
  const [showConfig, setShowConfig] = useState(true);

  /* ---- Session state ---- */
  const [sessionActive, setSessionActive] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [micActive, setMicActive] = useState(false);
  const [isSpeaking, setIsSpeakingState] = useState(false);
  const [subtitleText, setSubtitleText] = useState('');
  const [statusMessage, setStatusMessage] = useState('');
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [showTypeMessage, setShowTypeMessage] = useState(false);
  const [typedMessage, setTypedMessage] = useState('');
  const [thinkingMessage, setThinkingMessage] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  /* ---- Refs for SDK objects (not React state – no re-renders) ---- */
  const speechSdkRef = useRef<typeof SpeechSDKType | null>(null);
  const avatarSynthesizerRef = useRef<SpeechSDKType.AvatarSynthesizer | null>(null);
  const speechRecognizerRef = useRef<SpeechSDKType.SpeechRecognizer | null>(null);
  const peerConnectionRef = useRef<RTCPeerConnection | null>(null);
  const dataChannelRef = useRef<RTCDataChannel | null>(null);

  const isSpeakingRef = useRef(false);
  const spokenTextQueueRef = useRef<string[]>([]);
  const speakingTextRef = useRef('');
  const lastInteractionRef = useRef(new Date());
  const lastSpeakTimeRef = useRef<Date | undefined>(undefined);
  const isReconnectingRef = useRef(false);
  const userClosedSessionRef = useRef(false);
  const sessionActiveRef = useRef(false);

  const remoteVideoRef = useRef<HTMLDivElement>(null);
  const chatHistoryEndRef = useRef<HTMLDivElement>(null);

  /* ---- Load persisted preferences ---- */
  useEffect(() => {
    const s = (k: string) => localStorage.getItem(k);
    if (s('theme') === 'dark') setIsDarkMode(true);
    if (s('piiMaskingEnabled') === 'true') setPiiMaskingEnabled(true);
    if (s('selectedModel')) setSelectedModel(s('selectedModel')!);
    const lang = s('language') as Language | null;
    if (lang === 'tr' || lang === 'en') setLanguage(lang);
    const col = s('colorTheme') as any;
    if (['green', 'red', 'navy', 'gray'].includes(col)) setColorTheme(col);
    // Avatar-specific
    if (s('avatar_ttsVoice')) setTtsVoice(s('avatar_ttsVoice')!);
    if (s('avatar_character')) setAvatarCharacter(s('avatar_character')!);
    if (s('avatar_style')) setAvatarStyle(s('avatar_style')!);
    if (s('avatar_sttLocales')) setSttLocales(s('avatar_sttLocales')!);
  }, []);

  /* ---- Scroll chat to bottom ---- */
  useEffect(() => {
    chatHistoryEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory, thinkingMessage]);

  /* ---- Persist avatar settings on change ---- */
  const persistSetting = (key: string, value: string) => localStorage.setItem(key, value);

  /* ---- Cleanup on unmount ---- */
  useEffect(() => {
    return () => {
      disconnectAvatar();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ================================================================ */
  /*  Avatar Connection                                                */
  /* ================================================================ */

  const connectAvatar = useCallback(async () => {
    // Lazy-load SDK
    if (!speechSdkRef.current) {
      speechSdkRef.current = await import('microsoft-cognitiveservices-speech-sdk');
    }
    const SpeechSDK = speechSdkRef.current;

    setIsConnecting(true);
    setStatusMessage(t.avatarConnecting);

    try {
      // Fetch tokens from backend proxy (avoids CORS, keeps keys server-side)
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || '';
      const tokenRes = await fetch(`${apiUrl}/api/avatar/token`);
      if (!tokenRes.ok) {
        const err = await tokenRes.json().catch(() => ({ detail: tokenRes.statusText }));
        throw new Error(err.detail || `Token fetch failed: ${tokenRes.status}`);
      }
      const { relay, authToken, region: speechRegion } = await tokenRes.json();

      // Use auth token (not raw key) for Speech SDK configs
      const speechSynthesisConfig = SpeechSDK.SpeechConfig.fromAuthorizationToken(authToken, speechRegion);
      speechSynthesisConfig.speechSynthesisVoiceName = ttsVoice;

      const videoFormat = new SpeechSDK.AvatarVideoFormat();
      const avatarConfig = new SpeechSDK.AvatarConfig(avatarCharacter, avatarStyle, videoFormat);
      avatarConfig.customized = false;

      const synthesizer = new SpeechSDK.AvatarSynthesizer(speechSynthesisConfig, avatarConfig);
      avatarSynthesizerRef.current = synthesizer;

      synthesizer.avatarEventReceived = (_s: any, e: any) => {
        console.log('[Avatar Event]', e.description, e.offset !== 0 ? `offset: ${e.offset / 10000}ms` : '');
      };

      // Setup STT recognizer using auth token
      const speechRecognitionConfig = SpeechSDK.SpeechConfig.fromAuthorizationToken(authToken, speechRegion);
      speechRecognitionConfig.setProperty(
        SpeechSDK.PropertyId.SpeechServiceConnection_LanguageIdMode,
        'Continuous',
      );

      const localesArr = sttLocales.split(',').map(l => l.trim()).filter(Boolean);
      const autoDetect = SpeechSDK.AutoDetectSourceLanguageConfig.fromLanguages(localesArr);
      const recognizer = SpeechSDK.SpeechRecognizer.FromConfig(
        speechRecognitionConfig,
        autoDetect,
        SpeechSDK.AudioConfig.fromDefaultMicrophoneInput(),
      );
      speechRecognizerRef.current = recognizer;

      // Setup WebRTC with relay token
      await setupWebRTC(relay.Urls[0], relay.Username, relay.Password, SpeechSDK, synthesizer);
    } catch (err: any) {
      console.error('Failed to connect avatar:', err);
      setIsConnecting(false);
      setStatusMessage(err?.message || (language === 'tr' ? 'Bağlantı hatası' : 'Connection error'));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [avatarCharacter, avatarStyle, sttLocales, ttsVoice, language, t]);

  /* ================================================================ */
  /*  WebRTC Setup                                                     */
  /* ================================================================ */

  const setupWebRTC = async (
    iceUrl: string,
    iceUsername: string,
    iceCredential: string,
    SpeechSDK: typeof SpeechSDKType,
    synthesizer: SpeechSDKType.AvatarSynthesizer,
  ) => {
    const pc = new RTCPeerConnection({
      iceServers: [{ urls: [iceUrl], username: iceUsername, credential: iceCredential }],
    });
    peerConnectionRef.current = pc;

    pc.ontrack = (event) => {
      const remoteDiv = remoteVideoRef.current;
      if (!remoteDiv) return;

      if (event.track.kind === 'audio') {
        const audio = document.createElement('audio');
        audio.id = 'avatarAudio';
        audio.srcObject = event.streams[0];
        audio.autoplay = false;
        audio.addEventListener('loadeddata', () => audio.play());
        // Remove existing audio
        remoteDiv.querySelectorAll('audio').forEach(el => el.remove());
        remoteDiv.appendChild(audio);
      }

      if (event.track.kind === 'video') {
        const video = document.createElement('video');
        video.id = 'avatarVideo';
        video.srcObject = event.streams[0];
        video.autoplay = false;
        video.playsInline = true;
        video.style.width = '0.5px';
        video.addEventListener('loadeddata', () => video.play());

        video.onplaying = () => {
          // Remove old video elements
          remoteDiv.querySelectorAll('video').forEach(el => el.remove());
          video.style.width = '100%';
          video.style.maxWidth = '960px';
          video.style.borderRadius = '12px';
          remoteDiv.appendChild(video);

          setIsConnecting(false);
          setShowConfig(false);
          setSessionActive(true);
          sessionActiveRef.current = true;
          setStatusMessage(t.avatarSessionActive);
          isReconnectingRef.current = false;

          console.log('[WebRTC] Video channel connected.');
        };

        // If video not yet playing, append it so it can start
        if (!remoteDiv.querySelector('#avatarVideo')) {
          remoteDiv.appendChild(video);
        }
      }
    };

    // Data channel events (subtitles, session end, etc.)
    pc.addEventListener('datachannel', (event) => {
      dataChannelRef.current = event.channel;
      event.channel.onmessage = (e) => {
        const webRTCEvent = JSON.parse(e.data);
        if (webRTCEvent.event.eventType === 'EVENT_TYPE_TURN_START' && showSubtitles) {
          setSubtitleText(speakingTextRef.current);
        } else if (
          webRTCEvent.event.eventType === 'EVENT_TYPE_SESSION_END' ||
          webRTCEvent.event.eventType === 'EVENT_TYPE_SWITCH_TO_IDLE'
        ) {
          setSubtitleText('');
          if (webRTCEvent.event.eventType === 'EVENT_TYPE_SESSION_END') {
            if (!userClosedSessionRef.current && !isReconnectingRef.current) {
              if (Date.now() - lastInteractionRef.current.getTime() < 300_000) {
                console.log('[WebRTC] Session disconnected, reconnecting...');
                isReconnectingRef.current = true;
                setStatusMessage(t.avatarReconnecting);
                if (dataChannelRef.current) dataChannelRef.current.onmessage = null;
                if (avatarSynthesizerRef.current) avatarSynthesizerRef.current.close();
                connectAvatar();
              }
            }
          }
        }
        console.log('[WebRTC Event]', e.data);
      };
    });

    // Workaround: create client-side data channel
    pc.createDataChannel('eventChannel');

    pc.oniceconnectionstatechange = () => {
      console.log('[WebRTC] ICE state:', pc.iceConnectionState);
    };

    pc.addTransceiver('video', { direction: 'sendrecv' });
    pc.addTransceiver('audio', { direction: 'sendrecv' });

    try {
      const result = await synthesizer.startAvatarAsync(pc);
      if (result.reason === SpeechSDK.ResultReason.SynthesizingAudioCompleted) {
        console.log('[Avatar] Started. Result ID:', result.resultId);
      } else {
        console.log('[Avatar] Failed to start:', result.resultId);
        if (result.reason === SpeechSDK.ResultReason.Canceled) {
          const details = SpeechSDK.CancellationDetails.fromResult(result as any);
          console.error('[Avatar] Cancel reason:', details.errorDetails);
        }
        setIsConnecting(false);
        setShowConfig(true);
        setStatusMessage(language === 'tr' ? 'Avatar başlatılamadı' : 'Failed to start avatar');
      }
    } catch (err) {
      console.error('[Avatar] Start error:', err);
      setIsConnecting(false);
      setShowConfig(true);
    }
  };

  /* ================================================================ */
  /*  Disconnect                                                       */
  /* ================================================================ */

  const disconnectAvatar = useCallback(() => {
    if (avatarSynthesizerRef.current) {
      avatarSynthesizerRef.current.close();
      avatarSynthesizerRef.current = null;
    }
    if (speechRecognizerRef.current) {
      speechRecognizerRef.current.stopContinuousRecognitionAsync();
      speechRecognizerRef.current.close();
      speechRecognizerRef.current = null;
    }
    if (peerConnectionRef.current) {
      peerConnectionRef.current.close();
      peerConnectionRef.current = null;
    }
    sessionActiveRef.current = false;
  }, []);

  /* ================================================================ */
  /*  TTS: speak / speakNext / stopSpeaking                           */
  /* ================================================================ */

  const speakNext = useCallback((text: string) => {
    const synth = avatarSynthesizerRef.current;
    if (!synth) return;

    const ssml = `<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xmlns:mstts='http://www.w3.org/2001/mstts' xml:lang='en-US'><voice name='${ttsVoice}'><mstts:leadingsilence-exact value='0'/>${htmlEncode(text)}</voice></speak>`;

    lastSpeakTimeRef.current = new Date();
    isSpeakingRef.current = true;
    speakingTextRef.current = text;
    setIsSpeakingState(true);
    if (showSubtitles) setSubtitleText(text);

    synth.speakSsmlAsync(ssml).then(
      (result: any) => {
        const SpeechSDK = speechSdkRef.current!;
        if (result.reason === SpeechSDK.ResultReason.SynthesizingAudioCompleted) {
          console.log('[TTS] Completed:', text.substring(0, 50));
        } else {
          console.warn('[TTS] Error for text:', text.substring(0, 50));
        }
        lastSpeakTimeRef.current = new Date();
        speakingTextRef.current = '';

        if (spokenTextQueueRef.current.length > 0) {
          speakNext(spokenTextQueueRef.current.shift()!);
        } else {
          isSpeakingRef.current = false;
          setIsSpeakingState(false);
          setSubtitleText('');
        }
      },
      (error: any) => {
        console.error('[TTS] SSML error:', error);
        speakingTextRef.current = '';
        if (spokenTextQueueRef.current.length > 0) {
          speakNext(spokenTextQueueRef.current.shift()!);
        } else {
          isSpeakingRef.current = false;
          setIsSpeakingState(false);
        }
      },
    );
  }, [ttsVoice, showSubtitles]);

  const speak = useCallback((text: string) => {
    if (isSpeakingRef.current) {
      spokenTextQueueRef.current.push(text);
      return;
    }
    speakNext(text);
  }, [speakNext]);

  const stopSpeaking = useCallback(() => {
    lastInteractionRef.current = new Date();
    spokenTextQueueRef.current = [];
    avatarSynthesizerRef.current?.stopSpeakingAsync().then(
      () => {
        isSpeakingRef.current = false;
        setIsSpeakingState(false);
        setSubtitleText('');
        console.log('[TTS] Stop speaking request sent.');
      },
      (err: any) => console.error('[TTS] Stop error:', err),
    );
  }, []);

  /* ================================================================ */
  /*  Handle user query → backend SSE → avatar speech                  */
  /* ================================================================ */

  const handleUserQuery = useCallback(async (userQuery: string) => {
    lastInteractionRef.current = new Date();
    if (isSpeakingRef.current) stopSpeaking();

    setChatHistory(prev => [...prev, { role: 'user', content: userQuery, timestamp: new Date().toISOString() }]);
    setThinkingMessage(language === 'tr' ? 'Düşünüyor...' : 'Thinking...');
    setIsProcessing(true);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || '';
      const response = await fetch(`${apiUrl}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userQuery,
          session_id: sessionId,
          pii_masking_enabled: piiMaskingEnabled,
          model: selectedModel,
          language,
        }),
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) throw new Error('No reader');

      let assistantReply = '';
      let spokenSentence = '';
      let lineBuffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        lineBuffer += decoder.decode(value, { stream: true });
        const lines = lineBuffer.split('\n');
        lineBuffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const event: EventData = JSON.parse(line.substring(6));

            if (event.type === 'thinking') {
              setThinkingMessage(event.data.message);
            } else if (event.type === 'message_chunk') {
              setThinkingMessage(null);
              const token = event.data.content as string;
              assistantReply += token;
              spokenSentence += token;

              // Check for sentence boundary
              if (token === '\n' || token === '\n\n') {
                if (spokenSentence.trim()) speak(spokenSentence);
                spokenSentence = '';
              } else if (token.length <= 2) {
                for (const p of SENTENCE_PUNCTUATIONS) {
                  if (token.startsWith(p)) {
                    if (spokenSentence.trim()) speak(spokenSentence);
                    spokenSentence = '';
                    break;
                  }
                }
              }
            } else if (event.type === 'message') {
              assistantReply = event.data.content;
              setThinkingMessage(null);
            } else if (event.type === 'error') {
              console.error('[Chat] Error:', event.data.error);
              assistantReply = event.data.message || (language === 'tr' ? 'Bir hata oluştu.' : 'An error occurred.');
              setThinkingMessage(null);
            } else if (event.type === 'done') {
              break;
            }
          } catch (err) {
            console.error('[SSE] Parse error:', err);
          }
        }
      }

      // Speak any remaining sentence
      if (spokenSentence.trim()) {
        speak(spokenSentence);
      }

      if (assistantReply) {
        setChatHistory(prev => [...prev, { role: 'assistant', content: assistantReply, timestamp: new Date().toISOString() }]);
      }
    } catch (err) {
      console.error('[Chat] Request error:', err);
      const errMsg = language === 'tr' ? 'Üzgünüm, bir hata oluştu.' : 'Sorry, an error occurred.';
      setChatHistory(prev => [...prev, { role: 'assistant', content: errMsg, timestamp: new Date().toISOString() }]);
    } finally {
      setThinkingMessage(null);
      setIsProcessing(false);
    }
  }, [language, sessionId, piiMaskingEnabled, selectedModel, speak, stopSpeaking]);

  /* ================================================================ */
  /*  Microphone: start / stop STT                                     */
  /* ================================================================ */

  const toggleMicrophone = useCallback(() => {
    lastInteractionRef.current = new Date();
    const recognizer = speechRecognizerRef.current;
    if (!recognizer) return;

    if (micActive) {
      recognizer.stopContinuousRecognitionAsync(
        () => { setMicActive(false); },
        (err: string) => { console.error('[STT] Stop error:', err); setMicActive(false); },
      );
      return;
    }

    // Play audio element (required on some browsers for autoplay)
    const audioEl = remoteVideoRef.current?.querySelector('audio') as HTMLAudioElement | null;
    audioEl?.play();

    recognizer.recognized = (_s: any, e: any) => {
      const SpeechSDK = speechSdkRef.current;
      if (!SpeechSDK) return;
      if (e.result.reason === SpeechSDK.ResultReason.RecognizedSpeech) {
        const text = e.result.text.trim();
        if (!text) return;

        if (!continuousConversation) {
          recognizer.stopContinuousRecognitionAsync(
            () => setMicActive(false),
            (err: string) => { console.error('[STT] Stop error:', err); setMicActive(false); },
          );
        }
        handleUserQuery(text);
      }
    };

    recognizer.startContinuousRecognitionAsync(
      () => setMicActive(true),
      (err: string) => { console.error('[STT] Start error:', err); setMicActive(false); },
    );
  }, [micActive, continuousConversation, handleUserQuery]);

  /* ================================================================ */
  /*  Session controls                                                 */
  /* ================================================================ */

  const startSession = () => {
    userClosedSessionRef.current = false;
    persistSetting('avatar_ttsVoice', ttsVoice);
    persistSetting('avatar_character', avatarCharacter);
    persistSetting('avatar_style', avatarStyle);
    persistSetting('avatar_sttLocales', sttLocales);
    connectAvatar();
  };

  const closeSession = () => {
    userClosedSessionRef.current = true;
    setSessionActive(false);
    sessionActiveRef.current = false;
    setMicActive(false);
    setShowConfig(true);
    setStatusMessage(t.avatarSessionClosed);
    disconnectAvatar();
    // Clean up video/audio elements
    if (remoteVideoRef.current) {
      remoteVideoRef.current.innerHTML = '';
    }
  };

  const clearHistory = () => {
    setChatHistory([]);
    lastInteractionRef.current = new Date();
  };

  const handleTypedSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!typedMessage.trim() || isProcessing) return;
    handleUserQuery(typedMessage.trim());
    setTypedMessage('');
  };

  /* ================================================================ */
  /*  Render                                                           */
  /* ================================================================ */

  return (
    <div data-color={colorTheme} className={`flex flex-col h-screen ${isDarkMode ? 'dark bg-gradient-to-br from-dark-bg via-dark-surface to-dark-bg' : 'bg-gradient-to-br from-white via-primary/5 to-white'}`}>
      {/* ---- Header ---- */}
      <header className="bg-primary text-white p-4 shadow-md flex-shrink-0">
        <div className="container mx-auto flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold">{t.headerTitle}</h1>
            <p className="text-sm text-gray-100">{t.avatarSubtitle}</p>
          </div>
          <div className="flex items-center space-x-3">
            {/* Back to text chat */}
            <a
              href="/"
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-white/20 hover:bg-white/30 transition-colors text-sm"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
              <span>{t.avatarBackToChat}</span>
            </a>
            {/* Settings toggle */}
            {sessionActive && (
              <button
                onClick={() => setShowConfig(!showConfig)}
                className="p-2 rounded-lg hover:bg-white/20 transition-colors"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
              </button>
            )}
          </div>
        </div>
      </header>

      {/* ---- Main Content ---- */}
      <div className="flex-1 flex overflow-hidden">
        {/* ---- Left: Video Area ---- */}
        <div className={`flex-1 flex flex-col items-center justify-center p-4 relative ${sessionActive ? '' : 'min-h-0'}`}>
          {/* Configuration Panel */}
          {showConfig && !sessionActive && (
            <div className={`w-full max-w-lg rounded-xl shadow-lg p-6 ${isDarkMode ? 'bg-dark-surface' : 'bg-white'}`}>
              <h2 className={`text-lg font-bold mb-4 ${isDarkMode ? 'text-dark-text' : 'text-gray-800'}`}>{t.avatarConfigTitle}</h2>

              {/* TTS Voice */}
              <div className="mb-3">
                <label className={`block text-sm font-medium mb-1 ${isDarkMode ? 'text-dark-muted' : 'text-gray-600'}`}>{t.avatarTtsVoiceLabel}</label>
                <input
                  type="text"
                  value={ttsVoice}
                  onChange={e => setTtsVoice(e.target.value)}
                  className={`w-full p-2 rounded-lg border text-sm ${isDarkMode ? 'bg-dark-bg border-dark-card text-dark-text' : 'border-gray-300'}`}
                />
              </div>

              {/* Character & Style */}
              <div className="grid grid-cols-2 gap-3 mb-3">
                <div>
                  <label className={`block text-sm font-medium mb-1 ${isDarkMode ? 'text-dark-muted' : 'text-gray-600'}`}>{t.avatarCharacterLabel}</label>
                  <input
                    type="text"
                    value={avatarCharacter}
                    onChange={e => setAvatarCharacter(e.target.value)}
                    className={`w-full p-2 rounded-lg border text-sm ${isDarkMode ? 'bg-dark-bg border-dark-card text-dark-text' : 'border-gray-300'}`}
                  />
                </div>
                <div>
                  <label className={`block text-sm font-medium mb-1 ${isDarkMode ? 'text-dark-muted' : 'text-gray-600'}`}>{t.avatarStyleLabel}</label>
                  <input
                    type="text"
                    value={avatarStyle}
                    onChange={e => setAvatarStyle(e.target.value)}
                    className={`w-full p-2 rounded-lg border text-sm ${isDarkMode ? 'bg-dark-bg border-dark-card text-dark-text' : 'border-gray-300'}`}
                  />
                </div>
              </div>

              {/* STT Locales */}
              <div className="mb-3">
                <label className={`block text-sm font-medium mb-1 ${isDarkMode ? 'text-dark-muted' : 'text-gray-600'}`}>{t.avatarSttLocalesLabel}</label>
                <input
                  type="text"
                  value={sttLocales}
                  onChange={e => setSttLocales(e.target.value)}
                  className={`w-full p-2 rounded-lg border text-sm ${isDarkMode ? 'bg-dark-bg border-dark-card text-dark-text' : 'border-gray-300'}`}
                />
              </div>

              {/* Toggles */}
              <div className="flex flex-wrap gap-4 mb-5">
                <label className={`flex items-center space-x-2 text-sm ${isDarkMode ? 'text-dark-text' : 'text-gray-700'}`}>
                  <input type="checkbox" checked={showSubtitles} onChange={e => setShowSubtitles(e.target.checked)} className="rounded" />
                  <span>{t.avatarShowSubtitles}</span>
                </label>
                <label className={`flex items-center space-x-2 text-sm ${isDarkMode ? 'text-dark-text' : 'text-gray-700'}`}>
                  <input type="checkbox" checked={continuousConversation} onChange={e => setContinuousConversation(e.target.checked)} className="rounded" />
                  <span>{t.avatarContinuousConversation}</span>
                </label>
              </div>

              {/* Start button */}
              <button
                onClick={startSession}
                disabled={isConnecting}
                className="w-full py-3 rounded-lg bg-primary text-white font-semibold hover:bg-primary-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isConnecting ? t.avatarConnecting : t.avatarOpenSession}
              </button>
            </div>
          )}

          {/* Video container */}
          {(sessionActive || isConnecting) && (
            <div className="relative w-full max-w-[960px] flex flex-col items-center">
              <div
                ref={remoteVideoRef}
                className="w-full rounded-xl overflow-hidden bg-black/10 min-h-[300px] flex items-center justify-center"
              >
                {isConnecting && (
                  <div className="flex flex-col items-center space-y-3">
                    <div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin" />
                    <span className={`text-sm ${isDarkMode ? 'text-dark-muted' : 'text-gray-500'}`}>{t.avatarConnecting}</span>
                  </div>
                )}
              </div>

              {/* Subtitles overlay */}
              {subtitleText && (
                <div className="absolute bottom-16 left-0 right-0 text-center px-4">
                  <span className="inline-block px-4 py-2 rounded-lg bg-black/60 text-white text-sm shadow-lg" style={{ textShadow: '1px 1px 2px rgba(0,0,0,0.8)' }}>
                    {subtitleText}
                  </span>
                </div>
              )}

              {/* Control buttons */}
              {sessionActive && (
                <div className="flex flex-wrap items-center justify-center gap-2 mt-4">
                  {/* Microphone */}
                  <button
                    onClick={toggleMicrophone}
                    disabled={isProcessing && !micActive}
                    className={`flex items-center space-x-2 px-4 py-2 rounded-lg font-medium text-sm transition-all ${
                      micActive
                        ? 'bg-red-500 text-white hover:bg-red-600 animate-pulse'
                        : 'bg-primary text-white hover:bg-primary-dark disabled:opacity-50'
                    }`}
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 1a4 4 0 014 4v6a4 4 0 01-8 0V5a4 4 0 014-4z" />
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 10v1a7 7 0 01-14 0v-1" />
                      <line x1="12" y1="19" x2="12" y2="23" />
                      <line x1="8" y1="23" x2="16" y2="23" />
                    </svg>
                    <span>{micActive ? t.avatarStopMic : t.avatarStartMic}</span>
                  </button>

                  {/* Stop Speaking */}
                  <button
                    onClick={stopSpeaking}
                    disabled={!isSpeaking}
                    className={`flex items-center space-x-2 px-4 py-2 rounded-lg font-medium text-sm transition-all ${isDarkMode ? 'bg-dark-card text-dark-text hover:bg-dark-bg' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'} disabled:opacity-40`}
                  >
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                      <rect x="6" y="6" width="12" height="12" rx="2" />
                    </svg>
                    <span>{t.avatarStopSpeaking}</span>
                  </button>

                  {/* Type Message toggle */}
                  <button
                    onClick={() => setShowTypeMessage(!showTypeMessage)}
                    className={`flex items-center space-x-2 px-4 py-2 rounded-lg font-medium text-sm transition-all ${
                      showTypeMessage
                        ? isDarkMode ? 'bg-accent/20 text-accent' : 'bg-primary/10 text-primary'
                        : isDarkMode ? 'bg-dark-card text-dark-text hover:bg-dark-bg' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                    }`}
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                    <span>{t.avatarTypeMessage}</span>
                  </button>

                  {/* Clear Chat */}
                  <button
                    onClick={clearHistory}
                    className={`flex items-center space-x-2 px-4 py-2 rounded-lg font-medium text-sm transition-all ${isDarkMode ? 'bg-dark-card text-dark-text hover:bg-dark-bg' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`}
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                    <span>{t.avatarClearHistory}</span>
                  </button>

                  {/* Close Session */}
                  <button
                    onClick={closeSession}
                    className="flex items-center space-x-2 px-4 py-2 rounded-lg font-medium text-sm bg-red-500/10 text-red-500 hover:bg-red-500/20 transition-all"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                    <span>{t.avatarCloseSession}</span>
                  </button>
                </div>
              )}

              {/* Text input box */}
              {showTypeMessage && sessionActive && (
                <form onSubmit={handleTypedSubmit} className="w-full mt-3 flex space-x-2">
                  <input
                    type="text"
                    value={typedMessage}
                    onChange={e => setTypedMessage(e.target.value)}
                    placeholder={t.inputPlaceholder}
                    disabled={isProcessing}
                    className={`flex-1 p-3 rounded-lg border-2 text-sm focus:outline-none focus:border-primary ${isDarkMode ? 'bg-dark-bg border-dark-card text-dark-text placeholder-dark-muted' : 'border-primary/20'}`}
                  />
                  <button
                    type="submit"
                    disabled={isProcessing || !typedMessage.trim()}
                    className="px-5 py-3 rounded-lg bg-primary text-white font-medium hover:bg-primary-dark transition-colors disabled:opacity-50"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                    </svg>
                  </button>
                </form>
              )}
            </div>
          )}

          {/* Status bar */}
          {statusMessage && (
            <div className={`mt-3 text-xs px-3 py-1 rounded-full ${
              sessionActive
                ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                : isDarkMode ? 'bg-dark-card text-dark-muted' : 'bg-gray-100 text-gray-500'
            }`}>
              {sessionActive && <span className="inline-block w-2 h-2 rounded-full bg-green-500 mr-1.5 animate-pulse" />}
              {statusMessage}
            </div>
          )}
        </div>

        {/* ---- Right: Chat History Sidebar ---- */}
        {sessionActive && (
          <div className={`w-80 lg:w-96 flex-shrink-0 border-l flex flex-col ${isDarkMode ? 'bg-dark-bg border-dark-card' : 'bg-gray-50 border-gray-200'}`}>
            <div className={`p-3 border-b font-semibold text-sm ${isDarkMode ? 'border-dark-card text-dark-text' : 'border-gray-200 text-gray-700'}`}>
              💬 {language === 'tr' ? 'Sohbet Geçmişi' : 'Chat History'}
            </div>
            <div className="flex-1 overflow-y-auto p-3 space-y-3">
              {chatHistory.length === 0 && (
                <p className={`text-sm text-center py-8 ${isDarkMode ? 'text-dark-muted' : 'text-gray-400'}`}>
                  {language === 'tr' ? 'Henüz mesaj yok. Mikrofonu başlatın veya mesaj yazın.' : 'No messages yet. Start the microphone or type a message.'}
                </p>
              )}
              {chatHistory.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                    msg.role === 'user'
                      ? isDarkMode ? 'bg-primary/30 text-dark-text' : 'bg-primary-lighter text-gray-800'
                      : isDarkMode ? 'bg-dark-surface text-dark-text' : 'bg-white text-gray-800 shadow-sm'
                  }`}>
                    {msg.role === 'assistant' ? (
                      <div className={`prose prose-sm max-w-none break-words ${isDarkMode ? 'prose-invert' : ''}`}>
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                      </div>
                    ) : (
                      <span>{msg.content}</span>
                    )}
                    <div className={`text-[10px] mt-1 ${isDarkMode ? 'text-dark-muted' : 'text-gray-400'}`}>
                      {new Date(msg.timestamp).toLocaleTimeString('tr-TR')}
                    </div>
                  </div>
                </div>
              ))}

              {/* Thinking indicator */}
              {thinkingMessage && (
                <div className="flex justify-start">
                  <div className={`rounded-lg px-3 py-2 text-sm ${isDarkMode ? 'bg-dark-surface text-dark-muted' : 'bg-white text-gray-500 shadow-sm'}`}>
                    <div className="flex items-center space-x-2">
                      <div className="flex space-x-1">
                        <div className="w-1.5 h-1.5 bg-primary rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                        <div className="w-1.5 h-1.5 bg-primary rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                        <div className="w-1.5 h-1.5 bg-primary rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                      </div>
                      <span className="text-xs">{thinkingMessage}</span>
                    </div>
                  </div>
                </div>
              )}

              <div ref={chatHistoryEndRef} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
