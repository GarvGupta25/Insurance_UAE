import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, aed, post } from '../api';
import type { ProviderPolicy, ProviderQuotation } from './types';

export function ProviderPolicies({ selectedPolicy, onSelectPolicy }: { selectedPolicy: string; onSelectPolicy: (id: string) => void }) {
  const query = useQueryClient(); const [message, setMessage] = useState('');
  const quotations = useQuery<ProviderQuotation[]>({ queryKey: ['provider-quotations'], queryFn: () => api('/api/provider/quotations'), refetchInterval: 5000 });
  const policies = useQuery<ProviderPolicy[]>({ queryKey: ['provider-policies'], queryFn: () => api('/api/provider/policies') });
  async function action(path: string, body: unknown = {}) {
    setMessage('');
    try { await post(path, body); await Promise.all([query.invalidateQueries({ queryKey: ['provider-quotations'] }), query.invalidateQueries({ queryKey: ['provider-policies'] })]); setMessage('Provider record updated.'); }
    catch (error) { setMessage(error instanceof Error ? error.message : 'The provider record could not be updated.'); }
  }
  return <section className="surface"><span className="eyebrow">QUOTES & POLICIES</span><h2>Portfolio</h2>{message && <p className="notice" role="status">{message}</p>}<h3>Quotations</h3>{quotations.data?.map(quote => <div className="list-row" key={quote.id}><div><strong>{aed(quote.premium * 100)} · {quote.status}</strong><small>Application {quote.application_id.slice(0, 8)}</small></div>{quote.status === 'selected' && <button onClick={() => action(`/api/provider/quotations/${quote.id}/accept`)}>Accept and start policy</button>}{quote.status === 'accepted' && <span className="badge success">Policy started</span>}</div>)}{!quotations.isLoading && !quotations.data?.length && <p>No quotations yet.</p>}<h3>Policies</h3>{policies.data?.map(policy => <div className={`list-row provider-policy ${selectedPolicy === policy.id ? 'selected' : ''}`} key={policy.id}><button className="quiet" onClick={() => onSelectPolicy(policy.id)}><strong>Policy {policy.id.slice(0, 8)}</strong><small>{policy.status}</small></button>{policy.status === 'active' && <button className="secondary" onClick={() => { const reason = window.prompt('Reason for discontinuation'); if (reason) void action(`/api/provider/policies/${policy.id}/discontinue`, { reason }); }}>Discontinue</button>}</div>)}{!policies.isLoading && !policies.data?.length && <p>No bound policies yet.</p>}</section>;
}
