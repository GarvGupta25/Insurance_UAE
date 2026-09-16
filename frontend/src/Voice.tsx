import { useEffect, useRef, useState } from 'react';
import { Mic, Square, Volume2, X, LoaderCircle } from 'lucide-react';
import { api } from './api';

export function ReadAloud({ text }: { text: string }) {
  const [speaking, setSpeaking] = useState(false);
  useEffect(() => () => { if ('speechSynthesis' in window) window.speechSynthesis.cancel(); }, [text]);
  if (!('speechSynthesis' in window)) return null;
  function toggle() {
    window.speechSynthesis.cancel();
    if (speaking) { setSpeaking(false); return; }
    const utterance = new SpeechSynthesisUtterance(text); utterance.lang = 'en-GB'; utterance.rate = 0.95;
    utterance.onend = () => setSpeaking(false); utterance.onerror = () => setSpeaking(false);
    setSpeaking(true); window.speechSynthesis.speak(utterance);
  }
  return <button className="icon-text quiet" onClick={toggle} aria-label={speaking ? 'Stop reading' : 'Read explanation aloud'}><Volume2 size={16}/>{speaking ? 'Stop reading' : 'Listen'}</button>;
}

export function VoiceInput({ available, onTranscript }: { available: boolean; onTranscript: (text: string) => void }) {
  const [state, setState] = useState('idle'); const [seconds, setSeconds] = useState(0); const [error, setError] = useState('');
  const generation = useRef(0); const recorder = useRef<MediaRecorder | null>(null); const stream = useRef<MediaStream | null>(null);
  const abort = useRef<AbortController | null>(null); const interval = useRef<ReturnType<typeof setInterval> | null>(null);
  const stopTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  function release() {
    stream.current?.getTracks().forEach(track => track.stop()); stream.current = null;
    if (interval.current) clearInterval(interval.current);
    if (stopTimer.current) clearTimeout(stopTimer.current);
  }
  function cancel() {
    generation.current += 1; abort.current?.abort();
    if (recorder.current?.state === 'recording') recorder.current.stop();
    release(); setState('idle');
  }
  useEffect(() => () => { generation.current += 1; abort.current?.abort(); if (recorder.current?.state === 'recording') recorder.current.stop(); release(); }, []);
  async function start() {
    setError(''); setSeconds(0);
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) { setError('This browser cannot record audio here. You can type your answer.'); return; }
    const mime = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4'].find(type => MediaRecorder.isTypeSupported(type));
    if (!mime) { setError('No compatible recording format. Please use the keyboard.'); return; }
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    const current = ++generation.current; setState('permission');
    try {
      const media = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (current !== generation.current) { media.getTracks().forEach(t => t.stop()); return; }
      stream.current = media;
      const record = new MediaRecorder(media, { mimeType: mime }); recorder.current = record;
      const chunks: Blob[] = []; let total = 0;
      record.ondataavailable = event => { total += event.data.size; if (total <= 10 * 1024 * 1024) chunks.push(event.data); else { cancel(); setError('The recording is too large. Try a shorter answer.'); } };
      record.onstop = async () => {
        release(); if (current !== generation.current) return;
        const form = new FormData(); form.append('file', new Blob(chunks, { type: mime }), mime.includes('mp4') ? 'recording.mp4' : 'recording.webm');
        chunks.length = 0; setState('transcribing'); abort.current = new AbortController();
        try {
          const result = await api<{ transcript: string }>('/api/voice/transcriptions', { method: 'POST', body: form, signal: abort.current.signal });
          if (current === generation.current) { onTranscript(result.transcript); setState('idle'); }
        } catch (err) { if (current === generation.current) { setError(err instanceof Error ? err.message : 'Transcription failed.'); setState('idle'); } }
      };
      record.start(1000); setState('recording');
      interval.current = setInterval(() => setSeconds(s => s + 1), 1000);
      stopTimer.current = setTimeout(() => { if (record.state === 'recording') record.stop(); }, 60000);
    } catch { if (current === generation.current) { release(); setState('idle'); setError('Microphone access is unavailable. Check browser permission, or type your answer.'); } }
  }
  return <div className="voice-controls">
    {state === 'idle' ? <button type="button" className="voice-button" onClick={start} disabled={!available} title={!available ? 'Configure Groq to enable voice transcription' : 'Speak your answer'} aria-label="Speak your answer and create a transcript"><Mic size={18}/> Speak</button> :
      <><button type="button" className="voice-button recording" onClick={() => recorder.current?.stop()} disabled={state !== 'recording'}>{state === 'recording' ? <Square size={16}/> : <LoaderCircle className="spin" size={16}/>} {state === 'recording' ? `Stop · ${seconds}s` : state === 'permission' ? 'Allow microphone…' : 'Transcribing…'}</button><button type="button" className="quiet" onClick={cancel} aria-label="Cancel recording or transcription"><X size={17}/></button></>}
    <span className="sr-only" aria-live="polite">{state === 'recording' ? 'Recording. Use Stop to finish.' : state}</span>
    {error && <p role="alert" className="inline-error">{error}</p>}
  </div>;
}
