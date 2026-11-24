import React from 'react';
import { Globe, Sprout, Volume2 } from 'lucide-react';
import { HealthStatus, LanguageDisplay, VoiceOption } from '../types';

interface TopBarProps {
  health: HealthStatus;
  voices: VoiceOption[];
  selectedVoice: string;
  onVoiceChange: (voice: string) => void;
  languageMode: string;
  onLanguageModeChange: (lang: string) => void;
  detectedLanguage: LanguageDisplay;
  isConnected: boolean;
}

const LANG_OPTIONS = [
  { value: 'auto', label: 'Auto-Detect (12 Core Indic + EN)' },
  { value: 'auto_all', label: 'Auto-Detect (All 27 Indic Languages)' },
  { value: 'hi', label: 'Hindi — हिन्दी' },
  { value: 'en', label: 'English' },
  { value: 'mr', label: 'Marathi — मराठी' },
  { value: 'ta', label: 'Tamil — தமிழ்' },
  { value: 'te', label: 'Telugu — తెలుగు' },
  { value: 'bn', label: 'Bengali — বাংলা' },
  { value: 'gu', label: 'Gujarati — ગુજરાતી' },
  { value: 'kn', label: 'Kannada — ಕನ್ನಡ' },
  { value: 'ml', label: 'Malayalam — മലയാളം' },
  { value: 'pa', label: 'Punjabi — ਪੰਜਾਬੀ' },
  { value: 'or', label: 'Odia — ଓଡ଼ିଆ' },
  { value: 'as', label: 'Assamese — অসমীয়া' },
  { value: 'bho', label: 'Bhojpuri — भोजपुरी' },
  { value: 'hne', label: 'Chhattisgarhi — छत्तीसगढ़ी' },
  { value: 'bgc', label: 'Haryanvi — हरियाणवी' },
  { value: 'mai', label: 'Maithili — मैथिली' },
];

export const TopBar: React.FC<TopBarProps> = ({
  health,
  voices,
  selectedVoice,
  onVoiceChange,
  languageMode,
  onLanguageModeChange,
  detectedLanguage,
  isConnected,
}) => {
  const statusColor =
    health.status === 'ok'
      ? 'bg-emerald-500'
      : health.status === 'degraded'
        ? 'bg-amber-500'
        : 'bg-rose-500';

  const statusLabel =
    health.status === 'ok'
      ? 'All Models Ready'
      : health.status === 'degraded'
        ? 'Models Starting...'
        : 'Backend Offline';

  return (
    <header className="h-14 shrink-0 border-b border-[#E7E5E0] bg-white/90 backdrop-blur-sm px-5 flex items-center justify-between gap-4">
      {/* Brand */}
      <div className="flex items-center gap-2.5 min-w-0">
        <div className="w-8 h-8 rounded-xl bg-[#1B5E3F] text-white flex items-center justify-center shadow-xs">
          <Sprout className="w-4 h-4" />
        </div>
        <div className="leading-tight truncate">
          <div className="flex items-center gap-2">
            <h1 className="text-[15px] font-semibold tracking-tight text-[#16211C]">
              Kisan Sahayak
            </h1>
            <span className="hidden sm:inline-block text-[11px] font-medium px-2 py-0.5 rounded-full bg-[#EBF4EE] text-[#1B5E3F]">
              Agri-Credit Voice AI
            </span>
          </div>
          <p className="text-[11px] text-[#6B7570] hidden md:block">
            Indic-Transcribe · Qwen3.5-9B · Maya 2 Native · Silero VAD
          </p>
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-2.5">
        {/* Live Detected Language Pill */}
        {isConnected && (
          <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#F3F6F4] border border-[#DCE6DF] text-xs font-medium text-[#1B5E3F]">
            <span className="w-1.5 h-1.5 rounded-full bg-[#1B5E3F] animate-pulse" />
            <span>{detectedLanguage.label}</span>
          </div>
        )}

        {/* Language Selector */}
        <label className="flex items-center gap-1.5 bg-[#F8F7F4] border border-[#E5E2DC] rounded-lg px-2.5 py-1.5 text-xs text-[#3C4641]">
          <Globe className="w-3.5 h-3.5 text-[#6B7570] shrink-0" />
          <select
            value={languageMode}
            onChange={(e) => onLanguageModeChange(e.target.value)}
            className="bg-transparent outline-none font-medium text-[#1C2420] cursor-pointer max-w-[165px] truncate"
            title="Speech Recognition Language Mode"
          >
            {LANG_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>

        {/* Maya 2 Voice Selector */}
        <label className="hidden sm:flex items-center gap-1.5 bg-[#F8F7F4] border border-[#E5E2DC] rounded-lg px-2.5 py-1.5 text-xs text-[#3C4641]">
          <Volume2 className="w-3.5 h-3.5 text-[#6B7570] shrink-0" />
          <select
            value={selectedVoice}
            onChange={(e) => onVoiceChange(e.target.value)}
            className="bg-transparent outline-none font-medium text-[#1C2420] cursor-pointer"
            title="Maya 2 Native Voice"
          >
            {voices.map((v) => (
              <option key={v.id} value={v.id}>
                {v.label}
              </option>
            ))}
          </select>
        </label>

        {/* Model Stack Health Indicator */}
        <div
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-[#E7E5E0] bg-white text-[11px] font-medium text-[#4F5A54]"
          title={
            health.services
              ? `STT: ${health.services.stt_indic_transcribe.ok ? 'OK' : 'DOWN'} | LLM: ${health.services.llm_qwen35_9b.ok ? 'OK' : 'DOWN'} | TTS: ${health.services.tts_maya2_native.ok ? 'OK' : 'DOWN'}`
              : 'Checking model servers'
          }
        >
          <span className={`w-2 h-2 rounded-full ${statusColor}`} />
          <span className="hidden xl:inline">{statusLabel}</span>
        </div>
      </div>
    </header>
  );
};
