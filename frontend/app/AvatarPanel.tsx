'use client';

import { useState, useRef, useCallback, forwardRef, useImperativeHandle, useEffect } from 'react';
import type * as SpeechSDKType from 'microsoft-cognitiveservices-speech-sdk';
import type { Language, Translations } from './i18n';

export interface AvatarPanelHandle {
  speak: (text: string) => void;
  stopSpeaking: () => void;
  startSession: () => Promise<void>;
  closeSession: () => void;
  readonly sessionActive: boolean;
}

interface Props {
  ttsVoice: string;
  avatarCharacter: string;
  avatarStyle: string;
  sttLocales: string;
  usePhotoAvatar: boolean;
  showSubtitles: boolean;
  continuousConversation: boolean;
  language: Language;
  isDarkMode: boolean;
  t: Translations;
  onUserSpeech: (text: string) => void;
  onSessionChange: (active: boolean) => void;
}

function htmlEncode(text: string): string {
  const map: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;', '/': '&#x2F;' };
  return text.replace(/[&<>"'/]/g, (m) => map[m]);
}

const AvatarPanel = forwardRef<AvatarPanelHandle, Props>(function AvatarPanel(props, ref) {
  const {
    ttsVoice, avatarCharacter, avatarStyle, sttLocales, usePhotoAvatar,
    showSubtitles, continuousConversation,
    language, isDarkMode, t,
    onUserSpeech, onSessionChange,
  } = props;

  const [isSessionActive, setIsSessionActive] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [micActive, setMicActive] = useState(false);
  const [isSpeaking, setIsSpeakingUI] = useState(false);
  const [subtitleText, setSubtitleText] = useState('');
  const [statusMessage, setStatusMessage] = useState('');

  const speechSdkRef = useRef<typeof SpeechSDKType | null>(null);
  const avatarSynthesizerRef = useRef<SpeechSDKType.AvatarSynthesizer | null>(null);
  const speechRecognizerRef = useRef<SpeechSDKType.SpeechRecognizer | null>(null);
  const peerConnectionRef = useRef<RTCPeerConnection | null>(null);
  const dataChannelRef = useRef<RTCDataChannel | null>(null);

  const isSpeakingRef = useRef(false);
  const spokenTextQueueRef = useRef<string[]>([]);
  const speakingTextRef = useRef('');
  const lastInteractionRef = useRef(new Date());
  const isReconnectingRef = useRef(false);
  const userClosedRef = useRef(false);
  const sessionActiveRef = useRef(false);

  const remoteVideoRef = useRef<HTMLDivElement>(null);

  // Keep callback refs fresh without re-creating heavy callbacks
  const onUserSpeechRef = useRef(onUserSpeech);
  onUserSpeechRef.current = onUserSpeech;
  const onSessionChangeRef = useRef(onSessionChange);
  onSessionChangeRef.current = onSessionChange;
  const showSubtitlesRef = useRef(showSubtitles);
  //test
  showSubtitlesRef.current = showSubtitles;

  useEffect(() => { return () => { disconnectAvatar(); }; }, []); // eslint-disable-line react-hooks/exhaustive-deps

  /* ---- disconnect ---- */
  const disconnectAvatar = useCallback(() => {
    if (avatarSynthesizerRef.current) { avatarSynthesizerRef.current.close(); avatarSynthesizerRef.current = null; }
    if (speechRecognizerRef.current) { speechRecognizerRef.current.stopContinuousRecognitionAsync(); speechRecognizerRef.current.close(); speechRecognizerRef.current = null; }
    if (peerConnectionRef.current) { peerConnectionRef.current.close(); peerConnectionRef.current = null; }
    sessionActiveRef.current = false;
  }, []);

  /* ---- speakNext ---- */
  const speakNext = useCallback((text: string) => {
    const synth = avatarSynthesizerRef.current;
    if (!synth) return;
    const langLocale = language === 'tr' ? 'tr-TR' : 'en-US';
    const ssml = `<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xmlns:mstts='http://www.w3.org/2001/mstts' xml:lang='${langLocale}'><voice name='${ttsVoice}'><mstts:leadingsilence-exact value='0'/>${htmlEncode(text)}</voice></speak>`;
    isSpeakingRef.current = true;
    speakingTextRef.current = text;
    setIsSpeakingUI(true);
    if (showSubtitlesRef.current) setSubtitleText(text);

    synth.speakSsmlAsync(ssml).then(
      (result: any) => {
        const SDK = speechSdkRef.current!;
        if (result.reason !== SDK.ResultReason.SynthesizingAudioCompleted) {
          console.warn('[TTS] Error for:', text.substring(0, 40));
        }
        speakingTextRef.current = '';
        if (spokenTextQueueRef.current.length > 0) {
          speakNext(spokenTextQueueRef.current.shift()!);
        } else {
          isSpeakingRef.current = false; setIsSpeakingUI(false); setSubtitleText('');
        }
      },
      (err: any) => {
        console.error('[TTS] Error:', err);
        speakingTextRef.current = '';
        if (spokenTextQueueRef.current.length > 0) { speakNext(spokenTextQueueRef.current.shift()!); }
        else { isSpeakingRef.current = false; setIsSpeakingUI(false); }
      },
    );
  }, [ttsVoice, language]);

  /* ---- speak ---- */
  const speak = useCallback((text: string) => {
    if (isSpeakingRef.current) { spokenTextQueueRef.current.push(text); return; }
    speakNext(text);
  }, [speakNext]);

  /* ---- stopSpeaking ---- */
  const stopSpeaking = useCallback(() => {
    spokenTextQueueRef.current = [];
    avatarSynthesizerRef.current?.stopSpeakingAsync().then(
      () => { isSpeakingRef.current = false; setIsSpeakingUI(false); setSubtitleText(''); },
      (e: any) => console.error('[TTS] Stop err:', e),
    );
  }, []);

  /* ---- setupWebRTC ---- */
  const setupWebRTC = useCallback(async (
    iceUrl: string, iceUsername: string, iceCredential: string,
    SpeechSDK: typeof SpeechSDKType,
    synthesizer: SpeechSDKType.AvatarSynthesizer,
  ) => {
    const pc = new RTCPeerConnection({
      iceServers: [{ urls: [iceUrl], username: iceUsername, credential: iceCredential }],
    });
    peerConnectionRef.current = pc;

    pc.ontrack = (event) => {
      const div = remoteVideoRef.current;
      if (!div) return;
      if (event.track.kind === 'audio') {
        const audio = document.createElement('audio');
        audio.id = 'avatarAudio';
        audio.srcObject = event.streams[0];
        audio.autoplay = false;
        audio.addEventListener('loadeddata', () => audio.play());
        div.querySelectorAll('audio').forEach(el => el.remove());
        div.appendChild(audio);
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
          div.querySelectorAll('video').forEach(el => el.remove());
          video.style.width = '100%';
          video.style.borderRadius = '12px';
          div.appendChild(video);
          setIsConnecting(false);
          setIsSessionActive(true);
          sessionActiveRef.current = true;
          setStatusMessage(t.avatarSessionActive);
          isReconnectingRef.current = false;
          onSessionChangeRef.current(true);
        };
        if (!div.querySelector('#avatarVideo')) div.appendChild(video);
      }
    };

    pc.addEventListener('datachannel', (event) => {
      dataChannelRef.current = event.channel;
      event.channel.onmessage = (e) => {
        const ev = JSON.parse(e.data);
        if (ev.event.eventType === 'EVENT_TYPE_TURN_START' && showSubtitlesRef.current) {
          setSubtitleText(speakingTextRef.current);
        } else if (ev.event.eventType === 'EVENT_TYPE_SESSION_END' || ev.event.eventType === 'EVENT_TYPE_SWITCH_TO_IDLE') {
          setSubtitleText('');
          if (ev.event.eventType === 'EVENT_TYPE_SESSION_END' && !userClosedRef.current && !isReconnectingRef.current) {
            if (Date.now() - lastInteractionRef.current.getTime() < 300_000) {
              isReconnectingRef.current = true;
              setStatusMessage(t.avatarReconnecting);
              if (dataChannelRef.current) dataChannelRef.current.onmessage = null;
              if (avatarSynthesizerRef.current) avatarSynthesizerRef.current.close();
              connectAvatar();
            }
          }
        }
      };
    });
    pc.createDataChannel('eventChannel');
    pc.oniceconnectionstatechange = () => { console.log('[WebRTC] ICE:', pc.iceConnectionState); };
    pc.addTransceiver('video', { direction: 'sendrecv' });
    pc.addTransceiver('audio', { direction: 'sendrecv' });

    try {
      const result = await synthesizer.startAvatarAsync(pc);
      if (result.reason === SpeechSDK.ResultReason.SynthesizingAudioCompleted) {
        console.log('[Avatar] Started:', result.resultId);
      } else {
        console.error('[Avatar] Failed:', result.resultId);
        setIsConnecting(false);
        setStatusMessage(language === 'tr' ? 'Avatar başlatılamadı' : 'Failed to start avatar');
        onSessionChangeRef.current(false);
      }
    } catch (err) {
      console.error('[Avatar] Start error:', err);
      setIsConnecting(false);
      onSessionChangeRef.current(false);
    }
  }, [language, t]); // eslint-disable-line react-hooks/exhaustive-deps

  /* ---- connectAvatar ---- */
  const connectAvatar = useCallback(async () => {
    if (!speechSdkRef.current) {
      speechSdkRef.current = await import('microsoft-cognitiveservices-speech-sdk');
    }
    const SpeechSDK = speechSdkRef.current;
    setIsConnecting(true);
    setStatusMessage(t.avatarConnecting);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || '';
      const res = await fetch(`${apiUrl}/api/avatar/token`);
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `Token fetch failed: ${res.status}`);
      }
      const { relay, authToken, region } = await res.json();

      const synthConfig = SpeechSDK.SpeechConfig.fromAuthorizationToken(authToken, region);
      synthConfig.speechSynthesisVoiceName = ttsVoice;
      const videoFormat = new SpeechSDK.AvatarVideoFormat();
      const avatarConfig = new SpeechSDK.AvatarConfig(avatarCharacter, avatarStyle, videoFormat);
      avatarConfig.customized = false;
      if (usePhotoAvatar) {
        (avatarConfig as any).photoAvatarBaseModel = 'vasa-1';
      }
      const synthesizer = new SpeechSDK.AvatarSynthesizer(synthConfig, avatarConfig);
      avatarSynthesizerRef.current = synthesizer;
      synthesizer.avatarEventReceived = (_s: any, e: any) => {
        console.log('[Avatar Event]', e.description);
      };

      // STT recognizer
      const sttConfig = SpeechSDK.SpeechConfig.fromAuthorizationToken(authToken, region);
      sttConfig.setProperty(SpeechSDK.PropertyId.SpeechServiceConnection_LanguageIdMode, 'Continuous');
      const localesArr = sttLocales.split(',').map(l => l.trim()).filter(Boolean);
      const autoDetect = SpeechSDK.AutoDetectSourceLanguageConfig.fromLanguages(localesArr);
      speechRecognizerRef.current = SpeechSDK.SpeechRecognizer.FromConfig(
        sttConfig, autoDetect, SpeechSDK.AudioConfig.fromDefaultMicrophoneInput(),
      );

      await setupWebRTC(relay.Urls[0], relay.Username, relay.Password, SpeechSDK, synthesizer);
    } catch (err: any) {
      console.error('[Avatar] Connect error:', err);
      setIsConnecting(false);
      setStatusMessage(err?.message || (language === 'tr' ? 'Bağlantı hatası' : 'Connection error'));
      onSessionChangeRef.current(false);
    }
  }, [avatarCharacter, avatarStyle, sttLocales, ttsVoice, usePhotoAvatar, language, t, setupWebRTC]);

  /* ---- closeSession ---- */
  const closeSession = useCallback(() => {
    userClosedRef.current = true;
    setIsSessionActive(false);
    sessionActiveRef.current = false;
    setMicActive(false);
    setStatusMessage('');
    disconnectAvatar();
    onSessionChangeRef.current(false);
    if (remoteVideoRef.current) remoteVideoRef.current.innerHTML = '';
  }, [disconnectAvatar]);

  /* ---- toggleMicrophone ---- */
  const toggleMicrophone = useCallback(() => {
    lastInteractionRef.current = new Date();
    const rec = speechRecognizerRef.current;
    if (!rec) return;

    if (micActive) {
      rec.stopContinuousRecognitionAsync(
        () => setMicActive(false),
        (e: string) => { console.error('[STT] Stop err:', e); setMicActive(false); },
      );
      return;
    }

    const audioEl = remoteVideoRef.current?.querySelector('audio') as HTMLAudioElement | null;
    audioEl?.play();

    rec.recognized = (_s: any, e: any) => {
      const SDK = speechSdkRef.current;
      if (!SDK || e.result.reason !== SDK.ResultReason.RecognizedSpeech) return;
      const text = e.result.text.trim();
      if (!text) return;
      if (!continuousConversation) {
        rec.stopContinuousRecognitionAsync(() => setMicActive(false), () => setMicActive(false));
      }
      onUserSpeechRef.current(text);
    };

    rec.startContinuousRecognitionAsync(
      () => setMicActive(true),
      (e: string) => { console.error('[STT] Start err:', e); setMicActive(false); },
    );
  }, [micActive, continuousConversation]);

  /* ---- expose handle ---- */
  useImperativeHandle(ref, () => ({
    speak,
    stopSpeaking,
    startSession: connectAvatar,
    closeSession,
    get sessionActive() { return sessionActiveRef.current; },
  }), [speak, stopSpeaking, connectAvatar, closeSession]);

  /* ---- render ---- */
  return (
    <div className="flex flex-col w-full">
      {/* Video area */}
      <div className="flex items-center justify-center p-4 relative max-h-[400px] overflow-hidden">
        <div
          ref={remoteVideoRef}
          className={`w-full rounded-xl overflow-hidden min-h-[200px] flex items-center justify-center ${isDarkMode ? 'bg-dark-bg/50' : 'bg-transparent'}`}
        >
          {isConnecting && (
            <div className="flex flex-col items-center space-y-3">
              <div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin" />
              <span className={`text-sm ${isDarkMode ? 'text-dark-muted' : 'text-gray-500'}`}>{t.avatarConnecting}</span>
            </div>
          )}
          {!isConnecting && !isSessionActive && statusMessage && (
            <div className={`text-sm ${isDarkMode ? 'text-dark-muted' : 'text-gray-400'}`}>{statusMessage}</div>
          )}
        </div>

        {/* Subtitles */}
        {subtitleText && (
          <div className="absolute bottom-8 left-0 right-0 text-center px-4">
            <span className="inline-block px-4 py-2 rounded-lg bg-black/60 text-white text-sm" style={{ textShadow: '1px 1px 2px rgba(0,0,0,0.8)' }}>
              {subtitleText}
            </span>
          </div>
        )}
      </div>

      {/* Controls */}
      {isSessionActive && (
        <div className={`flex items-center justify-center gap-2 px-3 pb-3 flex-wrap`}>
          <button
            onClick={toggleMicrophone}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              micActive ? 'bg-red-500 text-white animate-pulse' : 'bg-primary text-white hover:bg-primary-dark'
            }`}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 1a4 4 0 014 4v6a4 4 0 01-8 0V5a4 4 0 014-4z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 10v1a7 7 0 01-14 0v-1" />
              <line x1="12" y1="19" x2="12" y2="23" /><line x1="8" y1="23" x2="16" y2="23" />
            </svg>
            <span>{micActive ? t.avatarStopMic : t.avatarStartMic}</span>
          </button>

          <button
            onClick={stopSpeaking}
            disabled={!isSpeaking}
            title={t.avatarStopSpeaking}
            className={`p-2 rounded-lg text-xs font-medium transition-all disabled:opacity-40 ${isDarkMode ? 'bg-dark-card text-dark-text' : 'bg-gray-200 text-gray-700'}`}
          >
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
              <rect x="6" y="6" width="12" height="12" rx="2" />
            </svg>
          </button>

          <button
            onClick={closeSession}
            title={t.avatarCloseSession}
            className="p-2 rounded-lg text-xs font-medium bg-red-500/10 text-red-500 hover:bg-red-500/20 transition-all"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.68 9.27C5.34 7.61 7.62 6.5 10.12 6.5h3.76c2.5 0 4.78 1.11 6.44 2.77l.18.18a1.5 1.5 0 01.07 2.04l-1.88 2.18a1.5 1.5 0 01-2.07.2l-2.2-1.65a1.5 1.5 0 01-.57-1.37l.12-1.35h-3.94l.12 1.35a1.5 1.5 0 01-.57 1.37l-2.2 1.65a1.5 1.5 0 01-2.07-.2L3.43 11.5a1.5 1.5 0 01.07-2.04l.18-.18z" />
            </svg>
          </button>
        </div>
      )}
    </div>
  );
});

export default AvatarPanel;
