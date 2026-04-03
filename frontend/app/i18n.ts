export type Language = 'tr' | 'en';

export interface Translations {
  // Header
  headerTitle: string;
  headerSubtitle: string;

  // Settings panel
  settingsTitle: string;
  piiMaskingLabel: string;
  piiMaskingToggle: string;
  llmModelLabel: string;
  themeLabel: string;
  themeLight: string;
  themeDark: string;
  colorLabel: string;
  colorGreen: string;
  colorRed: string;
  colorNavy: string;
  colorGray: string;
  languageLabel: string;

  // Welcome screen
  welcomeTitle: string;
  welcomeSubtitle: string;
  exampleQuestions: string[];

  // Input
  inputPlaceholder: string;

  // Errors
  errorGeneric: string;
  errorWithRetry: string;

  // Tool calls
  toolRunning: string;
  toolCompleted: string;

  // Message actions
  actionCopy: string;
  actionLike: string;
  actionDislike: string;
  actionReadAloud: string;
  actionShowDetails: string;
  actionHideDetails: string;

  // Avatar page
  avatarSubtitle: string;
  avatarConfigTitle: string;
  avatarRegionLabel: string;
  avatarApiKeyLabel: string;
  avatarTtsVoiceLabel: string;
  avatarVoiceLabel: string;
  avatarCharacterLabel: string;
  avatarStyleLabel: string;
  avatarSttLocalesLabel: string;
  avatarShowSubtitles: string;
  avatarContinuousConversation: string;
  avatarUsePhotoAvatar: string;
  avatarOpenSession: string;
  avatarCloseSession: string;
  avatarStartMic: string;
  avatarStopMic: string;
  avatarStopSpeaking: string;
  avatarClearHistory: string;
  avatarConnecting: string;
  avatarSessionActive: string;
  avatarSessionClosed: string;
  avatarReconnecting: string;
  avatarTypeMessage: string;
  avatarBackToChat: string;
  avatarNavLabel: string;

  // Debug panel
  debugResponseTimeline: string;
  debugAgent: string;
  debugStep: string;
  debugTimeline: string;
  debugDuration: string;
  debugTotalRequestDuration: string;
  debugTTFT: string;
  debugRequestInput: string;
  debugRequestOutput: string;
  debugRequestDetails: string;
  debugStart: string;
  debugEnd: string;
}

const tr: Translations = {
  headerTitle: 'Investing Agent',
  headerSubtitle: 'Fon Yatırım Asistanı',

  settingsTitle: 'Test Settings',
  piiMaskingLabel: 'PII Masking',
  piiMaskingToggle: 'Mask PII Data',
  llmModelLabel: 'LLM Model',
  themeLabel: 'Theme',
  themeLight: 'Light',
  themeDark: 'Dark',
  colorLabel: 'Renk Teması',
  colorGreen: 'Yeşil',
  colorRed: 'Kırmızı',
  colorNavy: 'Lacivert',
  colorGray: 'Koyu Gri',
  languageLabel: 'Language',

  welcomeTitle: 'Hoş Geldiniz!',
  welcomeSubtitle: 'Size nasıl yardımcı olabilirim? İşte bazı örnek sorular:',
  exampleQuestions: [
    'GTA fonu nedir? Dağılımı nasıl?',
    'Getirisi en yüksek fonlar hangileri?',
    'GOL, GTZ fonlarının son 1 ay getirisi kıyaslar mısın?',
    'Ben kimim?',
  ],

  inputPlaceholder: 'Size nasıl yardımcı olabilirim?',

  errorGeneric: 'Bir hata oluştu.',
  errorWithRetry: 'Üzgünüm, bir hata oluştu. Lütfen tekrar deneyin.',

  toolRunning: 'Çalışıyor...',
  toolCompleted: 'Tamamlandı',

  actionCopy: 'Kopyala',
  actionLike: 'Beğen',
  actionDislike: 'Beğenme',
  actionReadAloud: 'Sesli oku',
  actionShowDetails: 'Detayları Göster',
  actionHideDetails: 'Detayları Gizle',

  avatarSubtitle: 'Sesli & Görüntülü Asistan',
  avatarConfigTitle: 'Avatar Ayarları',
  avatarRegionLabel: 'Azure Speech Bölge',
  avatarApiKeyLabel: 'API Anahtarı',
  avatarTtsVoiceLabel: 'TTS Sesi',
  avatarVoiceLabel: 'Avatar Sesi',
  avatarCharacterLabel: 'Avatar Karakter',
  avatarStyleLabel: 'Avatar Stil',
  avatarSttLocalesLabel: 'STT Dilleri',
  avatarShowSubtitles: 'Altyazıları Göster',
  avatarContinuousConversation: 'Sürekli Konuşma',
  avatarUsePhotoAvatar: 'Photo Avatar Kullan',
  avatarOpenSession: 'Avatar Oturumu Aç',
  avatarCloseSession: 'Avatar Oturumu Kapat',
  avatarStartMic: 'Mikrofonu Başlat',
  avatarStopMic: 'Mikrofonu Durdur',
  avatarStopSpeaking: 'Konuşmayı Durdur',
  avatarClearHistory: 'Sohbeti Temizle',
  avatarConnecting: 'Bağlanıyor...',
  avatarSessionActive: 'Oturum Aktif',
  avatarSessionClosed: 'Oturum Kapalı',
  avatarReconnecting: 'Yeniden bağlanılıyor...',
  avatarTypeMessage: 'Mesaj Yaz',
  avatarBackToChat: 'Yazılı Sohbete Dön',
  avatarNavLabel: 'Avatar Asistan',

  debugResponseTimeline: 'Response Timeline:',
  debugAgent: 'Agent',
  debugStep: 'Step',
  debugTimeline: 'Timeline',
  debugDuration: 'Duration',
  debugTotalRequestDuration: 'Total Request Duration:',
  debugTTFT: 'Time to First Token (Frontend):',
  debugRequestInput: 'Request Input',
  debugRequestOutput: 'Request Output',
  debugRequestDetails: 'Request Details',
  debugStart: 'Start',
  debugEnd: 'End',
};

