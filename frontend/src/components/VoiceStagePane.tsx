import React from 'react';
import {
  AlertCircle,
  Hand,
  Mic,
  MicOff,
  PhoneIncoming,
  PhoneOff,
  PhoneOutgoing,
  ShieldCheck,
} from 'lucide-react';
import { AgentState, CallMode, SchemeRecommendation } from '../types';

interface VoiceStagePaneProps {
  isConnected: boolean;
  agentState: AgentState;
  callMode: CallMode;
  onCallModeChange: (mode: CallMode) => void;
  greetingLang: 'hi' | 'en';
  onGreetingLangChange: (lang: 'hi' | 'en') => void;
  isMuted: boolean;
  micError: string | null;
  audioLevel: number;
  callSeconds: number;
  recommendedSchemes: SchemeRecommendation[];
  onStartCall: () => void;
  onEndCall: () => void;
  onToggleMute: () => void;
  onInterrupt: () => void;
}

function formatTimer(totalSecs: number): string {
  const m = Math.floor(totalSecs / 60)
    .toString()
    .padStart(2, '0');
  const s = (totalSecs % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

const STATE_META: Record<
  AgentState,
  { label: string; sub: string; ringColor: string; coreColor: string; badgeClass: string }
> = {
  disconnected: {
    label: 'Ready for Web Call',
    sub: 'Click the mic button to start a live voice call',
    ringColor: 'rgba(27, 94, 63, 0.14)',
    coreColor: 'from-[#1F6A47] to-[#154A31]',
    badgeClass: 'bg-[#F0EFEA] text-[#5B6660]',
  },
  connecting: {
    label: 'Connecting...',
    sub: 'Initializing Silero VAD, Indic-Transcribe & Maya 2',
    ringColor: 'rgba(217, 119, 6, 0.20)',
    coreColor: 'from-amber-500 to-amber-600',
    badgeClass: 'bg-amber-50 text-amber-700',
  },
  idle: {
    label: 'Listening for you',
    sub: 'Speak naturally in any Indian language or English',
    ringColor: 'rgba(27, 94, 63, 0.18)',
    coreColor: 'from-[#1F6A47] to-[#154A31]',
    badgeClass: 'bg-[#EBF4EE] text-[#1B5E3F]',
  },
  listening: {
    label: 'Hearing Farmer...',
    sub: 'Silero VAD active — pause briefly when done',
    ringColor: 'rgba(16, 185, 129, 0.28)',
    coreColor: 'from-emerald-500 to-[#1B5E3F]',
    badgeClass: 'bg-emerald-50 text-emerald-700',
  },
  transcribing: {
    label: 'Understanding Speech...',
    sub: 'Bodhan AI Indic-Transcribe + Auto Language ID',
    ringColor: 'rgba(217, 119, 6, 0.24)',
    coreColor: 'from-amber-500 to-amber-600',
    badgeClass: 'bg-amber-50 text-amber-700',
  },
  thinking: {
    label: 'Preparing Reply...',
    sub: 'Qwen3.5-9B reasoning + live form extraction',
    ringColor: 'rgba(217, 119, 6, 0.26)',
    coreColor: 'from-amber-500 to-orange-600',
    badgeClass: 'bg-amber-50 text-amber-800',
  },
  speaking: {
    label: 'Kisan Sahayak Speaking',
    sub: 'Speak anytime to interrupt naturally (barge-in)',
    ringColor: 'rgba(27, 94, 63, 0.30)',
    coreColor: 'from-[#22734E] to-[#13462E]',
    badgeClass: 'bg-[#EBF4EE] text-[#1B5E3F]',
  },
};

export const VoiceStagePane: React.FC<VoiceStagePaneProps> = ({
  isConnected,
  agentState,
  callMode,
  onCallModeChange,
  greetingLang,
  onGreetingLangChange,
  isMuted,
  micError,
  audioLevel,
  callSeconds,
  recommendedSchemes,
  onStartCall,
  onEndCall,
  onToggleMute,
  onInterrupt,
}) => {
  const meta = STATE_META[agentState];
  const dynamicScale = 1 + Math.min(0.28, audioLevel * 0.35);

  return (
    <section className="flex flex-col h-full min-h-0 overflow-y-auto bg-[#F8F7F4] border-r border-[#E7E5E0] min-w-0 px-5 py-4 justify-between">
      {/* Top Call Mode Switcher */}
      <div className="flex flex-col items-center gap-2.5">
        <div className="inline-flex p-1 rounded-xl bg-[#ECEAE4] border border-[#E2DFD8]">
          <button
            type="button"
            disabled={isConnected}
            onClick={() => onCallModeChange('outbound')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer disabled:cursor-not-allowed ${
              callMode === 'outbound'
                ? 'bg-white text-[#1B5E3F] shadow-xs'
                : 'text-[#657069] hover:text-[#232F29]'
            }`}
          >
            <PhoneOutgoing className="w-3.5 h-3.5" />
            Agent Calls Farmer
          </button>
          <button
            type="button"
            disabled={isConnected}
            onClick={() => onCallModeChange('inbound')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer disabled:cursor-not-allowed ${
              callMode === 'inbound'
                ? 'bg-white text-[#1B5E3F] shadow-xs'
                : 'text-[#657069] hover:text-[#232F29]'
            }`}
          >
            <PhoneIncoming className="w-3.5 h-3.5" />
            Farmer Calls In
          </button>
        </div>

        {!isConnected && (
          <div className="flex items-center gap-2 text-[11px] text-[#6B7570]">
            <span>Greeting opener:</span>
            <button
              type="button"
              onClick={() => onGreetingLangChange('hi')}
              className={`px-2 py-0.5 rounded-md font-medium cursor-pointer transition-colors ${
                greetingLang === 'hi'
                  ? 'bg-[#EBF4EE] text-[#1B5E3F]'
                  : 'hover:bg-[#ECEAE4]'
              }`}
            >
              हिन्दी
            </button>
            <button
              type="button"
              onClick={() => onGreetingLangChange('en')}
              className={`px-2 py-0.5 rounded-md font-medium cursor-pointer transition-colors ${
                greetingLang === 'en'
                  ? 'bg-[#EBF4EE] text-[#1B5E3F]'
                  : 'hover:bg-[#ECEAE4]'
              }`}
            >
              English
            </button>
          </div>
        )}
      </div>

      {/* Center Interactive Voice Orb + Call Controls */}
      <div className="flex flex-col items-center justify-center my-4">
        {/* Status Pill & Timer */}
        <div className="flex items-center gap-2 mb-7">
          <span
            className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${meta.badgeClass}`}
          >
            {isConnected && (
              <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
            )}
            {meta.label}
          </span>
          {isConnected && (
            <span className="text-xs font-mono font-medium text-[#657069] px-2 py-1 rounded-full bg-white border border-[#E7E5E0]">
              {formatTimer(callSeconds)}
            </span>
          )}
        </div>

        {/* Audio-Reactive Voice Orb */}
        <div className="relative flex items-center justify-center w-48 h-48 mb-7">
          {/* Outer breathing halo */}
          <div
            className={`absolute inset-2 rounded-full transition-transform duration-150 ${
              isConnected ? 'animate-orb-breathe' : ''
            }`}
            style={{
              backgroundColor: meta.ringColor,
              transform: `scale(${dynamicScale * 1.12})`,
            }}
          />
          {/* Inner reactive ring */}
          <div
            className="absolute inset-6 rounded-full transition-transform duration-75"
            style={{
              backgroundColor: meta.ringColor,
              transform: `scale(${dynamicScale})`,
            }}
          />
          {/* Main clickable Orb / Mic Button */}
          <button
            type="button"
            onClick={isConnected ? onEndCall : onStartCall}
            className={`relative z-10 w-28 h-28 rounded-full bg-gradient-to-br ${
              isConnected ? meta.coreColor : 'from-[#1F6A47] to-[#14472F]'
            } text-white shadow-[0_12px_32px_rgba(27,94,63,0.28)] hover:shadow-[0_14px_38px_rgba(27,94,63,0.38)] active:scale-95 transition-all flex flex-col items-center justify-center gap-1 cursor-pointer group`}
            title={isConnected ? 'End Voice Call' : 'Start Web Voice Call'}
          >
            {isConnected ? (
              <>
                <Mic className="w-8 h-8 group-hover:hidden" />
                <PhoneOff className="w-8 h-8 hidden group-hover:block text-rose-100" />
                <span className="text-[11px] font-medium tracking-wide opacity-90 group-hover:hidden">
                  On Call
                </span>
                <span className="text-[11px] font-medium tracking-wide hidden group-hover:block text-rose-100">
                  End Call
                </span>
              </>
            ) : (
              <>
                <Mic className="w-8 h-8" />
                <span className="text-[11px] font-medium tracking-wide opacity-95">
                  Start Call
                </span>
              </>
            )}
          </button>
        </div>

        <p className="text-xs text-[#6B7570] text-center max-w-[260px] leading-relaxed">
          {meta.sub}
        </p>

        {/* Secondary Active Call Controls */}
        {isConnected && (
          <div className="flex items-center gap-2.5 mt-5">
            <button
              type="button"
              onClick={onToggleMute}
              className={`flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-medium border transition-colors cursor-pointer ${
                isMuted
                  ? 'bg-amber-50 border-amber-300 text-amber-800'
                  : 'bg-white border-[#E4E1DA] text-[#333E38] hover:bg-[#F2F1EC]'
              }`}
            >
              {isMuted ? <MicOff className="w-3.5 h-3.5" /> : <Mic className="w-3.5 h-3.5" />}
              {isMuted ? 'Unmute' : 'Mute'}
            </button>

            {agentState === 'speaking' && (
              <button
                type="button"
                onClick={onInterrupt}
                className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-medium bg-amber-50 border border-amber-200 text-amber-800 hover:bg-amber-100 transition-colors cursor-pointer"
              >
                <Hand className="w-3.5 h-3.5" />
                Interrupt
              </button>
            )}

            <button
              type="button"
              onClick={onEndCall}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-medium bg-rose-600 hover:bg-rose-700 text-white transition-colors cursor-pointer shadow-xs"
            >
              <PhoneOff className="w-3.5 h-3.5" />
              End
            </button>
          </div>
        )}

        {/* Mic Error Banner (e.g. insecure HTTP notice) */}
        {micError && (
          <div className="mt-4 w-full max-w-[320px] rounded-xl bg-amber-50 border border-amber-200 px-3 py-2.5 flex items-start gap-2 text-[11px] text-amber-900">
            <AlertCircle className="w-4 h-4 shrink-0 text-amber-600 mt-0.5" />
            <span>{micError}</span>
          </div>
        )}
      </div>

      {/* Bottom Dynamic Matched Schemes Strip */}
      <div className="bg-white rounded-2xl border border-[#E7E5E0] p-3.5 shadow-[0_1px_2px_rgba(0,0,0,0.02)]">
        <div className="flex items-center gap-1.5 mb-2">
          <ShieldCheck className="w-3.5 h-3.5 text-[#1B5E3F]" />
          <span className="text-[11px] font-semibold uppercase tracking-wider text-[#4F5B54]">
            Matched Agri-Credit Schemes
          </span>
        </div>
        <div className="space-y-2">
          {recommendedSchemes.slice(0, 3).map((s) => (
            <div
              key={s.id}
              className="rounded-xl bg-[#F8FAF8] border border-[#E2ECE5] px-3 py-2"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-semibold text-[#173D2B]">{s.name}</span>
                <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-md bg-[#E6F3EA] text-[#1B5E3F] shrink-0">
                  {s.badge}
                </span>
              </div>
              <p className="text-[11px] text-[#5C6A62] mt-0.5 leading-snug">{s.highlight}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};
