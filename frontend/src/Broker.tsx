import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertCircle, ArrowRight, Check, ClipboardCheck, RefreshCw } from 'lucide-react';
import { api, post, aed } from './api';
import { ErrorView, Loading } from './Shopping';
import { MarketplaceBrokerPanel } from './MarketplaceBrokerPanel';

type Recommendation = {
  id: string;
  quote_id: string;
  proposed_plan_id: string;
  status: 'pending_review';
  certainty: 'clear' | 'tradeoff' | 'missing_terms';
  summary: {
    selected: any;
    alternatives: any[];
    decision_brief: { requested_decision: string; main_uncertainty?: string | null; next_action: string };
  };
};

type Appeal = {
  id: string;
  appeal_id: string;
  policy_id: string;
  status: 'pending_review' | 'reviewed';
  appeal: { contested_event_id: string; statement: string; evidence: string[] };
  contested_decision: any;
  review: any;
};

type Reassessment = {
  id: string;
  policy_id: string;
  status: 'pending_review' | 'reviewed';
  recommended_plan_id: string | null;
  report: { outcome: 'retain' | 'review'; current: any; alternatives: any[]; findings: string[]; history_event_ids: string[] };
};

function certaintyLabel(certainty: Recommendation['certainty']) {
  return certainty === 'clear' ? 'Clear fit' : certainty === 'tradeoff' ? 'Tradeoffs to review' : 'Terms missing';
}

