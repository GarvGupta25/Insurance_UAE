import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, ClipboardCheck } from 'lucide-react';
import { aed, api, post } from './api';
import { ErrorView, Loading } from './Shopping';

type Application = {
  id: string;
  case_id: string;
  applicant_id: string;
  status: string;
};

type Detail = Application & {
  quotations: Array<{
    id: string;
    provider: string;
    premium: number;
    key_terms: Record<string, unknown>;
    status: string;
    submitted_at: string;
  }>;
  checkpoint_history: Array<{
    checkpoint: 'checkpoint_1' | 'checkpoint_2';
    approved_by: string;
    approved_at: string;
    action: string;
    note: string;
    edits: Record<string, unknown>;
  }>;
};

type Performance = { provider_id: string; provider_name: string; average_turnaround_hours: number | null; submitted: number; selected: number; win_rate_pct: number | null };

export function MarketplaceBrokerPanel() {
  const query = useQueryClient();
  const [selected, setSelected] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const applications = useQuery<Application[]>({
    queryKey: ['broker-marketplace-applications'],
    queryFn: () => api('/api/broker/marketplace/applications'),
    refetchInterval: 5000,
  });
  const detail = useQuery<Detail>({
    queryKey: ['broker-marketplace-application', selected],
    queryFn: () => api(`/api/broker/marketplace/applications/${selected}`),
    enabled: !!selected,
    refetchInterval: 5000,
  });
  const performance = useQuery<Performance[]>({ queryKey: ['broker-provider-performance'], queryFn: () => api('/api/broker/marketplace/provider-performance'), refetchInterval: 5000 });

  async function approveCheckpointTwo() {
    setBusy(true); setError('');
    try {
      await post(`/api/broker/marketplace/applications/${selected}/checkpoint-2`, {
        action: 'approve',
        note: 'Accepted quotation and final provider terms reviewed.',
      });
      await Promise.all([
        query.invalidateQueries({ queryKey: ['broker-worklist'] }),
        query.invalidateQueries({ queryKey: ['broker-marketplace-applications'] }),
        query.invalidateQueries({ queryKey: ['broker-marketplace-application', selected] }),
      ]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Checkpoint 2 could not be approved.');
    } finally { setBusy(false); }
  }
  const fastestProviderId = performance.data?.find(provider => provider.average_turnaround_hours != null)?.provider_id;

  return <section className="broker-appeals">
    <div className="section-heading"><div><span className="eyebrow">PROVIDER PERFORMANCE</span><h2>Response speed and wins</h2><p>Calculated from application and quotation timestamps already in the marketplace.</p></div></div>
    <div className="provider-performance">{performance.data?.map(provider => <article className={provider.provider_id === fastestProviderId ? 'fastest' : ''} key={provider.provider_id}><span className="badge neutral">{provider.provider_id === fastestProviderId ? 'Fastest response' : 'Provider'}</span><h3>{provider.provider_name}</h3><strong>{provider.average_turnaround_hours == null ? 'No data' : `${provider.average_turnaround_hours}h`}</strong><small>average turnaround</small><p>{provider.win_rate_pct == null ? 'No submitted quotations' : `${provider.win_rate_pct}% win rate · ${provider.selected}/${provider.submitted} selected`}</p></article>)}</div>
    <div className="section-heading"><div><span className="eyebrow">MARKETPLACE</span><h2>Provider quotations and checkpoints</h2><p>Compare submitted terms and inspect both human approvals from one case record.</p></div><span className="badge neutral">{applications.data?.length || 0} applications</span></div>
    {applications.isLoading ? <Loading/> : applications.error ? <ErrorView error={applications.error}/> : !applications.data?.length ? <div className="empty-state"><ClipboardCheck size={30}/><h3>No marketplace applications.</h3><p>Applications will appear here after customer consent.</p></div> : <div className="broker-list">{applications.data.map(item => <button className="list-row" key={item.id} aria-pressed={selected === item.id} onClick={() => setSelected(item.id)}><span className="badge neutral">{item.status.replaceAll('_', ' ')}</span><div><strong>Case {item.case_id}</strong><small>Applicant {item.applicant_id}</small></div></button>)}</div>}
    {detail.isLoading && <Loading/>}
    {detail.error && <ErrorView error={detail.error}/>}
    {error && <ErrorView error={new Error(error)}/>}
    {detail.data && <article className="surface broker-card">
      <div className="section-heading"><div><span className="eyebrow">QUOTATION COMPARISON</span><h2>Case {detail.data.case_id}</h2></div><span className="badge neutral">{detail.data.status.replaceAll('_', ' ')}</span></div>
      {!detail.data.quotations.length ? <p className="muted">No provider quotations submitted yet.</p> : <div className="plan-grid">{detail.data.quotations.map(quotation => <section className="plan-card" key={quotation.id}><div className="plan-top"><span className="eyebrow">{quotation.provider}</span><span className="badge neutral">{quotation.status}</span></div><strong className="plan-price">{aed(quotation.premium * 100)}<small>/ year</small></strong><dl className="term-list">{Object.entries(quotation.key_terms).slice(0, 5).map(([key, value]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{typeof value === 'object' ? JSON.stringify(value) : String(value)}</dd></div>)}</dl><small>Submitted {new Date(quotation.submitted_at).toLocaleString()}</small></section>)}</div>}
      <h3>Checkpoint history</h3>
      {!detail.data.checkpoint_history.length ? <p className="muted">No checkpoint approval recorded.</p> : <div className="broker-list">{detail.data.checkpoint_history.map(review => <div className="list-row" key={`${review.checkpoint}-${review.approved_at}`}><Check size={18}/><div><strong>{review.checkpoint.replace('_', ' ')}</strong><small>{review.action} by {review.approved_by} · {new Date(review.approved_at).toLocaleString()}{review.note ? ` · ${review.note}` : ''}{Object.keys(review.edits || {}).length ? ` · edits: ${JSON.stringify(review.edits)}` : ''}</small></div></div>)}</div>}
      {detail.data.status === 'provider_accepted' && <div className="broker-review-form"><button disabled={busy} onClick={() => void approveCheckpointTwo()}><Check size={17}/>{busy ? 'Saving approval…' : 'Approve Checkpoint 2'}</button></div>}
    </article>}
  </section>;
}
