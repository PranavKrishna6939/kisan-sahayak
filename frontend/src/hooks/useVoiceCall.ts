import { useCallback, useEffect, useRef, useState } from 'react';
import {
  AgentState,
  CallMode,
  CompletionStats,
  EMPTY_APPLICATION,
  LanguageDisplay,
  LoanApplicationData,
  SchemeRecommendation,
  TranscriptMessage,
} from '../types';

interface UseVoiceCallReturn {
  isConnected: boolean;
  agentState: AgentState;
  sessionId: string | null;
  isMuted: boolean;
  micError: string | null;
  audioLevel: number;
  callSeconds: number;
  detectedLanguage: LanguageDisplay;
  messages: TranscriptMessage[];
  application: LoanApplicationData;
  highlightedFields: Record<string, number>;
  completion: CompletionStats;
  recommendedSchemes: SchemeRecommendation[];
  plainTextDoc: string;
  startCall: (opts: {
    mode: CallMode;
    voice: string;
    langMode: string;
    greetingLang: 'hi' | 'en';
  }) => Promise<void>;
  endCall: () => void;
  toggleMute: () => void;
  sendText: (text: string) => void;
  sendManualInterrupt: () => void;
  editFormField: (field: keyof LoanApplicationData, value: string) => void;
  updateLiveVoice: (voice: string) => void;
  updateLiveLanguageMode: (lang: string) => void;
  resetLocalForm: () => void;
}

const DEFAULT_LANG: LanguageDisplay = {
  code: 'hi',
  name: 'Hindi',
  native: 'हिन्दी',
  tts_lang: 'hi',
  label: 'Hindi (हिन्दी)',
};

const DEFAULT_COMPLETION: CompletionStats = {
  core_filled: 0,
  core_total: 20,
  total_filled: 0,
  total_fields: 40,
  percent: 0,
};