export function BrokerWorkspace() {
  const query = useQueryClient();
  const recommendations = useQuery<Recommendation[]>({ queryKey: ['broker-recommendations'], queryFn: () => api('/api/broker/recommendations') });
  const appeals = useQuery<Appeal[]>({ queryKey: ['broker-appeals'], queryFn: () => api('/api/broker/appeals') });
  const reassessments = useQuery<Reassessment[]>({ queryKey: ['broker-reassessments'], queryFn: () => api('/api/broker/reassessments') });
  const worklist = useQuery<any[]>({ queryKey: ['broker-worklist'], queryFn: () => api('/api/broker/worklist') });
  const [selectedApplicant, setSelectedApplicant] = useState('');
  const caseDetail = useQuery<any>({ queryKey: ['broker-case', selectedApplicant], queryFn: () => api(`/api/broker/cases/${selectedApplicant}`), enabled: !!selectedApplicant });
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [selected, setSelected] = useState<Record<string, string>>({});
  const [busyId, setBusyId] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [appealNotes, setAppealNotes] = useState<Record<string, string>>({});
  const [appealActions, setAppealActions] = useState<Record<string, 'uphold' | 'overturn'>>({});
  const [appealMonths, setAppealMonths] = useState<Record<string, string>>({});
  const [appealCorrections, setAppealCorrections] = useState<Record<string, 'policy_month' | 'network_membership'>>({});
  const [appealEvidence, setAppealEvidence] = useState<Record<string, string>>({});
  const [appealProviders, setAppealProviders] = useState<Record<string, string>>({});
  const [appealNetworks, setAppealNetworks] = useState<Record<string, 'restricted' | 'standard' | 'wide'>>({});
  const [reassessmentNotes, setReassessmentNotes] = useState<Record<string, string>>({});
  const [reassessmentPlans, setReassessmentPlans] = useState<Record<string, string>>({});

  async function review(item: Recommendation, action: 'approve' | 'edit') {
    setBusyId(item.id); setError(''); setMessage('');
    try {
      const selectedPlan = selected[item.id] || item.proposed_plan_id;
      await post(`/api/broker/recommendations/${item.id}/review`, {
        action,
        ...(action === 'edit' ? { selected_plan_id: selectedPlan } : {}),
        note: notes[item.id] || '',
      });
      await query.invalidateQueries({ queryKey: ['broker-recommendations'] });
      setMessage('Recommendation approved. The application is ready for the member to confirm.');
      window.setTimeout(() => setMessage(''), 6000);
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'The review could not be saved.'); }
    finally { setBusyId(''); }
  }

  async function reviewAppeal(item: Appeal) {
    const action = appealActions[item.id] || 'uphold';
    const correction = appealCorrections[item.id] || 'policy_month';
    setBusyId(item.id); setError(''); setMessage('');
    try {
      await post(`/api/broker/appeals/${item.id}/review`, {
        action,
        note: appealNotes[item.id] || (action === 'uphold' ? 'The recorded decision remains supported.' : ''),
        ...(action === 'overturn' && correction === 'policy_month' ? { corrected_policy_month: Number(appealMonths[item.id]) } : {}),
        ...(action === 'overturn' && correction === 'network_membership' ? { verified_network_membership: { provider_name: appealProviders[item.id], network_tier: appealNetworks[item.id], evidence_reference: appealEvidence[item.id] } } : {}),
      });
      await query.invalidateQueries({ queryKey: ['broker-appeals'] });
      setMessage(`Appeal ${action === 'uphold' ? 'upheld' : 'overturned'} and recorded in the servicing history.`);
      window.setTimeout(() => setMessage(''), 6000);
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'The appeal review could not be saved.'); }
    finally { setBusyId(''); }
  }

  async function reviewReassessment(item: Reassessment) {
    const currentId = item.report.current.plan.id;
    const selectedPlan = reassessmentPlans[item.id] || currentId;
    const action = selectedPlan === currentId ? 'retain' : 'recommend_change';
    setBusyId(item.id); setError(''); setMessage('');
    try {
      await post(`/api/broker/reassessments/${item.id}/review`, { action, ...(action === 'recommend_change' ? { selected_plan_id: selectedPlan } : {}), note: reassessmentNotes[item.id] || (action === 'retain' ? 'Current fictional plan remains supported.' : 'A supported fictional alternative is recommended for a future review.') });
      await query.invalidateQueries({ queryKey: ['broker-reassessments'] });
      setMessage(action === 'retain' ? 'Fit reassessment reviewed: retain current policy.' : 'Fit reassessment reviewed: an alternative was recommended.');
      window.setTimeout(() => setMessage(''), 6000);
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'The reassessment review could not be saved.'); }
    finally { setBusyId(''); }
  }

  if (recommendations.isLoading) return <Loading/>;
  if (recommendations.error) return <ErrorView error={recommendations.error}/>;
  const rows = recommendations.data || [];
  const pending = rows.filter(item => item.status === 'pending_review');
  const uncertain = pending.filter(item => item.certainty !== 'clear');
  const appealRows = appeals.data || [];
  const pendingAppeals = appealRows.filter(item => item.status === 'pending_review');
  const reassessmentRows = reassessments.data || [];
  const pendingReassessments = reassessmentRows.filter(item => item.status === 'pending_review');

  return <>
    <div className="page-heading compact"><div><span className="eyebrow">BROKER WORKSPACE</span><h1>Review the recommendation.<br/>Keep the member in control.</h1><p>Review plan requests from assigned members, then handle appeals and policy fit checks here. Ordinary Easy Fill can proceed directly to member confirmation.</p></div><ClipboardCheck className="heading-icon" size={54}/></div>
    <div className="notice broker-notice"><AlertCircle size={19}/><div><strong>Demonstration review</strong><br/>Only cases assigned to your broker account appear here. Member submissions remain separate from your review decisions.</div></div>
    <section className="surface"><div className="section-heading"><div><span className="eyebrow">PRIORITIZED WORKLIST</span><h2>What needs attention first</h2></div><span className="badge neutral">{worklist.data?.length || 0} open</span></div>{worklist.isLoading ? <Loading/> : !worklist.data?.length ? <p className="muted">No assigned work is pending.</p> : <div className="broker-list">{worklist.data.map(item => <button className="list-row" key={item.id} aria-label={`Open ${item.item_type.replaceAll('_', ' ')} case, priority ${item.priority_rank}: ${item.priority_reason}`} aria-pressed={caseDetail.data?.applicant_id === item.applicant_id} onClick={() => setSelectedApplicant(item.applicant_id)}><span className="badge neutral">#{item.priority_rank}</span><div><strong>{item.item_type.replaceAll('_', ' ')}</strong><small>{item.priority_reason}</small></div><span>{item.age_days}d</span></button>)}</div>}{caseDetail.data && <section className="broker-case-detail" aria-live="polite"><span className="badge neutral">INTERNAL · BROKER ONLY</span><h2>Complete case record</h2><h3>Classification</h3><p>{caseDetail.data.classification.cohort.replaceAll('_', ' ')}</p>{caseDetail.data.classification.flags.map((flag: any) => <p key={flag.code}><strong>{flag.explanation}</strong> {flag.review_relevance}</p>)}<h3>Pending action</h3><p>{caseDetail.data.next_action_needed}</p><h3>Review history</h3>{caseDetail.data.review_history.length ? caseDetail.data.review_history.map((review: any) => <p key={review.decided_at}>{review.action}: {review.note || 'No note'}</p>) : <p>No completed review.</p>}<h3>Marketplace policies</h3>{caseDetail.data.marketplace_policies?.length ? caseDetail.data.marketplace_policies.map((policy: any) => <p key={policy.id}><strong>{policy.provider}</strong> · {aed(policy.premium * 100)} · {policy.status}</p>) : <p>No bound marketplace policy.</p>}</section>}</section>
    <div className="metric-grid broker-metrics"><div><span>Plan requests</span><strong>{pending.length}</strong><small>Members who asked for a broker decision</small></div><div><span>Needs attention</span><strong>{uncertain.length + pendingAppeals.length + pendingReassessments.length}</strong><small>Tradeoffs, appeals, or fit checks awaiting a decision</small></div></div>
    {message && <div className="notice" role="status">{message}</div>}
    {error && <ErrorView error={new Error(error)}/>} 
    {!rows.length ? <div className="empty-state"><ClipboardCheck size={32}/><h3>No plan review requests.</h3><p>Assigned members can choose “Ask my assigned broker to review” alongside Easy Fill. Appeals and fit checks appear below.</p><Link className="secondary button" to="/app">Return to workspace</Link></div> : <div className="broker-list">{rows.map(item => {
      const plan = item.summary.selected?.plan || {};
      const options = [item.summary.selected, ...(item.summary.alternatives || [])].filter(Boolean);
      const activePlan = selected[item.id] || item.proposed_plan_id;
      const isPending = item.status === 'pending_review';
      return <article className="surface broker-card" key={item.id}>
        <div className="section-heading broker-card-heading"><div><span className={`badge ${item.certainty === 'clear' ? 'success' : 'neutral'}`}>{certaintyLabel(item.certainty)}</span><h2>{plan.name || 'Selected plan'}</h2><p>{plan.network_note || `${plan.network || 'Plan'} network`} · {plan.annual_premium != null ? `${aed(plan.annual_premium * 100)} / year` : 'Premium needs review'}</p></div><span className={`badge ${isPending ? 'neutral' : 'success'}`}>{isPending ? 'Awaiting broker' : 'Approved'}</span></div>
        <div className="broker-grid"><section className="decision-brief"><span className="eyebrow">DECISION BRIEF</span><h3>{item.summary.decision_brief?.requested_decision || 'Review this recommendation.'}</h3><p>{item.summary.decision_brief?.next_action}</p>{item.summary.decision_brief?.main_uncertainty && <p className="broker-uncertainty"><AlertCircle size={16}/>{item.summary.decision_brief.main_uncertainty}</p>}</section>
          <section><h3>Why this plan was selected</h3><ul className="broker-points">{(item.summary.selected?.reasons || []).map((reason: string) => <li key={reason}><Check size={15}/>{reason}</li>)}{[...(item.summary.selected?.tradeoffs || []), ...(item.summary.selected?.gaps || []), ...(item.summary.selected?.unknowns || [])].map((reason: string) => <li className="gap" key={reason}><AlertCircle size={15}/>{reason}</li>)}</ul></section></div>
        {isPending ? <div className="broker-review-form"><div className="form-grid"><label className="field">Supported plan to approve<select value={activePlan} onChange={event => setSelected(current => ({ ...current, [item.id]: event.target.value }))}>{options.filter(option => option.status === 'supported').map(option => <option key={option.plan.id} value={option.plan.id}>{option.plan.name} · {aed(option.premium_fils)}</option>)}</select></label><label className="field">Review note <input value={notes[item.id] || ''} maxLength={2000} onChange={event => setNotes(current => ({ ...current, [item.id]: event.target.value }))} placeholder="Optional reason or handoff note"/></label></div><div className="actions"><button disabled={busyId === item.id} onClick={() => void review(item, activePlan === item.proposed_plan_id ? 'approve' : 'edit')}><Check size={17}/>{busyId === item.id ? 'Saving review…' : activePlan === item.proposed_plan_id ? 'Approve recommendation' : 'Approve changed plan'}</button><Link className="text-link" to={`/app/quotes/${item.quote_id}`}>Open comparison <ArrowRight size={16}/></Link></div></div> : <div className="broker-approved"><Check size={17}/><span>The member can now review and confirm this application.</span><Link className="text-link" to={`/app/quotes/${item.quote_id}`}>View comparison <ArrowRight size={16}/></Link></div>}
      </article>;
    })}</div>}
    <MarketplaceBrokerPanel/>
    <section className="broker-appeals"><div className="section-heading"><div><span className="eyebrow">POLICY SERVICING</span><h2>Appeals</h2><p>Record an uphold or a corrected effective decision. The original servicing history stays visible.</p></div><span className="badge neutral">{pendingAppeals.length} awaiting review</span></div>{appeals.isLoading ? <Loading/> : appeals.error ? <ErrorView error={appeals.error}/> : !appealRows.length ? <p className="muted">No servicing appeals have been submitted.</p> : <div className="broker-list">{appealRows.map(item => { const action = appealActions[item.id] || 'uphold'; return <article className="surface broker-card" key={item.id}><div className="section-heading broker-card-heading"><div><span className={`badge ${item.status === 'reviewed' ? 'success' : 'neutral'}`}>{item.status === 'reviewed' ? 'Reviewed' : 'Awaiting broker'}</span><h2>Appeal {item.appeal_id}</h2><p>Contests {item.appeal.contested_event_id} · {item.contested_decision?.reason_code?.replaceAll('_', ' ') || 'Decision detail unavailable'}</p></div></div><div className="broker-grid"><section className="decision-brief"><span className="eyebrow">MEMBER STATEMENT</span><p>{item.appeal.statement}</p>{item.appeal.evidence?.length ? <p className="source-label">Evidence: {item.appeal.evidence.join(', ')}</p> : null}</section><section><h3>Original decision</h3><ul className="broker-points"><li><Check size={15}/>Outcome: {item.contested_decision?.outcome?.replaceAll('_', ' ') || 'Unavailable'}</li><li><Check size={15}/>Plan payment: {item.contested_decision?.plan_pays_fils != null ? aed(item.contested_decision.plan_pays_fils) : 'Not applicable'}</li></ul></section></div>{item.status === 'pending_review' ? <div className="broker-review-form"><div className="form-grid"><label className="field">Decision<select value={action} onChange={event => setAppealActions(current => ({ ...current, [item.id]: event.target.value as 'uphold' | 'overturn' }))}><option value="uphold">Uphold recorded decision</option><option value="overturn">Overturn with verified correction</option></select></label>{action === 'overturn' && <><label className="field">Correction type<select value={appealCorrections[item.id] || 'policy_month'} onChange={event => setAppealCorrections(current => ({ ...current, [item.id]: event.target.value as 'policy_month' | 'network_membership' }))}><option value="policy_month">Corrected treatment month</option>{item.contested_decision?.reason_code === 'provider_out_of_network' && !!item.appeal.evidence?.length && <option value="network_membership">Verified provider network membership</option>}</select></label>{(appealCorrections[item.id] || 'policy_month') === 'policy_month' ? <label className="field">Corrected policy month<input required type="number" min="0" max="1200" value={appealMonths[item.id] || ''} onChange={event => setAppealMonths(current => ({ ...current, [item.id]: event.target.value }))}/></label> : <><label className="field">Evidence checked<select value={appealEvidence[item.id] || ''} onChange={event => setAppealEvidence(current => ({ ...current, [item.id]: event.target.value }))}><option value="">Choose attached evidence</option>{item.appeal.evidence.map(evidence => <option key={evidence} value={evidence}>{evidence}</option>)}</select></label><label className="field">Licensed provider name<input value={appealProviders[item.id] || ''} onChange={event => setAppealProviders(current => ({ ...current, [item.id]: event.target.value }))}/></label><label className="field">Verified network tier<select value={appealNetworks[item.id] || ''} onChange={event => setAppealNetworks(current => ({ ...current, [item.id]: event.target.value as 'restricted' | 'standard' | 'wide' }))}><option value="">Choose verified tier</option><option value="restricted">Restricted</option><option value="standard">Standard</option><option value="wide">Wide</option></select></label></>}</>}<label className="field">Review note<input value={appealNotes[item.id] || ''} maxLength={2000} onChange={event => setAppealNotes(current => ({ ...current, [item.id]: event.target.value }))} placeholder="Reason for this decision"/></label></div><button disabled={busyId === item.id || (action === 'overturn' && (!appealNotes[item.id]?.trim() || ((appealCorrections[item.id] || 'policy_month') === 'policy_month' ? !appealMonths[item.id] : !appealProviders[item.id]?.trim() || !appealEvidence[item.id] || !appealNetworks[item.id])))} onClick={() => void reviewAppeal(item)}><Check size={17}/>{busyId === item.id ? 'Saving review…' : action === 'uphold' ? 'Uphold appeal decision' : 'Overturn and replay ledger'}</button></div> : <div className="broker-approved"><Check size={17}/><span>Appeal review has been appended to the policy history.</span></div>}</article>; })}</div>}</section>
    <section className="broker-appeals"><div className="section-heading"><div><span className="eyebrow">POLICY FIT</span><h2>Reassessments</h2><p>Review the current profile against the frozen fictional plan and its effective servicing history. This only records a recommendation; it does not switch cover.</p></div><span className="badge neutral">{pendingReassessments.length} awaiting review</span></div>{reassessments.isLoading ? <Loading/> : reassessments.error ? <ErrorView error={reassessments.error}/> : !reassessmentRows.length ? <p className="muted">No policy fit reassessments have been requested.</p> : <div className="broker-list">{reassessmentRows.map(item => { const current = item.report.current; const options = [current, ...(item.report.alternatives || [])].filter(option => option.status === 'supported'); const selectedPlan = reassessmentPlans[item.id] || item.recommended_plan_id || current.plan.id; return <article className="surface broker-card" key={item.id}><div className="section-heading broker-card-heading"><div><span className={`badge ${item.status === 'reviewed' ? 'success' : 'neutral'}`}>{item.status === 'reviewed' ? 'Reviewed' : item.report.outcome === 'retain' ? 'Retain supported' : 'Review recommended'}</span><h2>{current.plan.name}</h2><p>Current policy fit check · {item.report.history_event_ids.length} effective servicing event(s) considered</p></div></div><div className="broker-grid"><section className="decision-brief"><span className="eyebrow">FIT FINDINGS</span>{item.report.findings.map(finding => <p key={finding}>{finding}</p>)}</section><section><h3>Supported options</h3><ul className="broker-points">{options.map(option => <li key={option.plan.id}><Check size={15}/>{option.plan.name} · {aed(option.premium_fils)} / year</li>)}</ul></section></div>{item.status === 'pending_review' ? <div className="broker-review-form"><div className="form-grid"><label className="field">Recorded recommendation<select value={selectedPlan} onChange={event => setReassessmentPlans(currentPlans => ({ ...currentPlans, [item.id]: event.target.value }))}>{options.map(option => <option key={option.plan.id} value={option.plan.id}>{option.plan.name}</option>)}</select></label><label className="field">Review note<input value={reassessmentNotes[item.id] || ''} maxLength={2000} onChange={event => setReassessmentNotes(currentNotes => ({ ...currentNotes, [item.id]: event.target.value }))} placeholder="Reason for retain or future recommendation"/></label></div><button disabled={busyId === item.id} onClick={() => void reviewReassessment(item)}><Check size={17}/>{busyId === item.id ? 'Saving review…' : selectedPlan === current.plan.id ? 'Retain current policy' : 'Record future recommendation'}</button></div> : <div className="broker-approved"><Check size={17}/><span>Recorded recommendation: {item.recommended_plan_id || current.plan.id}. No policy was changed.</span></div>}</article>; })}</div>}</section>
    <button className="quiet broker-refresh" onClick={() => { void recommendations.refetch(); void appeals.refetch(); void reassessments.refetch(); }}><RefreshCw size={16}/> Refresh workspace</button>
  </>;
}
