import React, { useEffect, useRef, useState } from 'react';
import { MessageSquareText, Send, Sparkles } from 'lucide-react';
import { LanguageDisplay, TranscriptMessage } from '../types';

interface TranscriptPaneProps {
  messages: TranscriptMessage[];
  isConnected: boolean;
  detectedLanguage: LanguageDisplay;
  onSendText: (text: string) => void;
}

function formatClock(ts: number): string {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export const TranscriptPane: React.FC<TranscriptPaneProps> = ({
  messages,
  isConnected,
  detectedLanguage,
  onSendText,
}) => {
  const [draft, setDraft] = useState('');
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!draft.trim() || !isConnected) return;
    onSendText(draft);
    setDraft('');
  };

  return (
    <section className="flex flex-col h-full min-h-0 overflow-hidden bg-[#FAF9F6] border-r border-[#E7E5E0] min-w-0">
      {/* Pane Header */}
      <div className="px-4 py-3 border-b border-[#ECEAE4] bg-white/70 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <MessageSquareText className="w-4 h-4 text-[#1B5E3F]" />
          <h2 className="text-xs font-semibold uppercase tracking-wider text-[#46524B]">
            Live Transcript
          </h2>
        </div>
        <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-[#F1F0EC] text-[#57635C]">
          {detectedLanguage.native}
        </span>
      </div>

      {/* Chat Bubbles */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3.5">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center px-6">
            <div className="w-11 h-11 rounded-2xl bg-[#EBF4EE] text-[#1B5E3F] flex items-center justify-center mb-3">
              <Sparkles className="w-5 h-5" />
            </div>
            <p className="text-sm font-medium text-[#2A352F]">
              Call script appears here live
            </p>
            <p className="text-xs text-[#78827C] mt-1 leading-relaxed max-w-[240px]">
              Agent messages appear on the left; your spoken replies appear on the right in their native script.
            </p>
          </div>
        ) : (
          messages.map((m) => {
            const isUser = m.role === 'user';
            return (
              <div
                key={m.id}
                className={`flex flex-col ${isUser ? 'items-end' : 'items-start'}`}
              >
                <div className="flex items-center gap-1.5 mb-1 px-1">
                  <span className="text-[10px] font-semibold uppercase tracking-wide text-[#75807A]">
                    {isUser ? 'Farmer (You)' : 'Kisan Sahayak'}
                  </span>
                  {m.language && (
                    <span className="text-[10px] px-1.5 py-0.2 rounded bg-[#EFEEEA] text-[#5B6660]">
                      {m.language.native}
                    </span>
                  )}
                  <span className="text-[10px] text-[#9AA39E]">
                    {formatClock(m.timestamp)}
                  </span>
                </div>

                <div
                  className={`max-w-[88%] rounded-2xl px-3.5 py-2.5 text-[13.5px] leading-relaxed shadow-[0_1px_2px_rgba(0,0,0,0.03)] ${
                    isUser
                      ? 'bg-[#1B5E3F] text-white rounded-br-sm'
                      : 'bg-white text-[#1D2621] border border-[#E7E5E0] rounded-bl-sm'
                  }`}
                >
                  <p className="whitespace-pre-wrap break-words">
                    {m.text || (m.streaming ? '...' : '')}
                    {m.streaming && (
                      <span className="inline-block w-1.5 h-3.5 ml-1 bg-[#1B5E3F]/50 animate-pulse align-middle rounded-xs" />
                    )}
                  </p>
                  {m.interrupted && (
                    <span className="inline-block mt-1.5 text-[10px] font-medium px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200/80">
                      Interrupted by caller
                    </span>
                  )}
                </div>
              </div>
            );
          })
        )}
        <div ref={bottomRef} />
      </div>

      {/* Optional Text Input Bar (works alongside live voice) */}
      <form
        onSubmit={handleSubmit}
        className="p-3 border-t border-[#ECEAE4] bg-white/80 flex items-center gap-2"
      >
        <input
          type="text"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          disabled={!isConnected}
          placeholder={
            isConnected
              ? 'Or type in any Indian language / English...'
              : 'Start call to speak or type...'
          }
          className="flex-1 bg-[#F8F7F4] border border-[#E5E2DC] focus:border-[#1B5E3F] rounded-xl px-3 py-2 text-xs text-[#1C2420] placeholder:text-[#98A09B] outline-none transition-colors disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={!isConnected || !draft.trim()}
          className="w-8 h-8 rounded-xl bg-[#1B5E3F] hover:bg-[#154C32] disabled:bg-[#D5D9D6] text-white flex items-center justify-center transition-colors cursor-pointer disabled:cursor-not-allowed"
          title="Send text turn"
        >
          <Send className="w-3.5 h-3.5" />
        </button>
      </form>
    </section>
  );
};
