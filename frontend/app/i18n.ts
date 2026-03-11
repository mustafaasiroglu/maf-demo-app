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
