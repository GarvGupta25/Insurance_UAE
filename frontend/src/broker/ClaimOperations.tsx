import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, post } from '../api';

export function ClaimOperations() {
  const query = useQueryClient();
  const metrics = useQuery({ queryKey: ['claim-observability'], queryFn: () => api('/api/broker/claims/observability'), refetchInterval: 15000 });
  const rules = useQuery({ queryKey: ['claim-rules'], queryFn: () => api('/api/broker/claims/rules') });
  const samples = useQuery<any[]>({ queryKey: ['claim-samples'], queryFn: () => api('/api/broker/claims/quality-samples') });
  const [kind, setKind] = useState<'provisional' | 'automatic'>('provisional');
  const [form, setForm] = useState({ policy_type: 'plan_a', claim_category: 'emergency_room_admission', max_amount_aed: '2000', min_confidence: '0.8' });
  const [claimId, setClaimId] = useState('');
  const [replay, setReplay] = useState<any>(null);
  const [notice, setNotice] = useState('');
  async function saveRule(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      await post(`/api/broker/claims/rules/${kind}`, { ...form, max_amount_aed: Number(form.max_amount_aed), min_confidence: Number(form.min_confidence), active: true, requires_conditions: kind === 'provisional' ? ['emergency_flag', 'active_policy', 'covered_category'] : [] });
      setNotice('Rule saved. Higher automatic caps require reviewed quality samples.');
      await query.invalidateQueries({ queryKey: ['claim-rules'] });
    } catch (error) { setNotice((error as Error).message); }
  }
  async function reviewSample(id: string, status: 'correct' | 'incorrect') {
    const note = window.prompt('Record the evidence for this human audit:');
    if (!note?.trim()) return;
    try { await post(`/api/broker/claims/quality-samples/${id}/review`, { status, note }); setNotice('Audit saved.'); await query.invalidateQueries({ queryKey: ['claim-samples'] }); await query.invalidateQueries({ queryKey: ['claim-observability'] }); }
    catch (error) { setNotice((error as Error).message); }
  }
  async function loadReplay() {
    try { setReplay(await api(`/api/broker/claims/${claimId.trim()}/replay`)); setNotice(''); }
    catch (error) { setNotice((error as Error).message); }
  }
  return <section className="surface" aria-label="Claim operations and compliance">
    <h2>Claim operations</h2><p className="muted">Broker-only sandbox controls and an evidence trail for every claim.</p>
    {metrics.data && <div className="claim-field-grid"><p><strong>Routes</strong><br/>{Object.entries(metrics.data.routes).map(([route, count]) => `${route}: ${count}`).join(' · ') || 'No claims yet'}</p><p><strong>Average seconds to decision</strong><br/>{Object.entries(metrics.data.mean_seconds_to_decision).map(([route, seconds]) => `${route}: ${seconds}`).join(' · ') || 'Pending'}</p><p><strong>False-auto rate</strong><br/>{metrics.data.false_auto_rate_pct == null ? 'Awaiting audits' : `${metrics.data.false_auto_rate_pct}%`}</p><p><strong>On-call page within 60 seconds</strong><br/>{metrics.data.oncall_page_within_60_seconds.met} / {metrics.data.oncall_page_within_60_seconds.total}</p></div>}
    <details><summary>Underwriting rules</summary><p>These demo rules affect only matching policy types and categories. Core safety floors still apply.</p>{rules.data && <pre className="claim-replay">{JSON.stringify(rules.data, null, 2)}</pre>}<form onSubmit={event => void saveRule(event)} className="servicing-form"><label className="field">Rule type<select value={kind} onChange={event => setKind(event.target.value as typeof kind)}><option value="provisional">Emergency provisional</option><option value="automatic">Routine automatic</option></select></label><label className="field">Policy type<input required value={form.policy_type} onChange={event => setForm({ ...form, policy_type: event.target.value })}/></label><label className="field">Claim category<input required value={form.claim_category} onChange={event => setForm({ ...form, claim_category: event.target.value })}/></label><label className="field">Maximum AED<input required type="number" min="1" value={form.max_amount_aed} onChange={event => setForm({ ...form, max_amount_aed: event.target.value })}/></label>{kind === 'automatic' && <label className="field">Minimum confidence<input required type="number" min="0" max="1" step="0.05" value={form.min_confidence} onChange={event => setForm({ ...form, min_confidence: event.target.value })}/></label>}<button>Save rule</button></form></details>
    <details><summary>Sampled automatic decisions ({samples.data?.length || 0} pending)</summary>{samples.data?.map(sample => <p key={sample.id}>Claim {sample.claim_id} <button type="button" onClick={() => void reviewSample(sample.id, 'correct')}>Mark correct</button> <button type="button" onClick={() => void reviewSample(sample.id, 'incorrect')}>Mark incorrect</button></p>)}</details>
    <details><summary>Replay a claim</summary><label className="field">Claim ID<input value={claimId} onChange={event => setClaimId(event.target.value)}/></label><button type="button" disabled={!claimId.trim()} onClick={() => void loadReplay()}>Load evidence trail</button>{replay && <pre className="claim-replay">{JSON.stringify(replay, null, 2)}</pre>}</details>
    {notice && <p role="status">{notice}</p>}
  </section>;
}