export function useVoiceCall(): UseVoiceCallReturn {
  const [isConnected, setIsConnected] = useState(false);
  const [agentState, setAgentState] = useState<AgentState>('disconnected');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isMuted, setIsMuted] = useState(false);
  const [micError, setMicError] = useState<string | null>(null);
  const [audioLevel, setAudioLevel] = useState(0);
  const [callSeconds, setCallSeconds] = useState(0);
  const [detectedLanguage, setDetectedLanguage] = useState<LanguageDisplay>(DEFAULT_LANG);
  const [messages, setMessages] = useState<TranscriptMessage[]>([]);
  const [application, setApplication] = useState<LoanApplicationData>(EMPTY_APPLICATION);
  const [highlightedFields, setHighlightedFields] = useState<Record<string, number>>({});
  const [completion, setCompletion] = useState<CompletionStats>(DEFAULT_COMPLETION);
  const [recommendedSchemes, setRecommendedSchemes] = useState<SchemeRecommendation[]>([
    {
      id: 'kcc-default',
      name: 'Kisan Credit Card (MISS 4%)',
      badge: '4% Effective Interest',
      highlight: '7% crop credit reduced to 4% on timely repayment; collateral-free up to ₹1.6–2 lakh.',
    },
  ]);
  const [plainTextDoc, setPlainTextDoc] = useState<string>(
    'Start a voice call with Kisan Sahayak — farmer loan application fields will appear here in real time.'
  );

  const wsRef = useRef<WebSocket | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const micStreamRef = useRef<MediaStream | null>(null);
  const micNodeRef = useRef<AudioWorkletNode | null>(null);
  const playbackNodeRef = useRef<AudioWorkletNode | null>(null);
  const timerRef = useRef<number | null>(null);
  const agentStateRef = useRef<AgentState>('disconnected');
  agentStateRef.current = agentState;

  const cleanupAudio = useCallback(() => {
    if (micNodeRef.current) {
      micNodeRef.current.disconnect();
      micNodeRef.current = null;
    }
    if (playbackNodeRef.current) {
      playbackNodeRef.current.disconnect();
      playbackNodeRef.current = null;
    }
    if (micStreamRef.current) {
      micStreamRef.current.getTracks().forEach((t) => t.stop());
      micStreamRef.current = null;
    }
    if (audioCtxRef.current) {
      audioCtxRef.current.close().catch(() => {});
      audioCtxRef.current = null;
    }
    setAudioLevel(0);
  }, []);

  const endCall = useCallback(() => {
    if (timerRef.current) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (wsRef.current) {
      try {
        wsRef.current.close();
      } catch {
        // ignore
      }
      wsRef.current = null;
    }
    cleanupAudio();
    setIsConnected(false);
    setAgentState('disconnected');
  }, [cleanupAudio]);

  useEffect(() => {
    return () => {
      endCall();
    };
  }, [endCall]);

  const flushPlayback = useCallback(() => {
    if (playbackNodeRef.current) {
      playbackNodeRef.current.port.postMessage({ type: 'flush' });
    }
  }, []);

  const startCall = useCallback(
    async ({
      mode,
      voice,
      langMode,
      greetingLang,
    }: {
      mode: CallMode;
      voice: string;
      langMode: string;
      greetingLang: 'hi' | 'en';
    }) => {
      endCall();
      setMicError(null);
      setMessages([]);
      setApplication(EMPTY_APPLICATION);
      setCompletion(DEFAULT_COMPLETION);
      setHighlightedFields({});
      setCallSeconds(0);
      setIsMuted(false);
      setAgentState('connecting');

      // 1. Setup AudioContext & AudioWorklets (playback + mic capture)
      const ctx = new AudioContext();
      audioCtxRef.current = ctx;
      if (ctx.state === 'suspended') {
        await ctx.resume();
      }

      try {
        await ctx.audioWorklet.addModule('/audio/playback-processor.js');
        const playNode = new AudioWorkletNode(ctx, 'pcm-playback-processor', {
          numberOfInputs: 0,
          numberOfOutputs: 1,
          outputChannelCount: [2],
        });
        playNode.connect(ctx.destination);
        playNode.port.onmessage = (ev) => {
          if (ev.data?.type === 'level' && agentStateRef.current === 'speaking') {
            setAudioLevel(Math.min(1, ev.data.rms * 4.5));
          }
        };
        playbackNodeRef.current = playNode;
      } catch (err) {
        console.error('Playback worklet init failed:', err);
      }

      // Capture mic with browser-native Acoustic Echo Cancellation (AEC)
      let micNode: AudioWorkletNode | null = null;
      if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        try {
          const stream = await navigator.mediaDevices.getUserMedia({
            audio: {
              echoCancellation: true,
              noiseSuppression: true,
              autoGainControl: true,
              channelCount: 1,
            },
          });
          micStreamRef.current = stream;
          await ctx.audioWorklet.addModule('/audio/mic-processor.js');
          const source = ctx.createMediaStreamSource(stream);
          micNode = new AudioWorkletNode(ctx, 'mic-capture-processor');
          // Connect through zero-gain node so worklet stays active without echoing mic locally
          const silentGain = ctx.createGain();
          silentGain.gain.value = 0;
          source.connect(micNode);
          micNode.connect(silentGain);
          silentGain.connect(ctx.destination);
          micNodeRef.current = micNode;
        } catch (err: unknown) {
          const msg =
            err instanceof Error
              ? err.message
              : 'Microphone access denied. Use HTTPS or localhost SSH tunnel, or type in the transcript box.';
          setMicError(msg);
        }
      } else {
        setMicError(
          'Browser blocked microphone on insecure HTTP. Open over HTTPS (port 8091) or localhost via SSH tunnel. Text input still works!'
        );
      }

      // 2. Open WebSocket to Pipecat backend
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const params = new URLSearchParams({
        mode,
        voice,
        lang: langMode,
        greeting_lang: greetingLang,
      });
      const ws = new WebSocket(`${proto}://${window.location.host}/ws/call?${params.toString()}`);
      ws.binaryType = 'arraybuffer';
      wsRef.current = ws;

      if (micNode) {
        micNode.port.onmessage = (ev) => {
          const d = ev.data;
          if (!d) return;
          if (d.type === 'audio') {
            if (agentStateRef.current !== 'speaking') {
              setAudioLevel(Math.min(1, d.rms * 5.0));
            }
            if (ws.readyState === WebSocket.OPEN) {
              ws.send(d.pcm);
            }
          } else if (d.type === 'level') {
            if (agentStateRef.current !== 'speaking') {
              setAudioLevel(0);
            }
          }
        };
      }

      ws.onopen = () => {
        setIsConnected(true);
        setAgentState('idle');
        timerRef.current = window.setInterval(() => {
          setCallSeconds((s) => s + 1);
        }, 1000);
      };

      ws.onmessage = (event) => {
        if (event.data instanceof ArrayBuffer) {
          if (audioCtxRef.current && audioCtxRef.current.state === 'suspended') {
            audioCtxRef.current.resume().catch(() => {});
          }
          if (playbackNodeRef.current) {
            playbackNodeRef.current.port.postMessage(
              { type: 'pcm', buffer: event.data },
              [event.data]
            );
          }
          return;
        }

        if (typeof event.data === 'string') {
          try {
            const msg = JSON.parse(event.data);
            switch (msg.type) {
              case 'session_init':
                setSessionId(msg.session_id);
                if (msg.detected_language) setDetectedLanguage(msg.detected_language);
                if (msg.application) setApplication(msg.application);
                if (msg.completion) setCompletion(msg.completion);
                if (msg.recommended_schemes) setRecommendedSchemes(msg.recommended_schemes);
                if (msg.plain_text) setPlainTextDoc(msg.plain_text);
                break;

              case 'interrupt':
                flushPlayback();
                setAudioLevel(0);
                if (micNodeRef.current) {
                  micNodeRef.current.port.postMessage({ botSpeaking: false });
                }
                setMessages((prev) =>
                  prev.filter((m) => !(m.streaming && m.text.trim() === ''))
                );
                break;

              case 'state':
                setAgentState(msg.state as AgentState);
                if (micNodeRef.current) {
                  if (msg.state === 'speaking') {
                    micNodeRef.current.port.postMessage({ botSpeaking: true });
                  } else if (msg.state === 'idle') {
                    // Brief 350ms tail hold so residual speaker output doesn't echo back into VAD
                    window.setTimeout(() => {
                      if (micNodeRef.current && agentStateRef.current !== 'speaking') {
                        micNodeRef.current.port.postMessage({ botSpeaking: false });
                      }
                    }, 350);
                  }
                }
                if (msg.state === 'idle') setAudioLevel(0);
                break;

              case 'language_detected':
                if (msg.language) setDetectedLanguage(msg.language);
                break;

              case 'transcript':
                if (msg.message) {
                  setMessages((prev) => {
                    if (prev.some((m) => m.id === msg.message.id)) return prev;
                    return [...prev, msg.message];
                  });
                }
                break;

              case 'transcript_start':
                setMessages((prev) => [
                  ...prev,
                  {
                    id: msg.id,
                    role: 'assistant',
                    text: '',
                    timestamp: Date.now() / 1000,
                    streaming: true,
                  },
                ]);
                break;

              case 'transcript_delta':
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === msg.id ? { ...m, text: m.text + (msg.delta || '') } : m
                  )
                );
                break;

              case 'transcript_done':
                if (msg.message) {
                  setMessages((prev) => {
                    const exists = prev.some((m) => m.id === msg.message.id);
                    if (exists) {
                      return prev.map((m) =>
                        m.id === msg.message.id
                          ? { ...msg.message, streaming: false }
                          : m
                      );
                    }
                    return [...prev, { ...msg.message, streaming: false }];
                  });
                }
                break;

              case 'form_update':
                if (msg.application) setApplication(msg.application);
                if (msg.completion) setCompletion(msg.completion);
                if (msg.recommended_schemes) setRecommendedSchemes(msg.recommended_schemes);
                if (msg.plain_text) setPlainTextDoc(msg.plain_text);
                if (Array.isArray(msg.changed_fields) && msg.changed_fields.length > 0) {
                  const now = Date.now();
                  setHighlightedFields((prev) => {
                    const next = { ...prev };
                    for (const f of msg.changed_fields) next[f] = now;
                    return next;
                  });
                }
                break;
            }
          } catch (err) {
            console.warn('Invalid WS JSON:', err);
          }
        }
      };

      ws.onclose = () => {
        endCall();
      };

      ws.onerror = () => {
        setMicError('WebSocket connection error. Verify the backend is running.');
      };
    },
    [endCall, flushPlayback]
  );

  const toggleMute = useCallback(() => {
    setIsMuted((prev) => {
      const next = !prev;
      if (micNodeRef.current) {
        micNodeRef.current.port.postMessage({ muted: next });
      }
      return next;
    });
  }, []);

  const sendText = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
      flushPlayback();
      wsRef.current.send(JSON.stringify({ type: 'text_input', text: trimmed }));
    },
    [flushPlayback]
  );

  const sendManualInterrupt = useCallback(() => {
    flushPlayback();
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'interrupt' }));
    }
  }, [flushPlayback]);

  const editFormField = useCallback((field: keyof LoanApplicationData, value: string) => {
    setApplication((prev) => ({ ...prev, [field]: value || null }));
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({ type: 'manual_form_edit', field, value })
      );
    }
  }, []);

  const updateLiveVoice = useCallback((voice: string) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'set_voice', voice }));
    }
  }, []);

  const updateLiveLanguageMode = useCallback((lang: string) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'set_language', language: lang }));
    }
  }, []);

  const resetLocalForm = useCallback(() => {
    setApplication(EMPTY_APPLICATION);
    setCompletion(DEFAULT_COMPLETION);
    setHighlightedFields({});
  }, []);

  return {
    isConnected,
    agentState,
    sessionId,
    isMuted,
    micError,
    audioLevel,
    callSeconds,
    detectedLanguage,
    messages,
    application,
    highlightedFields,
    completion,
    recommendedSchemes,
    plainTextDoc,
    startCall,
    endCall,
    toggleMute,
    sendText,
    sendManualInterrupt,
    editFormField,
    updateLiveVoice,
    updateLiveLanguageMode,
    resetLocalForm,
  };
}
