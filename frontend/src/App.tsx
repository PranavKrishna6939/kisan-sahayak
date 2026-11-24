import React, { useEffect, useState } from 'react';
import { TopBar } from './components/TopBar';
import { TranscriptPane } from './components/TranscriptPane';
import { VoiceStagePane } from './components/VoiceStagePane';
import { LoanFormPane } from './components/LoanFormPane';
import { useVoiceCall } from './hooks/useVoiceCall';
import { CallMode, HealthStatus, VoiceOption } from './types';

const DEFAULT_VOICES: VoiceOption[] = [
  { id: 'Vaidehi', label: 'Vaidehi (Calm Female)', gender: 'female', style: 'Warm, calm, gentle' },
  { id: 'Jahnavi', label: 'Jahnavi (Friendly Female)', gender: 'female', style: 'Warm, friendly' },
  { id: 'Ahana', label: 'Ahana (Bright Female)', gender: 'female', style: 'Bright, youthful' },
  { id: 'Satvik', label: 'Satvik (Friendly Male)', gender: 'male', style: 'Warm, approachable' },
  { id: 'Siddhant', label: 'Siddhant (Clear Male)', gender: 'male', style: 'Clear, professional' },
  { id: 'Vasant', label: 'Vasant (Mature Male)', gender: 'male', style: 'Steady, reassuring' },
];

export const App: React.FC = () => {
  const [callMode, setCallMode] = useState<CallMode>('outbound');
  const [greetingLang, setGreetingLang] = useState<'hi' | 'en'>('hi');
  const [selectedVoice, setSelectedVoice] = useState<string>('Vaidehi');
  const [languageMode, setLanguageMode] = useState<string>('auto');
  const [voices, setVoices] = useState<VoiceOption[]>(DEFAULT_VOICES);
  const [health, setHealth] = useState<HealthStatus>({ status: 'degraded' });

  const call = useVoiceCall();

  useEffect(() => {
    let active = true;
    const fetchMeta = async () => {
      try {
        const res = await fetch('/api/config');
        if (res.ok && active) {
          const data = await res.json();
          if (Array.isArray(data.voices) && data.voices.length > 0) {
            setVoices(data.voices);
          }
        }
      } catch {
        // fallback defaults
      }
    };
    const fetchHealth = async () => {
      try {
        const res = await fetch('/api/health');
        if (res.ok && active) {
          setHealth(await res.json());
        } else if (active) {
          setHealth({ status: 'offline' });
        }
      } catch {
        if (active) setHealth({ status: 'offline' });
      }
    };

    fetchMeta();
    fetchHealth();
    const id = window.setInterval(fetchHealth, 12000);
    return () => {
      active = false;
      window.clearInterval(id);
    };
  }, []);

  const handleVoiceChange = (voice: string) => {
    setSelectedVoice(voice);
    call.updateLiveVoice(voice);
  };

  const handleLanguageChange = (lang: string) => {
    setLanguageMode(lang);
    call.updateLiveLanguageMode(lang);
  };

  const handleStartCall = () => {
    call.startCall({
      mode: callMode,
      voice: selectedVoice,
      langMode: languageMode,
      greetingLang,
    });
  };

  return (
    <div className="h-screen w-screen overflow-hidden flex flex-col bg-[#F8F7F4]">
      <TopBar
        health={health}
        voices={voices}
        selectedVoice={selectedVoice}
        onVoiceChange={handleVoiceChange}
        languageMode={languageMode}
        onLanguageModeChange={handleLanguageChange}
        detectedLanguage={call.detectedLanguage}
        isConnected={call.isConnected}
      />

      {/* Minimal 3-Pane Split Workspace */}
      <main className="flex-1 min-h-0 overflow-hidden grid grid-cols-1 lg:grid-cols-[34%_30%_36%] lg:grid-rows-[minmax(0,1fr)]">
        {/* Pane 1 (Left): Live Call Transcript */}
        <TranscriptPane
          messages={call.messages}
          isConnected={call.isConnected}
          detectedLanguage={call.detectedLanguage}
          onSendText={call.sendText}
        />

        {/* Pane 2 (Center): Web Voice Call Stage */}
        <VoiceStagePane
          isConnected={call.isConnected}
          agentState={call.agentState}
          callMode={callMode}
          onCallModeChange={setCallMode}
          greetingLang={greetingLang}
          onGreetingLangChange={setGreetingLang}
          isMuted={call.isMuted}
          micError={call.micError}
          audioLevel={call.audioLevel}
          callSeconds={call.callSeconds}
          recommendedSchemes={call.recommendedSchemes}
          onStartCall={handleStartCall}
          onEndCall={call.endCall}
          onToggleMute={call.toggleMute}
          onInterrupt={call.sendManualInterrupt}
        />

        {/* Pane 3 (Right): Real-Time Loan Application Form */}
        <LoanFormPane
          application={call.application}
          highlightedFields={call.highlightedFields}
          completion={call.completion}
          plainTextDoc={call.plainTextDoc}
          sessionId={call.sessionId}
          onEditField={call.editFormField}
        />
      </main>
    </div>
  );
};

export default App;
