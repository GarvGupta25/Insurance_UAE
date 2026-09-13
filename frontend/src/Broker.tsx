import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertCircle, ArrowRight, Check, ClipboardCheck, RefreshCw } from 'lucide-react';
import { api, post, aed } from './api';
import { ErrorView, Loading } from './Shopping';

type Recommendation = {
  id: string;
  quote_id: string;
  proposed_plan_id: string;
  status: 'pending_review' | 'approved';
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

function certaintyLabel(certainty: Recommendation['certainty']) {
  return certainty === 'clear' ? 'Clear fit' : certainty === 'tradeoff' ? 'Tradeoffs to review' : 'Terms missing';
}

export function BrokerWorkspace() {
  const query = useQueryClient();
  const recommendations = useQuery<Recommendation[]>({ queryKey: ['broker-recommendations'], queryFn: () => api('/api/broker/recommendations') });
  const appeals = useQuery<Appeal[]>({ queryKey: ['broker-appeals'], queryFn: () => api('/api/broker/appeals') });
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [selected, setSelected] = useState<Record<string, string>>({});
  const [busyId, setBusyId] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [appealNotes, setAppealNotes] = useState<Record<string, string>>({});
  const [appealActions, setAppealActions] = useState<Record<string, 'uphold' | 'overturn'>>({});
  const [appealMonths, setAppealMonths] = useState<Record<string, string>>({});

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
    setBusyId(item.id); setError(''); setMessage('');
    try {
      await post(`/api/broker/appeals/${item.id}/review`, {
        action,
        note: appealNotes[item.id] || (action === 'uphold' ? 'The recorded decision remains supported.' : 'The corrected policy month is supported by the submitted evidence.'),
        ...(action === 'overturn' ? { corrected_policy_month: Number(appealMonths[item.id]) } : {}),
      });
      await query.invalidateQueries({ queryKey: ['broker-appeals'] });
      setMessage(`Appeal ${action === 'uphold' ? 'upheld' : 'overturned'} and recorded in the servicing history.`);
      window.setTimeout(() => setMessage(''), 6000);
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'The appeal review could not be saved.'); }
    finally { setBusyId(''); }
  }

  if (recommendations.isLoading) return <Loading/>;
  if (recommendations.error) return <ErrorView error={recommendations.error}/>;
  const rows = recommendations.data || [];
  const pending = rows.filter(item => item.status === 'pending_review');
  const uncertain = pending.filter(item => item.certainty !== 'clear');
  const appealRows = appeals.data || [];
  const pendingAppeals = appealRows.filter(item => item.status === 'pending_review');

  return <>
    <div className="page-heading compact"><div><span className="eyebrow">BROKER WORKSPACE</span><h1>Review the recommendation.<br/>Keep the member in control.</h1><p>Check the documented fit and approve or change the supported plan before the member submits.</p></div><ClipboardCheck className="heading-icon" size={54}/></div>
    <div className="notice broker-notice"><AlertCircle size={19}/><div><strong>Demonstration review</strong><br/>This workspace uses the same demo account for the member and broker. Production broker assignment and role controls are not configured.</div></div>
    <div className="metric-grid broker-metrics"><div><span>Awaiting review</span><strong>{pending.length}</strong><small>Prepared applications needing a decision</small></div><div><span>Needs attention</span><strong>{uncertain.length + pendingAppeals.length}</strong><small>Recommendations or appeals awaiting a decision</small></div><div><span>Reviewed</span><strong>{rows.length - pending.length}</strong><small>Recommendations ready for member confirmation</small></div></div>
    {message && <div className="notice" role="status">{message}</div>}
    {error && <ErrorView error={new Error(error)}/>} 
    {!rows.length ? <div className="empty-state"><ClipboardCheck size={32}/><h3>Nothing is waiting for review.</h3><p>Prepared recommendations will appear here after a member selects Easy Fill.</p><Link className="secondary button" to="/app">Return to workspace</Link></div> : <div className="broker-list">{rows.map(item => {
      const plan = item.summary.selected?.plan || {};
      const options = [item.summary.selected, ...(item.summary.alternatives || [])].filter(Boolean);
      const activePlan = selected[item.id] || item.proposed_plan_id;
      const isPending = item.status === 'pending_review';
      return <article className="surface broker-card" key={item.id}>
        <div className="section-heading broker-card-heading"><div><span className={`badge ${item.certainty === 'clear' ? 'success' : 'neutral'}`}>{certaintyLabel(item.certainty)}</span><h2>{plan.name || 'Selected plan'}</h2><p>{plan.network_note || `${plan.network || 'Plan'} network`} · {plan.annual_premium != null ? `${aed(plan.annual_premium * 100)} / year` : 'Premium needs review'}</p></div><span className={`badge ${isPending ? 'neutral' : 'success'}`}>{isPending ? 'Awaiting broker' : 'Approved'}</span></div>
        <div className="broker-grid"><section className="decision-brief"><span className="eyebrow">DECISION BRIEF</span><h3>{item.summary.decision_brief?.requested_decision || 'Review this recommendation.'}</h3><p>{item.summary.decision_brief?.next_action}</p>{item.summary.decision_brief?.main_uncertainty && <p className="broker-uncertainty"><AlertCircle size={16}/>{item.summary.decision_brief.main_uncertainty}</p>}</section>
          <section><h3>Why this plan was selected</h3><ul className="broker-points">{(item.summary.selected?.reasons || []).map((reason: string) => <li key={reason}><Check size={15}/>{reason}</li>)}{[...(item.summary.selected?.gaps || []), ...(item.summary.selected?.unknowns || [])].map((reason: string) => <li className="gap" key={reason}><AlertCircle size={15}/>{reason}</li>)}</ul></section></div>
        {isPending ? <div className="broker-review-form"><div className="form-grid"><label className="field">Supported plan to approve<select value={activePlan} onChange={event => setSelected(current => ({ ...current, [item.id]: event.target.value }))}>{options.filter(option => option.status === 'supported').map(option => <option key={option.plan.id} value={option.plan.id}>{option.plan.name} · {aed(option.premium_fils)}</option>)}</select></label><label className="field">Review note <input value={notes[item.id] || ''} maxLength={2000} onChange={event => setNotes(current => ({ ...current, [item.id]: event.target.value }))} placeholder="Optional reason or handoff note"/></label></div><div className="actions"><button disabled={busyId === item.id} onClick={() => void review(item, activePlan === item.proposed_plan_id ? 'approve' : 'edit')}><Check size={17}/>{busyId === item.id ? 'Saving review…' : activePlan === item.proposed_plan_id ? 'Approve recommendation' : 'Approve changed plan'}</button><Link className="text-link" to={`/app/quotes/${item.quote_id}`}>Open comparison <ArrowRight size={16}/></Link></div></div> : <div className="broker-approved"><Check size={17}/><span>The member can now review and confirm this application.</span><Link className="text-link" to={`/app/quotes/${item.quote_id}`}>View comparison <ArrowRight size={16}/></Link></div>}
      </article>;
    })}</div>}
    <section className="broker-appeals"><div className="section-heading"><div><span className="eyebrow">POLICY SERVICING</span><h2>Appeals</h2><p>Record an uphold or a corrected effective decision. The original servicing history stays visible.</p></div><span className="badge neutral">{pendingAppeals.length} awaiting review</span></div>{appeals.isLoading ? <Loading/> : appeals.error ? <ErrorView error={appeals.error}/> : !appealRows.length ? <p className="muted">No servicing appeals have been submitted.</p> : <div className="broker-list">{appealRows.map(item => { const action = appealActions[item.id] || 'uphold'; return <article className="surface broker-card" key={item.id}><div className="section-heading broker-card-heading"><div><span className={`badge ${item.status === 'reviewed' ? 'success' : 'neutral'}`}>{item.status === 'reviewed' ? 'Reviewed' : 'Awaiting broker'}</span><h2>Appeal {item.appeal_id}</h2><p>Contests {item.appeal.contested_event_id} · {item.contested_decision?.reason_code?.replaceAll('_', ' ') || 'Decision detail unavailable'}</p></div></div><div className="broker-grid"><section className="decision-brief"><span className="eyebrow">MEMBER STATEMENT</span><p>{item.appeal.statement}</p>{item.appeal.evidence?.length ? <p className="source-label">Evidence: {item.appeal.evidence.join(', ')}</p> : null}</section><section><h3>Original decision</h3><ul className="broker-points"><li><Check size={15}/>Outcome: {item.contested_decision?.outcome?.replaceAll('_', ' ') || 'Unavailable'}</li><li><Check size={15}/>Plan payment: {item.contested_decision?.plan_pays_fils != null ? aed(item.contested_decision.plan_pays_fils) : 'Not applicable'}</li></ul></section></div>{item.status === 'pending_review' ? <div className="broker-review-form"><div className="form-grid"><label className="field">Decision<select value={action} onChange={event => setAppealActions(current => ({ ...current, [item.id]: event.target.value as 'uphold' | 'overturn' }))}><option value="uphold">Uphold recorded decision</option><option value="overturn">Overturn with corrected policy month</option></select></label>{action === 'overturn' && <label className="field">Corrected policy month<input required type="number" min="0" max="1200" value={appealMonths[item.id] || ''} onChange={event => setAppealMonths(current => ({ ...current, [item.id]: event.target.value }))}/></label>}<label className="field">Review note<input value={appealNotes[item.id] || ''} maxLength={2000} onChange={event => setAppealNotes(current => ({ ...current, [item.id]: event.target.value }))} placeholder="Reason for this decision"/></label></div><button disabled={busyId === item.id || (action === 'overturn' && !appealMonths[item.id])} onClick={() => void reviewAppeal(item)}><Check size={17}/>{busyId === item.id ? 'Saving review…' : action === 'uphold' ? 'Uphold appeal decision' : 'Overturn and replay ledger'}</button></div> : <div className="broker-approved"><Check size={17}/><span>Appeal review has been appended to the policy history.</span></div>}</article>; })}</div>}</section>
    <button className="quiet broker-refresh" onClick={() => { void recommendations.refetch(); void appeals.refetch(); }}><RefreshCw size={16}/> Refresh workspace</button>
  </>;
}
