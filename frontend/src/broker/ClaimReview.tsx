import { useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, Check, FileText, MessageSquare } from 'lucide-react';
import { api, auth, post } from '../api';
import { ErrorView, Loading } from '../Shopping';
import { ClaimOperations } from './ClaimOperations';

type ReviewAction = 'approve' | 'partially_approve' | 'request_more_information' | 'deny' | 'medical_review' | 'escalate_to_senior_broker';
type Claim = {
  id: string;
  created_at: string;
  is_emergency: boolean;
  intake: { kind: string; raw_message: string | null; structured_fields: Record<string, unknown> };
  policy: { id: string; status: string; plan: Record<string, any> };
  claimant: { id: string; name: string | null };
  documents: Array<{ id: string; doc_type: string; extracted_fields: Record<string, unknown>; completeness_ok: boolean; has_original: boolean }>;
  flags: Array<{ id: string; flag_type: string; reason: string }>;
  transcript: Array<{ role: string; content: string }>;
  suggested_action: { action: ReviewAction; reasoning: string; source: string };
  case_brief?: { summary: string; document_status: string[]; eligibility: string; cited_clauses: Array<{ clause_id: string; text_snippet: string }>; risk_flags: string[]; suggested_action: ReviewAction; rationale: string };
  provisional_amount_fils?: number | null;
};

const actionLabels: Record<ReviewAction, string> = {
  approve: 'Approve',
  partially_approve: 'Partially approve',
  request_more_information: 'Request more information',
  deny: 'Deny',
  medical_review: 'Medical review',
  escalate_to_senior_broker: 'Escalate to senior broker',
};

function show(value: unknown) {
  return value == null || value === '' ? 'Not provided' : typeof value === 'object' ? JSON.stringify(value) : String(value);
}

function OriginalPreview({ claimId, documentId }: { claimId: string; documentId: string }) {
  const [url, setUrl] = useState('');
  const [mediaType, setMediaType] = useState('');
  const [error, setError] = useState('');
  const [open, setOpen] = useState(false);
  useEffect(() => () => { if (url) URL.revokeObjectURL(url); }, [url]);
  async function view() {
    if (open) { setOpen(false); return; }
    if (url) { setOpen(true); return; }
    setError('');
    try {
      const session = auth ? (await auth.auth.getSession()).data.session : null;
      const response = await fetch(`/api/broker/claims/${claimId}/documents/${documentId}/original`, {
        headers: session ? { Authorization: `Bearer ${session.access_token}` } : {},
      });
      if (!response.ok) throw new Error('The original file could not be opened. Please retry.');
      setMediaType(response.headers.get('Content-Type') || '');
      setUrl(URL.createObjectURL(await response.blob()));
      setOpen(true);
    } catch (reason) { setError((reason as Error).message); }
  }
  return <div className="claim-original"><div><button type="button" className="secondary" onClick={() => void view()}>{open ? 'Hide original' : 'View original image or PDF'}</button>{url && <a className="button secondary" href={url} download={`claim-document.${mediaType === 'application/pdf' ? 'pdf' : mediaType === 'image/png' ? 'png' : 'jpg'}`}>Download original</a>}</div>{error && <span role="alert">{error}</span>}{open && url && (mediaType === 'application/pdf' ? <iframe title="Uploaded claim PDF" src={url}/> : <img alt="Uploaded claim document" src={url}/>)}</div>;
}

