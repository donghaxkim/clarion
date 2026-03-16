'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Mic, MicOff } from 'lucide-react';

import { AgentOrb } from '@/components/agent/AgentOrb';
import { editSection, getVoiceSessionConfig } from '@/lib/api';
import type { ReportSection } from '@/lib/types';
import type {
  VoiceEditProposalEvent,
  VoiceOrbState,
  VoiceServerEvent,
} from '@/lib/voice';

interface FocusRequest {
  nonce: number;
  section: ReportSection;
}

interface ReportVoiceAssistantProps {
  caseId: string;
  reportId: string | null;
  enabled: boolean;
  sections: ReportSection[];
  focusRequest: FocusRequest | null;
  onFocusChange: (sectionId: string | null) => void;
  onNavigateSection: (sectionId: string) => void;
  onNavigateEntity: (entityIdOrName: string) => void;
  onNavigateEvidence: (evidenceId: string) => void;
  onReportUpdated: () => Promise<void>;
}

type RawVoiceState = Exclude<VoiceOrbState, 'awaiting_confirm'>;

interface RecorderRefs {
  stream: MediaStream;
  context: AudioContext;
  source: MediaStreamAudioSourceNode;
  processor: ScriptProcessorNode;
  sink: GainNode;
}

export function ReportVoiceAssistant({
  caseId,
  reportId,
  enabled,
  sections,
  focusRequest,
  onFocusChange,
  onNavigateSection,
  onNavigateEntity,
  onNavigateEvidence,
  onReportUpdated,
}: ReportVoiceAssistantProps) {
  const [rawState, setRawState] = useState<RawVoiceState>('disconnected');
  const [focusedSectionId, setFocusedSectionId] = useState<string | null>(null);
  const [pendingProposal, setPendingProposal] = useState<VoiceEditProposalEvent | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isApplyingEdit, setIsApplyingEdit] = useState(false);

  const socketRef = useRef<WebSocket | null>(null);
  const connectPromiseRef = useRef<Promise<WebSocket> | null>(null);
  const wsBaseUrlRef = useRef<string | null>(null);
  const sessionReadyRef = useRef(false);
  const recorderRef = useRef<RecorderRefs | null>(null);
  const playbackContextRef = useRef<AudioContext | null>(null);
  const nextPlaybackTimeRef = useRef(0);
  const lastFocusNonceRef = useRef<number | null>(null);
  const unmountedRef = useRef(false);

  const focusedSection = useMemo(
    () => sections.find((section) => section.id === focusedSectionId) ?? null,
    [focusedSectionId, sections]
  );
  const orbState: VoiceOrbState = pendingProposal ? 'awaiting_confirm' : rawState;

  const closeSocket = useCallback(() => {
    connectPromiseRef.current = null;
    sessionReadyRef.current = false;
    const socket = socketRef.current;
    socketRef.current = null;
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.close(1000, 'component cleanup');
    } else if (socket && socket.readyState === WebSocket.CONNECTING) {
      socket.close();
    }
  }, []);

  const stopCapture = useCallback(async (sendAudioEnd: boolean) => {
    const recorder = recorderRef.current;
    recorderRef.current = null;
    if (!recorder) {
      if (sendAudioEnd && socketRef.current?.readyState === WebSocket.OPEN) {
        sendSocketMessage(socketRef.current, { type: 'audio_end' });
      }
      return;
    }

    recorder.processor.disconnect();
    recorder.source.disconnect();
    recorder.sink.disconnect();
    for (const track of recorder.stream.getTracks()) {
      track.stop();
    }
    await recorder.context.close();

    if (sendAudioEnd && socketRef.current?.readyState === WebSocket.OPEN) {
      sendSocketMessage(socketRef.current, { type: 'audio_end' });
    }
  }, []);

  const closePlayback = useCallback(async () => {
    nextPlaybackTimeRef.current = 0;
    if (playbackContextRef.current) {
      const context = playbackContextRef.current;
      playbackContextRef.current = null;
      await context.close();
    }
  }, []);

  useEffect(() => {
    return () => {
      unmountedRef.current = true;
      void stopCapture(false);
      void closePlayback();
      closeSocket();
    };
  }, [closePlayback, closeSocket, stopCapture]);

  useEffect(() => {
    if (!enabled) {
      setPendingProposal(null);
      setErrorMessage(null);
      setRawState('disconnected');
      setFocusedSectionId(null);
      onFocusChange(null);
      void stopCapture(false);
      closeSocket();
    }
  }, [closeSocket, enabled, onFocusChange, stopCapture]);

  const ensureWebSocketBaseUrl = useCallback(async () => {
    if (wsBaseUrlRef.current) {
      return wsBaseUrlRef.current;
    }
    const config = await getVoiceSessionConfig();
    wsBaseUrlRef.current = config.websocket_base_url.replace(/\/$/, '');
    return wsBaseUrlRef.current;
  }, []);

  const handleServerEvent = useCallback(
    (event: VoiceServerEvent) => {
      switch (event.type) {
        case 'state':
          if (event.value === 'idle') {
            sessionReadyRef.current = true;
          }
          setRawState(event.value);
          if (event.value !== 'error') {
            setErrorMessage(null);
          }
          return;
        case 'audio_chunk':
          void enqueueAudioChunk(
            event.data,
            event.mime_type,
            playbackContextRef,
            nextPlaybackTimeRef,
          );
          return;
        case 'audio_end':
          return;
        case 'navigate':
          if (event.target === 'section') {
            onNavigateSection(event.id);
          } else if (event.target === 'entity') {
            onNavigateEntity(event.id);
          } else if (event.target === 'evidence') {
            onNavigateEvidence(event.id);
          }
          return;
        case 'edit_proposal':
          setPendingProposal(event);
          setFocusedSectionId(event.section_id);
          onFocusChange(event.section_id);
          return;
        case 'edit_applied':
        case 'edit_cancelled':
          setPendingProposal(null);
          return;
        case 'error':
          setRawState('error');
          setErrorMessage(event.message);
          return;
      }
    },
    [onFocusChange, onNavigateEntity, onNavigateEvidence, onNavigateSection]
  );

  const connectSocket = useCallback(async (): Promise<WebSocket> => {
    if (!enabled || !reportId) {
      throw new Error('Voice is available after the report finishes generating.');
    }

    const existing = socketRef.current;
    if (existing && existing.readyState === WebSocket.OPEN && sessionReadyRef.current) {
      return existing;
    }
    if (connectPromiseRef.current) {
      return connectPromiseRef.current;
    }

    sessionReadyRef.current = false;
    setRawState('connecting');
    const connectPromise = (async () => {
      const baseUrl = await ensureWebSocketBaseUrl();
      const socket = new WebSocket(`${baseUrl}/voice/ws/${encodeURIComponent(reportId)}`);
      socketRef.current = socket;

      return await new Promise<WebSocket>((resolve, reject) => {
        const timeoutId = window.setTimeout(() => {
          if (socket.readyState !== WebSocket.OPEN) {
            reject(new Error('Voice connection timed out.'));
          } else if (!sessionReadyRef.current) {
            reject(new Error('Voice session did not become ready in time.'));
          }
        }, 5000);

        socket.onopen = () => undefined;

        socket.onmessage = (message) => {
          try {
            const event = JSON.parse(message.data) as VoiceServerEvent;
            if (event.type === 'state' && event.value === 'idle' && !sessionReadyRef.current) {
              window.clearTimeout(timeoutId);
              sessionReadyRef.current = true;
              if (focusedSectionId) {
                sendSocketMessage(socket, {
                  type: 'context_update',
                  focused_section_id: focusedSectionId,
                });
              }
              resolve(socket);
            } else if (event.type === 'error' && !sessionReadyRef.current) {
              window.clearTimeout(timeoutId);
              reject(new Error(event.message || 'Unable to start the voice session.'));
            }
            handleServerEvent(event);
          } catch (error) {
            console.error('Unable to parse voice event', error);
          }
        };

        socket.onerror = () => {
          setRawState('error');
          setErrorMessage('Unable to connect to the voice session.');
        };

        socket.onclose = () => {
          window.clearTimeout(timeoutId);
          connectPromiseRef.current = null;
          socketRef.current = null;
          sessionReadyRef.current = false;
          if (!unmountedRef.current) {
            setRawState('disconnected');
          }
          reject(new Error('Voice session closed.'));
        };
      });
    })();

    connectPromiseRef.current = connectPromise;
    try {
      return await connectPromise;
    } catch (error) {
      connectPromiseRef.current = null;
      socketRef.current = null;
      setRawState('error');
      setErrorMessage(
        error instanceof Error ? error.message : 'Unable to connect to the voice session.'
      );
      throw error;
    }
  }, [enabled, ensureWebSocketBaseUrl, focusedSectionId, handleServerEvent, reportId]);

  const sendContextUpdate = useCallback(
    async (sectionId: string | null) => {
      const socket = await connectSocket();
      sendSocketMessage(socket, {
        type: 'context_update',
        focused_section_id: sectionId ?? undefined,
      });
    },
    [connectSocket]
  );

  const sendTextTurn = useCallback(
    async (text: string) => {
      const socket = await connectSocket();
      sendSocketMessage(socket, {
        type: 'text_turn',
        text,
      });
    },
    [connectSocket]
  );

  useEffect(() => {
    if (!focusRequest || lastFocusNonceRef.current === focusRequest.nonce) {
      return;
    }
    lastFocusNonceRef.current = focusRequest.nonce;
    setFocusedSectionId(focusRequest.section.id);
    onFocusChange(focusRequest.section.id);
    setErrorMessage(null);
    void sendContextUpdate(focusRequest.section.id).catch((error) => {
      setRawState('error');
      setErrorMessage(
        error instanceof Error ? error.message : 'Unable to focus the voice assistant.'
      );
    });
  }, [focusRequest, onFocusChange, sendContextUpdate]);

  const clearFocus = useCallback(() => {
    setFocusedSectionId(null);
    onFocusChange(null);
    void sendContextUpdate(null).catch((error) => {
      setRawState('error');
      setErrorMessage(
        error instanceof Error ? error.message : 'Unable to switch back to report-wide mode.'
      );
    });
  }, [onFocusChange, sendContextUpdate]);

  const startCapture = useCallback(async () => {
    const socket = await connectSocket();
    if (recorderRef.current) {
      return;
    }

    const stream = await navigator.mediaDevices.getUserMedia({
      audio: true,
    });
    const context = new AudioContext();
    await context.resume();
    const source = context.createMediaStreamSource(stream);
    const processor = context.createScriptProcessor(4096, 1, 1);
    const sink = context.createGain();
    sink.gain.value = 0;

    processor.onaudioprocess = (event) => {
      const openSocket = socketRef.current;
      if (!openSocket || openSocket.readyState !== WebSocket.OPEN) {
        return;
      }
      const input = event.inputBuffer.getChannelData(0);
      const pcm16 = downsampleToPcm16(input, context.sampleRate, 16000);
      if (pcm16.length === 0) {
        return;
      }
      sendSocketMessage(openSocket, {
          type: 'audio_chunk',
          data: bytesToBase64(new Uint8Array(pcm16.buffer)),
        });
    };

    source.connect(processor);
    processor.connect(sink);
    sink.connect(context.destination);

    recorderRef.current = {
      stream,
      context,
      source,
      processor,
      sink,
    };

    sendSocketMessage(socket, { type: 'audio_start' });
    setRawState('listening');
  }, [connectSocket]);

  const toggleListening = useCallback(async () => {
    if (!enabled) {
      setErrorMessage('Voice is available once the report has finished generating.');
      return;
    }

    if (rawState === 'listening') {
      await stopCapture(true);
      setRawState('thinking');
      return;
    }

    if (rawState === 'connecting' || rawState === 'thinking' || rawState === 'speaking') {
      return;
    }

    setErrorMessage(null);
    try {
      await startCapture();
    } catch (error) {
      setRawState('error');
      setErrorMessage(
        error instanceof Error ? error.message : 'Unable to start the microphone.'
      );
    }
  }, [enabled, rawState, startCapture, stopCapture]);

  const handleConfirmEdit = useCallback(async () => {
    if (!pendingProposal) {
      return;
    }
    setIsApplyingEdit(true);
    try {
      await editSection({
        caseId,
        sectionId: pendingProposal.section_id,
        instruction: pendingProposal.instruction,
        canonicalBlockId: pendingProposal.canonical_block_id,
        editTarget: pendingProposal.edit_target,
      });
      await onReportUpdated();
      setPendingProposal(null);
      setErrorMessage(null);
      setFocusedSectionId(pendingProposal.section_id);
      onFocusChange(pendingProposal.section_id);
      await sendContextUpdate(pendingProposal.section_id);
      await sendTextTurn(
        `The user confirmed the edit for ${pendingProposal.title}. The report has been updated.`
      );
    } catch (error) {
      setRawState('error');
      setErrorMessage(
        error instanceof Error ? error.message : 'Unable to apply the voice edit.'
      );
    } finally {
      setIsApplyingEdit(false);
    }
  }, [
    caseId,
    onFocusChange,
    onReportUpdated,
    pendingProposal,
    sendContextUpdate,
    sendTextTurn,
  ]);

  const handleCancelEdit = useCallback(async () => {
    if (!pendingProposal) {
      return;
    }
    const cancelled = pendingProposal;
    setPendingProposal(null);
    try {
      await sendTextTurn(
        `The user canceled the proposed edit for ${cancelled.title}. Continue helping without changing the report.`
      );
    } catch (error) {
      setRawState('error');
      setErrorMessage(
        error instanceof Error ? error.message : 'Unable to resume the voice session.'
      );
    }
  }, [pendingProposal, sendTextTurn]);

  const orbCaption = pendingProposal
    ? 'confirm change'
    : rawState === 'listening'
      ? 'tap to stop'
      : rawState === 'disconnected' && enabled
        ? 'tap to connect'
        : 'tap to speak';

  return (
    <div
      style={{
        position: 'fixed',
        right: '28px',
        bottom: '28px',
        width: '240px',
        zIndex: 35,
      }}
    >
      <div
        style={{
          background: 'rgba(251, 250, 247, 0.96)',
          border: '1px solid var(--border)',
          borderRadius: '14px',
          padding: '14px 14px 12px',
          boxShadow: '0 14px 32px rgba(27, 25, 19, 0.08)',
          backdropFilter: 'blur(10px)',
        }}
      >
        {focusedSection && (
          <div
            style={{
              marginBottom: '10px',
              paddingBottom: '10px',
              borderBottom: '1px solid var(--border)',
            }}
          >
            <p
              style={{
                margin: 0,
                fontSize: '10px',
                fontWeight: 600,
                letterSpacing: '0.08em',
                color: 'var(--text-tertiary)',
                textTransform: 'uppercase',
              }}
            >
              Focused Section
            </p>
            <p
              style={{
                margin: '4px 0 0',
                fontSize: '12px',
                color: 'var(--text-primary)',
                lineHeight: 1.45,
              }}
            >
              {describeSection(focusedSection)}
            </p>
            <button
              type="button"
              onClick={clearFocus}
              style={ghostButtonStyle}
            >
              Return to report-wide mode
            </button>
          </div>
        )}

        {pendingProposal && (
          <div
            style={{
              marginBottom: '12px',
              padding: '10px 12px',
              borderRadius: '10px',
              border: '1px solid var(--border)',
              background: 'var(--bg-elevated)',
            }}
          >
            <p
              style={{
                margin: 0,
                fontSize: '10px',
                fontWeight: 600,
                letterSpacing: '0.08em',
                color: 'var(--text-tertiary)',
                textTransform: 'uppercase',
              }}
            >
              Edit proposal
            </p>
            <p
              style={{
                margin: '6px 0 4px',
                fontSize: '12px',
                color: 'var(--text-primary)',
                lineHeight: 1.45,
              }}
            >
              {pendingProposal.title}
            </p>
            <p
              style={{
                margin: 0,
                fontSize: '12px',
                color: 'var(--text-secondary)',
                lineHeight: 1.45,
              }}
            >
              {pendingProposal.summary}
            </p>
            <div style={{ display: 'flex', gap: '8px', marginTop: '10px' }}>
              <button
                type="button"
                onClick={() => void handleConfirmEdit()}
                disabled={isApplyingEdit}
                style={primaryButtonStyle}
              >
                {isApplyingEdit ? 'Applying...' : 'Confirm'}
              </button>
              <button
                type="button"
                onClick={() => void handleCancelEdit()}
                disabled={isApplyingEdit}
                style={secondaryButtonStyle}
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {errorMessage && (
          <div
            style={{
              marginBottom: '12px',
              padding: '8px 10px',
              borderRadius: '8px',
              background: 'var(--severity-high-bg)',
              color: 'var(--severity-high)',
              fontSize: '12px',
              lineHeight: 1.45,
            }}
          >
            {errorMessage}
          </div>
        )}

        <div style={{ width: '96px', margin: '0 auto' }}>
          <AgentOrb
            state={orbState}
            onClick={() => void toggleListening()}
            disabled={!enabled || isApplyingEdit}
            caption={orbCaption}
          />
        </div>

        <div
          style={{
            marginTop: '6px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px',
            color: 'var(--text-tertiary)',
            fontSize: '11px',
          }}
        >
          {rawState === 'listening' ? <Mic size={12} /> : <MicOff size={12} />}
          <span>
            {enabled
              ? rawState === 'listening'
                ? 'Listening. Tap again to send.'
                : 'Tap the orb to ask a question or direct an edit.'
              : 'Voice becomes available once the report is complete.'}
          </span>
        </div>
      </div>
    </div>
  );
}

const ghostButtonStyle: React.CSSProperties = {
  marginTop: '8px',
  background: 'none',
  border: 'none',
  padding: 0,
  color: 'var(--accent)',
  cursor: 'pointer',
  fontSize: '11px',
  fontWeight: 500,
};

const primaryButtonStyle: React.CSSProperties = {
  flex: 1,
  border: '1px solid transparent',
  borderRadius: '8px',
  padding: '8px 10px',
  background: 'var(--accent)',
  color: '#fff',
  cursor: 'pointer',
  fontSize: '12px',
  fontWeight: 600,
};

const secondaryButtonStyle: React.CSSProperties = {
  flex: 1,
  border: '1px solid var(--border)',
  borderRadius: '8px',
  padding: '8px 10px',
  background: 'var(--bg-surface)',
  color: 'var(--text-primary)',
  cursor: 'pointer',
  fontSize: '12px',
  fontWeight: 500,
};

function downsampleToPcm16(
  input: Float32Array,
  inputSampleRate: number,
  outputSampleRate: number
): Int16Array {
  if (inputSampleRate === outputSampleRate) {
    return floatToInt16(input);
  }

  const ratio = inputSampleRate / outputSampleRate;
  const outputLength = Math.max(1, Math.round(input.length / ratio));
  const output = new Int16Array(outputLength);
  let outputOffset = 0;
  let inputOffset = 0;

  while (outputOffset < outputLength) {
    const nextInputOffset = Math.min(input.length, Math.round((outputOffset + 1) * ratio));
    let accumulator = 0;
    let count = 0;
    while (inputOffset < nextInputOffset) {
      accumulator += input[inputOffset];
      inputOffset += 1;
      count += 1;
    }
    const sample = count > 0 ? accumulator / count : 0;
    output[outputOffset] = clampToInt16(sample);
    outputOffset += 1;
  }

  return output;
}

function floatToInt16(input: Float32Array): Int16Array {
  const output = new Int16Array(input.length);
  for (let index = 0; index < input.length; index += 1) {
    output[index] = clampToInt16(input[index]);
  }
  return output;
}

function clampToInt16(value: number): number {
  const sample = Math.max(-1, Math.min(1, value));
  return sample < 0 ? sample * 0x8000 : sample * 0x7fff;
}

async function enqueueAudioChunk(
  base64Data: string,
  mimeType: string | undefined,
  playbackContextRef: React.MutableRefObject<AudioContext | null>,
  nextPlaybackTimeRef: React.MutableRefObject<number>
) {
  const context =
    playbackContextRef.current ??
    new AudioContext({
      sampleRate: parseSampleRate(mimeType),
    });
  playbackContextRef.current = context;
  if (context.state === 'suspended') {
    await context.resume();
  }

  const bytes = base64ToUint8Array(base64Data);
  const sampleRate = parseSampleRate(mimeType);
  const floatData = pcm16BytesToFloat32(bytes);
  const buffer = context.createBuffer(1, floatData.length, sampleRate);
  buffer.getChannelData(0).set(floatData);

  const source = context.createBufferSource();
  source.buffer = buffer;
  source.connect(context.destination);

  const startTime = Math.max(context.currentTime, nextPlaybackTimeRef.current);
  source.start(startTime);
  nextPlaybackTimeRef.current = startTime + buffer.duration;
}

function parseSampleRate(mimeType?: string): number {
  const match = mimeType?.match(/rate=(\d+)/);
  if (match) {
    return Number(match[1]);
  }
  return 24000;
}

function pcm16BytesToFloat32(bytes: Uint8Array): Float32Array {
  const sampleCount = Math.floor(bytes.length / 2);
  const output = new Float32Array(sampleCount);
  for (let index = 0; index < sampleCount; index += 1) {
    let value = bytes[index * 2] | (bytes[index * 2 + 1] << 8);
    if (value >= 0x8000) {
      value -= 0x10000;
    }
    output[index] = value / 0x8000;
  }
  return output;
}

function bytesToBase64(bytes: Uint8Array): string {
  let binary = '';
  for (let index = 0; index < bytes.length; index += 1) {
    binary += String.fromCharCode(bytes[index]);
  }
  return btoa(binary);
}

function base64ToUint8Array(value: string): Uint8Array {
  const binary = atob(value);
  const output = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    output[index] = binary.charCodeAt(index);
  }
  return output;
}

function sendSocketMessage(socket: WebSocket, payload: unknown) {
  if (socket.readyState !== WebSocket.OPEN) {
    throw new Error('Voice session is not connected.');
  }
  socket.send(JSON.stringify(payload));
}

function describeSection(section: ReportSection): string {
  const text = section.text?.trim();
  if (!text) {
    return section.id;
  }
  if (text.length <= 90) {
    return text;
  }
  return `${text.slice(0, 87).trimEnd()}...`;
}
