import { useState } from 'react';
import { Check, ChevronDown, UploadCloud, LoaderCircle } from 'lucide-react';
import { api, post } from './api';
import { FormActions } from './FormActions';

const extendedGroups = ['About you', 'Health and cover', 'Funding and preferences'];
const challengeGroups = ['About you', 'Health and upcoming care', 'Budget and priorities'];
type Field = { key: string; label: string; type?: string; options?: string[] };
const challengeRegistry: Field[][] = [
  [{ key: 'display_name', label: 'Name to display (optional)' }, { key: 'age', label: 'Age', type: 'number' }, { key: 'marital_status', label: 'Marital status', options: ['single', 'married', 'divorced', 'widowed'] }, { key: 'smoker', label: 'Do you smoke?', options: ['yes', 'no', 'unknown', 'declined'] }],
  [{ key: 'diagnosed_conditions', label: 'Diagnosed conditions', options: ['yes', 'no', 'unknown', 'declined'] }, { key: 'conditions', label: 'Declared conditions, separated by commas', type: 'list' }, { key: 'near_term_needs', label: 'Upcoming care needs, separated by commas', type: 'list' }],
  [{ key: 'budget_category', label: 'Budget comfort', options: ['low', 'moderate', 'comfortable', 'not primary concern'] }, { key: 'priorities', label: 'What matters most, separated by commas', type: 'list' }],
];
const extendedRegistry: Field[][] = [
  [{ key: 'legal_name', label: 'Full name' }, { key: 'date_of_birth', label: 'Date of birth', type: 'date' }, { key: 'nationality', label: 'Nationality' }, { key: 'residency', label: 'Residency', options: ['citizen', 'resident', 'visitor', 'pending'] }, { key: 'emirate', label: 'Emirate', options: ['Dubai', 'Abu Dhabi', 'Sharjah', 'Ajman', 'Fujairah', 'Ras Al Khaimah', 'Umm Al Quwain'] }, { key: 'emirates_id_status', label: 'Emirates ID status', options: ['issued', 'application_pending', 'not_applicable_visitor'] }, { key: 'area', label: 'City / area (optional)' }, { key: 'mobile', label: 'Mobile (optional)' }],
  [{ key: 'diagnosed_conditions', label: 'Diagnosed conditions', options: ['yes', 'no', 'unknown', 'declined'] }, { key: 'conditions', label: 'Conditions, separated by commas', type: 'list' }, { key: 'medications', label: 'Regular medicines (optional)', type: 'list' }, { key: 'existing_cover', label: 'Existing insurance (optional)', options: ['yes', 'no', 'unknown', 'declined'] }, { key: 'smoker', label: 'Do you smoke?', options: ['yes', 'no', 'unknown', 'declined'] }, { key: 'maternity', label: 'Include maternity?', type: 'boolean' }, { key: 'maximum_maternity_wait', label: 'Maximum maternity wait (months)', type: 'number' }, { key: 'immediate_chronic_cover', label: 'Existing-condition cover from day one?', type: 'boolean' }, { key: 'geography', label: 'Where do you need cover?', options: ['UAE', 'international', 'unsure'] }, { key: 'start_date', label: 'Desired coverage start', type: 'date' }, { key: 'upcoming_care', label: 'Upcoming care (optional)' }, { key: 'dental', label: 'Dental / optical preference', options: ['none', 'basic', 'full'] }, { key: 'preferred_network', label: 'Preferred network', options: ['restricted', 'standard', 'wide'] }, { key: 'preferred_provider', label: 'Preferred hospital or clinic (optional)' }],
  [{ key: 'payer', label: 'Who will pay?', options: ['self', 'employer', 'sponsor'] }, { key: 'annual_budget', label: 'Annual budget (AED)', type: 'number' }, { key: 'strict_budget', label: 'Is this a strict maximum?', type: 'boolean' }, { key: 'payment_frequency', label: 'Payment preference', options: ['annual', 'monthly'] }, { key: 'cost_sharing', label: 'Cost preference', options: ['lower_premium', 'lower_member_cost', 'balanced'] }, { key: 'company_name', label: 'Employer company name' }, { key: 'sponsor_name', label: 'Sponsor name' }, { key: 'sponsor_relationship', label: 'Sponsor relationship' }, { key: 'contribution_aed', label: 'Employer / sponsor contribution (AED)', type: 'number' }],
];
export function ProfileEditor({ profile, onSaved }: { profile: any; onSaved: () => void }) {
  const [tab, setTab] = useState(0); const [draft, setDraft] = useState<Record<string, any>>({}); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  const [useExtended, setUseExtended] = useState(false);
  const [extraction, setExtraction] = useState<any>(null);
  const [autoAdvance, setAutoAdvance] = useState(true);
  const [savedNotice, setSavedNotice] = useState('');
  const facts = { ...profile.facts, ...draft };
  const missing: string[] = profile.readiness.missing;
  const challenge = profile.readiness.mode === 'challenge' && !useExtended;
  const groups = challenge ? challengeGroups : extendedGroups;
  const registry = challenge ? challengeRegistry : extendedRegistry;
  function set(field: Field, value: string) {
    const parsed = value === '' ? null : field.type === 'number' ? Number(value) : field.type === 'boolean' ? value === 'true' : field.type === 'list' ? value.split(',').map(s => s.trim()).filter(Boolean) : value;
    setDraft(d => ({ ...d, [field.key]: parsed }));
  }
  async function save() {
    setError(''); setBusy(true);
    try { await api('/api/me/profile', { method: 'PATCH', body: JSON.stringify({ expected_version: profile.version, changes: draft }) }); setDraft({}); onSaved(); if (autoAdvance && tab < groups.length - 1 && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) { setSavedNotice(`Saved — moving to ${groups[tab + 1]}`); window.setTimeout(() => setTab(current => Math.min(current + 1, groups.length - 1)), 650); } }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  async function upload(file: File) {
    if (file.size > 10 * 1024 * 1024) { setError('Use a document smaller than 10 MB.'); return; }
    setBusy(true); setError(''); const form = new FormData(); form.append('file', file);
    try { setExtraction(await api('/api/documents', { method: 'POST', body: form })); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  async function accept() {
    setBusy(true); setError('');
    try { await post(`/api/extractions/${extraction.id}/accept`, { expected_version: profile.version, changes: extraction.fields }); setExtraction(null); onSaved(); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  return <section className="profile-editor" aria-label="Editable insurance profile">
    <div className="section-heading"><div><span className="eyebrow">YOUR DETAILS</span><h2>One profile. Every step.</h2></div><span className="badge neutral">{missing.length ? `${missing.length} details to go` : 'Ready to compare'}</span></div>
    {profile.readiness.mode === 'challenge' && <button type="button" className="quiet" onClick={() => { setUseExtended(value => !value); setTab(0); }}>{useExtended ? 'Use the short challenge profile' : 'Add detailed application information (optional)'}</button>}
    <div className="profile-tools"><label><input type="checkbox" checked={autoAdvance} onChange={event => setAutoAdvance(event.target.checked)}/> Auto-advance after save</label><small>Step {tab + 1} of {groups.length} · about {groups.length - tab} minute{groups.length - tab === 1 ? '' : 's'} left</small></div>{savedNotice && <p className="saved-notice" role="status">{savedNotice}</p>}<div className="tabs" role="tablist" aria-label="Profile stages">{groups.map((name, i) => <button role="tab" aria-selected={tab === i} key={name} onClick={() => setTab(i)}>{i + 1}. {name}</button>)}</div>
    {!challenge && tab === 0 && <label className="upload-area"><UploadCloud size={22}/><span><strong>Autofill from an identity document</strong><small>Optional · JPG, PNG or PDF · 10 MB · up to 5 pages</small></span><input aria-label="Upload identity document" type="file" accept="image/jpeg,image/png,application/pdf" disabled={busy} onChange={e => { if (e.target.files?.[0]) void upload(e.target.files[0]); e.target.value = ''; }}/></label>}
    {extraction && <div className="notice"><strong>Review extracted identity details</strong><p>{extraction.notice}</p>{Object.entries(extraction.fields).map(([key, value]) => <label className="field" key={key}>{key.replaceAll('_', ' ')}<input value={String(value)} onChange={e => setExtraction({ ...extraction, fields: { ...extraction.fields, [key]: e.target.value } })}/></label>)}<div className="actions"><button disabled={busy || !Object.keys(extraction.fields).length} onClick={accept}>Accept checked details</button><button className="secondary" onClick={() => setExtraction(null)}>Discard</button></div></div>}
    {facts.emirate && <p className="notice">Applicable regulator: <strong>{facts.emirate === 'Dubai' ? 'DHA' : facts.emirate === 'Abu Dhabi' ? 'DoH' : 'MOHAP'}</strong>. Educational only; this does not determine cover.</p>}
    <div className="form-grid">{registry[tab].filter(f => {
      if (challenge && f.key === 'conditions') return facts.diagnosed_conditions === 'yes';
      if (f.key === 'maximum_maternity_wait') return facts.maternity === true;
      if (f.key === 'immediate_chronic_cover') return facts.diagnosed_conditions === 'yes';
      if (f.key === 'company_name') return facts.payer === 'employer';
      if (['sponsor_name', 'sponsor_relationship'].includes(f.key)) return facts.payer === 'sponsor';
      if (f.key === 'contribution_aed') return ['employer', 'sponsor'].includes(facts.payer);
      return true;
    }).map(field => <label className="field" key={field.key}>{field.label}<span className="input-wrap">{field.options || field.type === 'boolean' ? <><select value={facts[field.key] == null ? '' : String(facts[field.key])} onChange={e => set(field, e.target.value)}><option value="">Choose an answer</option>{(field.options || ['true', 'false']).map(option => <option key={option} value={option}>{option === 'true' ? 'Yes' : option === 'false' ? 'No' : option.replaceAll('_', ' ')}</option>)}</select><ChevronDown size={14}/></> : <input type={field.type === 'list' ? 'text' : field.type || 'text'} min={field.type === 'number' ? 0 : undefined} value={Array.isArray(facts[field.key]) ? facts[field.key].join(', ') : facts[field.key] ?? ''} onChange={e => set(field, e.target.value)}/>}</span></label>)}</div>
    {error && <p role="alert" className="error">{error}</p>}
    <FormActions secondaryLabel={tab ? 'Back' : undefined} onSecondary={() => setTab(value => Math.max(0, value - 1))} primaryDisabled={busy || !Object.keys(draft).length} onPrimary={() => void save()} primaryLabel={<>{busy ? <LoaderCircle size={16} className="spin"/> : <Check size={16}/>} Save details</>}/>
  </section>;
}
