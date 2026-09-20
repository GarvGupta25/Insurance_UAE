import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { post } from '../api';

export function ProviderQuoteForm({ applicationId }: { applicationId: string }) {
  const query = useQueryClient();
  const [premium, setPremium] = useState('');
  const [deductible, setDeductible] = useState('');
  const [network, setNetwork] = useState('standard');
  const [message, setMessage] = useState('');
  const [assistantDraft, setAssistantDraft] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setMessage('');
    try {
      await post(`/api/provider/applications/${applicationId}/quote`, { premium: Number(premium), plan_terms: { deductible: Number(deductible), network } });
      await Promise.all([query.invalidateQueries({ queryKey: ['provider-applications'] }), query.invalidateQueries({ queryKey: ['provider-quotations'] })]);
      setMessage('Quotation submitted to the marketplace.'); setPremium(''); setDeductible('');
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Quotation could not be submitted.'); }
    finally { setBusy(false); }
  }
  async function askAssistant(task: 'summarize_application' | 'draft_quotation' | 'flag_anomalies') {
    try { const response = await post<{ draft: string }>(`/api/provider/applications/${applicationId}/assistant`, { task }); setAssistantDraft(response.draft); }
    catch (error) { setAssistantDraft(error instanceof Error ? error.message : 'The drafting aid is unavailable.'); }
  }
  return <form className="surface provider-form" onSubmit={submit}><div className="section-heading"><div><span className="eyebrow">QUOTATION</span><h2>Terms for this application</h2></div></div><div className="provider-assistant"><strong>Provider drafting aid</strong><div className="actions"><button type="button" className="secondary" onClick={() => askAssistant('summarize_application')}>Summarize</button><button type="button" className="secondary" onClick={() => askAssistant('draft_quotation')}>Draft wording</button><button type="button" className="secondary" onClick={() => askAssistant('flag_anomalies')}>Check gaps</button></div>{assistantDraft && <p>{assistantDraft}</p>}</div><div className="form-grid"><label className="field">Annual premium (AED)<input type="number" min="1" step="0.01" value={premium} onChange={event => setPremium(event.target.value)} required/></label><label className="field">Deductible (AED)<input type="number" min="0" step="1" value={deductible} onChange={event => setDeductible(event.target.value)} required/></label><label className="field">Network<select value={network} onChange={event => setNetwork(event.target.value)}><option value="restricted">Restricted</option><option value="standard">Standard</option><option value="wide">Wide</option></select></label></div>{message && <p className="notice" role="status">{message}</p>}<div className="form-actions"><small>All limits and exclusions remain visible to the customer and broker.</small><button disabled={busy}>{busy ? 'Submitting…' : 'Submit quotation'}</button></div></form>;
}
