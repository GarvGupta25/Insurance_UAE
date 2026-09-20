import { useState } from 'react';
import { post } from '../api';

export function ProviderFlagForm({ policyId }: { policyId: string }) {
  const [reason, setReason] = useState(''); const [note, setNote] = useState(''); const [message, setMessage] = useState('');
  async function submit(event: React.FormEvent) {
    event.preventDefault(); setMessage('');
    try { await post(`/api/provider/policies/${policyId}/flags`, { reason, note: note || null }); setReason(''); setNote(''); setMessage('Flag sent to the assigned broker worklist.'); }
    catch (error) { setMessage(error instanceof Error ? error.message : 'Flag could not be sent.'); }
  }
  if (!policyId) return null;
  return <form className="surface provider-form" onSubmit={submit}><span className="eyebrow">BROKER ESCALATION</span><h2>Flag a policy</h2><div className="form-grid"><label className="field">Reason<input value={reason} minLength={3} maxLength={1000} onChange={event => setReason(event.target.value)} required/></label><label className="field">Internal note<input value={note} maxLength={2000} onChange={event => setNote(event.target.value)}/></label></div>{message && <p className="notice" role="status">{message}</p>}<div className="form-actions"><small>The member’s assigned broker receives this flag.</small><button>Send flag</button></div></form>;
}
