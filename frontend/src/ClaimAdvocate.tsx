import { useState } from 'react';
import { auth, post } from './api';

export function ClaimAdvocate({ policyId }: { policyId: string }) {
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState<Array<{ role: string; text: string; proof?: string }>>([]);
  const [busy, setBusy] = useState(false);

  async function ask(event: React.FormEvent) {
    event.preventDefault();
    const text = question.trim();
    if (!text || busy) return;
    setQuestion(''); setBusy(true);
    setMessages(current => [...current, { role: 'You', text }]);
    try {
      const result = await post(`/api/policies/${policyId}/claim-intakes/advocate`, { message: text });
      setMessages(current => [...current, { role: 'Helm', text: result.reply, proof: result.proof_url }]);
    } catch (error) {
      setMessages(current => [...current, { role: 'Helm', text: (error as Error).message }]);
    } finally { setBusy(false); }
  }

  async function download(path: string) {
    const token = auth ? (await auth.auth.getSession()).data.session?.access_token : null;
    const response = await fetch(path, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
    if (!response.ok) throw new Error('The letter could not be downloaded.');
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement('a'); link.href = url; link.download = 'helm-policy-proof.pdf'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return <section className="surface claim-advocate"><span className="eyebrow">CLAIM ADVOCATE · AVAILABLE ANYTIME</span>
    <h2>Ask about your claim or cover</h2><p className="muted">Ask why a claim is in review, what your saved plan says, or request a policy proof letter.</p>
    <div className="claim-advocate-messages" aria-live="polite">{messages.map((message, index) => <div className={message.role === 'You' ? 'member-message' : 'helm-message'} key={index}><strong>{message.role}</strong><p>{message.text}</p>{message.proof && <button type="button" className="secondary" onClick={() => void download(message.proof!)}>Download proof letter</button>}</div>)}</div>
    <form onSubmit={ask}><label className="field">Your question<textarea maxLength={1000} value={question} onChange={event => setQuestion(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} placeholder="Why is my claim in review?"/></label><button disabled={busy || !question.trim()}>{busy ? 'Checking…' : 'Ask Helm'}</button></form>
  </section>;
}