export function ClaimReview() {
  const query = useQueryClient();
  const claims = useQuery<Claim[]>({ queryKey: ['broker-claims'], queryFn: () => api('/api/broker/claims'), refetchInterval: 10000 });
  const analytics = useQuery<{ total_intakes: number; straight_through: number; straight_through_rate_pct: number; definition: string }>({ queryKey: ['broker-claim-analytics'], queryFn: () => api('/api/broker/claims/analytics') });
  const [selectedId, setSelectedId] = useState('');
  const [actions, setActions] = useState<Record<string, ReviewAction>>({});
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  async function takeShift() {
    setBusy(true); setError('');
    try {
      const start = new Date(); const end = new Date(start.getTime() + 8 * 60 * 60 * 1000);
      await post('/api/broker/claims/on-call-shifts', { shift_start: start.toISOString(), shift_end: end.toISOString() });
      await query.invalidateQueries({ queryKey: ['broker-claims'] });
      setMessage(`On-call shift started until ${end.toLocaleTimeString()}. Emergency pages require the configured paging connection.`);
    } catch (reason) { setError((reason as Error).message); } finally { setBusy(false); }
  }

  if (claims.isLoading) return <Loading/>;
  if (claims.error) return <ErrorView error={claims.error}/>;
  const rows = claims.data || [];
  const selected = rows.find(claim => claim.id === selectedId) || rows[0];

  async function confirm(claim: Claim) {
    const action = actions[claim.id] || claim.suggested_action.action;
    const note = notes[claim.id]?.trim();
    if (!note) { setError('Add a reviewer note before confirming this action.'); return; }
    setBusy(true); setError(''); setMessage('');
    try {
      await post(`/api/broker/claims/${claim.id}/review`, { action, note });
      await query.invalidateQueries({ queryKey: ['broker-claims'] });
      setMessage(`${actionLabels[action]} was appended to the claim review history.`);
      setSelectedId('');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The claim review could not be saved.');
    } finally { setBusy(false); }
  }

  async function reviewAppeal(claim: Claim, action: 'uphold' | 'reopen_for_review') {
    const note = notes[claim.id]?.trim();
    if (!note) { setError('Add a reviewer note before deciding this appeal.'); return; }
    setBusy(true); setError('');
    try { await post(`/api/broker/claims/${claim.id}/appeal-review`, { action, note }); setMessage(`Appeal ${action.replaceAll('_', ' ')} recorded by you.`); await query.invalidateQueries({ queryKey: ['broker-claims'] }); }
    catch (reason) { setError((reason as Error).message); } finally { setBusy(false); }
  }

  return <>
    <div className="page-heading compact"><div><span className="eyebrow">BROKER CLAIM REVIEW</span><h1>Review flagged claims.<br/>Keep every decision human.</h1><p>Emergency claims stay first. Claim Agent suggestions are drafts; edit and confirm the action yourself.</p></div><FileText className="heading-icon" size={54}/></div>
    <button className="secondary" disabled={busy} onClick={() => void takeShift()}>Start an 8-hour on-call shift</button>
    {analytics.data && <section className="claim-analytics" aria-label="Claim straight-through performance"><span>Claim straight-through rate</span><strong>{analytics.data.straight_through_rate_pct}%</strong><small>{analytics.data.straight_through} of {analytics.data.total_intakes} intakes · {analytics.data.definition}</small></section>}
    <ClaimOperations/>
    {message && <div className="notice" role="status">{message}</div>}
    {error && <ErrorView error={new Error(error)}/>} 
    {!rows.length ? <div className="empty-state"><Check size={32}/><h3>No flagged claims need review.</h3><p>New assigned claims with open flags will appear here.</p></div> : <div className="claim-review-layout">
      <aside className="claim-review-queue" aria-label="Claims awaiting review">
        <div className="claim-review-queue-heading"><strong>{rows.length} awaiting review</strong><small>Emergency claims are pinned first</small></div>
        {rows.map(claim => <button key={claim.id} className={`claim-review-item ${claim.is_emergency ? 'emergency' : ''} ${selected?.id === claim.id ? 'selected' : ''}`} onClick={() => { setSelectedId(claim.id); setError(''); }}>
          <span className={`badge ${claim.is_emergency ? 'urgent' : 'neutral'}`}>{claim.is_emergency ? 'Emergency' : claim.intake.kind.replaceAll('_', ' ')}</span>
          <strong>{claim.claimant.name || 'Assigned member'}</strong>
          <small>{claim.policy.plan.name || 'Policy'} · {new Date(claim.created_at).toLocaleDateString()}</small>
          <span>{claim.flags[0]?.reason}</span>
        </button>)}
      </aside>
      {selected && <article className={`surface claim-review-detail ${selected.is_emergency ? 'emergency' : ''}`}>
        {selected.is_emergency && <div className="claim-emergency-banner"><AlertTriangle size={20}/><strong>Emergency claim — review before all non-emergency work.</strong></div>}
        {selected.provisional_amount_fils != null && <div className="notice"><strong>Provisional — pending final decision: AED {(selected.provisional_amount_fils / 100).toFixed(2)}</strong><p>Sandbox authorization only. Compare with the final deterministic decision before closing review.</p></div>}
        {selected.intake.kind === 'appeal' && <div className="notice"><strong>Appeals are human-decided.</strong><p>Inspect the original reason, member statement and new evidence below. Neither agent nor auto rule can decide this.</p></div>}
        <div className="section-heading"><div><span className="eyebrow">COMPLETE CLAIM INTAKE</span><h2>{selected.claimant.name || 'Assigned member'} · {selected.intake.kind.replaceAll('_', ' ')}</h2><p>Policy {selected.policy.id} · {selected.policy.plan.name || selected.policy.status}</p></div></div>
        <section className="claim-detail-section"><h3>Intake fields</h3><dl className="claim-field-grid">{Object.entries(selected.intake.structured_fields).filter(([key]) => key !== 'follow_up').map(([key, value]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{show(value)}</dd></div>)}</dl></section>
        <section className="claim-detail-section"><h3>Open flags</h3>{selected.flags.map(flag => <div className="claim-flag" key={flag.id}><AlertTriangle size={17}/><div><strong>{flag.flag_type.replaceAll('_', ' ')}</strong><p>{flag.reason}</p></div></div>)}</section>
        <section className="claim-detail-section"><h3>Documents</h3>{selected.documents.map(document => <article className="claim-document" key={document.id}><div><FileText size={17}/><strong>{document.doc_type.replaceAll('_', ' ')}</strong><span className={`badge ${document.completeness_ok ? 'success' : 'urgent'}`}>{document.completeness_ok ? 'Complete' : 'Incomplete'}</span></div>{document.has_original ? <OriginalPreview claimId={selected.id} documentId={document.id}/> : <p className="muted">Original file unavailable. Ask the member to upload it again.</p>}<dl>{Object.entries(document.extracted_fields || {}).map(([key, value]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{show(value)}</dd></div>)}</dl></article>)}</section>
        <section className="claim-detail-section"><h3>Full Claim Agent transcript</h3><div className="claim-transcript">{selected.transcript.length ? selected.transcript.map((message, index) => <div key={`${message.role}-${index}`}><MessageSquare size={16}/><p><strong>{message.role.replaceAll('_', ' ')}</strong>{message.content}</p></div>) : <p className="muted">This structured intake has no chat transcript.</p>}</div></section>
        {selected.case_brief && <section className="claim-detail-section"><h3>Case brief · suggestion only</h3><p>{selected.case_brief.summary}</p><p>Policy match: {selected.case_brief.eligibility}</p>{selected.case_brief.cited_clauses.map(clause => <p key={clause.clause_id}>{clause.clause_id}: {clause.text_snippet}</p>)}{selected.case_brief.document_status.map(doc => <p key={doc}>Missing: {doc}</p>)}{selected.case_brief.risk_flags.map(flag => <p key={flag}>{flag}</p>)}<p>Suggested next step: {actionLabels[selected.case_brief.suggested_action]}. {selected.case_brief.rationale}</p></section>}
        <section className="claim-suggestion"><span className="eyebrow">CLAIM AGENT DRAFT · HUMAN REVIEW REQUIRED</span><h3>{actionLabels[selected.suggested_action.action]}</h3><p>{selected.suggested_action.reasoning}</p></section>
        <div className="broker-review-form"><div className="form-grid">{selected.intake.kind !== 'appeal' && <label className="field">Reviewer action<select value={actions[selected.id] || selected.suggested_action.action} onChange={event => setActions(current => ({ ...current, [selected.id]: event.target.value as ReviewAction }))}>{Object.entries(actionLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>}<label className="field">Reviewer note<textarea required maxLength={2000} value={notes[selected.id] || ''} onChange={event => setNotes(current => ({ ...current, [selected.id]: event.target.value }))} placeholder="Record the evidence and reason for this action."/></label></div><p className="muted">Payable actions use the verified intake and deterministic servicing rules. No manual payment amount can be entered.</p>{selected.intake.kind === 'appeal' ? <div><button disabled={busy || !notes[selected.id]?.trim()} onClick={() => void reviewAppeal(selected, 'uphold')}>Uphold denial</button> <button disabled={busy || !notes[selected.id]?.trim()} onClick={() => void reviewAppeal(selected, 'reopen_for_review')}>Reopen for review</button></div> : <button disabled={busy || !notes[selected.id]?.trim()} onClick={() => void confirm(selected)}><Check size={17}/>{busy ? 'Recording action…' : `Confirm ${actionLabels[actions[selected.id] || selected.suggested_action.action]}`}</button>}</div>
      </article>}
    </div>}
  </>;
}