const en: Translations = {
  headerTitle: 'Investing Agent',
  headerSubtitle: 'Fund Investment Assistant',

  settingsTitle: 'Test Settings',
  piiMaskingLabel: 'PII Masking',
  piiMaskingToggle: 'Mask PII Data',
  llmModelLabel: 'LLM Model',
  themeLabel: 'Theme',
  themeLight: 'Light',
  themeDark: 'Dark',
  colorLabel: 'Color Theme',
  colorGreen: 'Green',
  colorRed: 'Red',
  colorNavy: 'Navy',
  colorGray: 'Dark Gray',
  languageLabel: 'Language',

  welcomeTitle: 'Welcome!',
  welcomeSubtitle: 'How can I help you? Here are some example questions:',
  exampleQuestions: [
    'What is the GTA fund? What is its distribution?',
    'Which funds have the highest returns?',
    'Can you compare the 1-month returns of GOL and GTZ funds?',
    'Who am I?',
  ],

  inputPlaceholder: 'How can I help you?',

  errorGeneric: 'An error occurred.',
  errorWithRetry: 'Sorry, an error occurred. Please try again.',

  toolRunning: 'Running...',
  toolCompleted: 'Completed',

  actionCopy: 'Copy',
  actionLike: 'Like',
  actionDislike: 'Dislike',
  actionReadAloud: 'Read aloud',
  actionShowDetails: 'Show Details',
  actionHideDetails: 'Hide Details',

  avatarSubtitle: 'Voice & Video Assistant',
  avatarConfigTitle: 'Avatar Settings',
  avatarRegionLabel: 'Azure Speech Region',
  avatarApiKeyLabel: 'API Key',
  avatarTtsVoiceLabel: 'TTS Voice',
  avatarVoiceLabel: 'Avatar Voice',
  avatarCharacterLabel: 'Avatar Character',
  avatarStyleLabel: 'Avatar Style',
  avatarSttLocalesLabel: 'STT Locales',
  avatarShowSubtitles: 'Show Subtitles',
  avatarContinuousConversation: 'Continuous Conversation',
  avatarUsePhotoAvatar: 'Use Photo Avatar',
  avatarOpenSession: 'Open Avatar Session',
  avatarCloseSession: 'Close Avatar Session',
  avatarStartMic: 'Start Microphone',
  avatarStopMic: 'Stop Microphone',
  avatarStopSpeaking: 'Stop Speaking',
  avatarClearHistory: 'Clear Chat',
  avatarConnecting: 'Connecting...',
  avatarSessionActive: 'Session Active',
  avatarSessionClosed: 'Session Closed',
  avatarReconnecting: 'Reconnecting...',
  avatarTypeMessage: 'Type Message',
  avatarBackToChat: 'Back to Text Chat',
  avatarNavLabel: 'Avatar Assistant',

  debugResponseTimeline: 'Response Timeline:',
  debugAgent: 'Agent',
  debugStep: 'Step',
  debugTimeline: 'Timeline',
  debugDuration: 'Duration',
  debugTotalRequestDuration: 'Total Request Duration:',
  debugTTFT: 'Time to First Token (Frontend):',
  debugRequestInput: 'Request Input',
  debugRequestOutput: 'Request Output',
  debugRequestDetails: 'Request Details',
  debugStart: 'Start',
  debugEnd: 'End',
};

export const translations: Record<Language, Translations> = { tr, en };

export function getTranslations(lang: Language): Translations {
  return translations[lang];
}
