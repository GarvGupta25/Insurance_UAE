import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowUp, Sparkles, Check, MessageCircle } from 'lucide-react';
import { api, post } from './api';
import { VoiceInput, ReadAloud } from './Voice';

export function Conversation({ caseId, profile, voice, policyId }: { caseId: string; profile: any; voice: boolean; policyId?: string }) {
  const query = useQueryClient(); const [text, setText] = useState(''); const [modality, setModality] = useState('text'); const [transcript, setTranscript] = useState<string | null>(null);
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false); const [dismissed, setDismissed] = useState<string[]>([]); const [selectionNote, setSelectionNote] = useState('');
  const end = useRef<HTMLDivElement>(null);
  const { data, error: loadError } = useQuery({ queryKey: ['case', caseId], queryFn: () => api(`/api/cases/${caseId}`), refetchInterval: query => query.state.data?.active_runs?.length ? 1500 : false });
  const recommendationsReady = data?.messages?.some((message: any) => message.role === 'assistant' && message.text.includes('recommendations are ready'));
  const recommendations = useQuery<any>({ queryKey: ['chat-recommendations', caseId], queryFn: () => api(`/api/marketplace/cases/${caseId}/recommendations`), enabled: !policyId && !!profile.readiness.ready && !!recommendationsReady, retry: false });
  const visibleMessages = data?.messages.filter((message: any) => message.text !== 'AI is not configured yet. Your saved policy details remain available on this page.');
  useEffect(() => { end.current?.scrollIntoView({ block: 'nearest', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' }); }, [data?.messages?.length]);
  async function send(event: React.FormEvent) {
    event.preventDefault(); if (!text.trim()) return; setBusy(true); setError('');
    try {
      const ranks = !policyId && profile.readiness.ready && /^\s*[1-5](\s*[,\s]\s*[1-5])*\s*$/.test(text) ? [...new Set((text.match(/[1-5]/g) || []).map(Number))].slice(0, 3) : [];
      if (ranks.length && recommendations.data?.recommendations) {
        const planIds = ranks.map(rank => recommendations.data.recommendations[rank - 1]?.plan_id).filter(Boolean);
        await post(`/api/marketplace/cases/${caseId}/consent`, { consent: 'yes', plan_ids: planIds });
        setSelectionNote(`✨ Your request was sent to provider option${ranks.length === 1 ? '' : 's'} ${ranks.join(', ')}. We will notify you when final quotations are ready.`);
        setText(''); await query.invalidateQueries({ queryKey: ['marketplace-applications'] }); return;
      }
      await post(`/api/cases/${caseId}/messages`, { text, modality, policy_id: policyId }); setText(''); setModality('text'); await query.invalidateQueries({ queryKey: ['case', caseId] });
    }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  async function accept(message: any) {
    setBusy(true); setError('');
    try { await api('/api/me/profile', { method: 'PATCH', body: JSON.stringify({ expected_version: message.details.profile_version, changes: message.details.patch, source_message_id: message.details.source_message_id }) }); setDismissed(d => [...d, message.id]); await query.invalidateQueries({ queryKey: ['profile'] }); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  return <section className="conversation">
    <div className="conversation-header"><span className="assistant-avatar"><Sparkles size={21}/></span><div><strong>Your Helm assistant</strong><small>Here to make the details clearer</small></div><span className="status-dot"/></div>
    <div className="messages" aria-label="Conversation history"><div className="message assistant"><span className="eyebrow">LET’S START WITH YOU</span><p>{policyId ? 'Ask a question about this policy, its saved terms or its payment schedule.' : 'Tell me what you need from your health cover. We’ll keep the details together, so you only explain things once.'}</p>{!policyId && !data?.messages?.length && <p>{profile.readiness.question}</p>}</div>
      {recommendations.data?.recommendations?.length > 0 && <div className="message assistant"><span className="message-label">Helm · your personalised matches</span><p>{recommendations.data.recommendations.map((item: any) => `#${item.rank} ${item.provider_name} — ${item.name} (AED ${item.premium_aed.toLocaleString()}/year)`).join('\n')}</p><small>Reply with up to three numbers, such as “1, 3”, to request final quotations. You can also choose cards manually under Get quotation.</small></div>}
      {selectionNote && <div className="notice" role="status">{selectionNote}</div>}
      {visibleMessages?.map((message: any) => <div className={`message ${message.role}`} key={message.id}><span className="message-label">{message.role === 'user' ? 'You' : 'Helm'}{message.modality === 'voice' ? ' · from voice' : ''}</span><p>{message.text}</p>{message.role === 'assistant' && <ReadAloud text={message.text}/>}
        {message.details?.patch && Object.keys(message.details.patch).length > 0 && !dismissed.includes(message.id) && <div className="fact-review"><strong>Check what I understood</strong><dl>{Object.entries(message.details.patch).map(([key, value]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{Array.isArray(value) ? value.join(', ') : String(value)}</dd></div>)}</dl><div className="actions"><button disabled={busy || message.details.profile_version !== profile.version} onClick={() => accept(message)}><Check size={15}/> Save these details</button><button className="quiet" onClick={() => setDismissed(d => [...d, message.id])}>Discard</button></div>{message.details.profile_version !== profile.version && <small>Your profile has changed. Use the editor to apply any remaining corrections.</small>}</div>}</div>)}
      {data?.active_runs?.length > 0 && <div className="processing" role="status"><span className="typing-dots">•••</span> Working on your answer. Your saved details are safe.</div>}
      {loadError && <p className="error">{(loadError as Error).message}</p>}<div ref={end}/>
    </div>
    <form className="composer" onSubmit={send}>
      {modality === 'voice' && <div className="transcript-label"><MessageCircle size={15}/> Review or edit the transcript, then send.</div>}
      <label className="sr-only" htmlFor="message">Your answer or policy question</label><textarea id="message" value={text} maxLength={4000} onChange={e => setText(e.target.value)} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} placeholder="Tell us a little about yourself, or ask a question…" rows={3}/>
      {transcript !== null && <div className="fact-review"><label className="field">Review the voice transcript<textarea aria-label="Voice transcript" value={transcript} onChange={e => setTranscript(e.target.value)}/></label><div className="actions"><button type="button" onClick={() => { setText(previous => previous ? previous + '\n' + transcript : transcript); setModality('voice'); setTranscript(null); }}>Use this transcript</button><button type="button" className="quiet" onClick={() => setTranscript(null)}>Discard recording</button></div></div>}
      <div className="composer-actions"><VoiceInput key={caseId + (policyId || '')} available={voice && !busy} onTranscript={setTranscript}/><button className="send-button" aria-label="Send message" disabled={busy || !text.trim() || !!data?.active_runs?.length}><ArrowUp size={20}/></button></div>
      <small>Press Enter to send · Shift+Enter for a new line. Voice sends audio to Groq for transcription; Helm discards the clip.</small>
      {error && <p role="alert" className="error">{error}</p>}
    </form>
  </section>;
}
