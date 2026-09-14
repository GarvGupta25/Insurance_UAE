import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowRight, Check, CircleAlert, SlidersHorizontal } from 'lucide-react';
import { aed, api, post } from './api';

type Inputs = {
  monthly_budget_aed: number;
  outpatient_spend_aed: number;
  contribution_aed: number;
  priority: 'lower_premium' | 'balanced' | 'lower_member_cost';
};
type PlanResult = {
  plan_id: string;
  name: string;
  fit_status: string;
  premium_fils: number;
  member_premium_fils: number;
  monthly_budget_equivalent_fils: number;
  illustrative_member_care_fils: number;
  annual_planning_total_fils: number;
  within_budget: boolean;
  budget_gap_fils: number;
  gaps: string[];
  unknowns: string[];
};
type Scenario = {
  recommended_plan_id: string | null;
  reply: string;
  rows: PlanResult[];
  assumptions: string[];
};

const startingInputs: Inputs = {
  monthly_budget_aed: 1000,
  outpatient_spend_aed: 3000,
  contribution_aed: 0,
  priority: 'balanced',
};

export function FinancialPlanner({ quoteId, stale, onChoose }: {
  quoteId: string; stale: boolean; onChoose: (planId: string) => void;
}) {
  const query = useQueryClient();
  const profile = useQuery({ queryKey: ['profile'], queryFn: () => api('/api/me/profile') });
  const saved = useQuery({ queryKey: ['financial-scenarios', quoteId], queryFn: () => api(`/api/quotes/${quoteId}/financial-scenarios`) });
  const initialized = useRef(false);
  const [inputs, setInputs] = useState<Inputs>(startingInputs);
  const [preview, setPreview] = useState<Scenario | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (initialized.current || profile.isLoading || saved.isLoading) return;
    initialized.current = true;
    const facts = profile.data?.facts || {};
    setInputs(saved.data?.items?.[0]?.inputs || {
      ...startingInputs,
      monthly_budget_aed: facts.annual_budget ? Math.round(facts.annual_budget / 12) : startingInputs.monthly_budget_aed,
      contribution_aed: facts.contribution_aed || 0,
      priority: facts.cost_sharing || startingInputs.priority,
    });
  }, [profile.isLoading, profile.data, saved.isLoading, saved.data]);

  useEffect(() => {
    if (stale || !initialized.current) return;
    query.setQueryData(['financial-draft', quoteId], inputs);
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      try {
        const result = await api<Scenario>(`/api/quotes/${quoteId}/financial-preview`, {
          method: 'POST', body: JSON.stringify(inputs), signal: controller.signal,
        });
        setPreview(result);
        setError('');
      } catch (caught) {
        if (!controller.signal.aborted) setError((caught as Error).message);
      }
    }, 260);
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [inputs, quoteId, stale]);

  async function save() {
    setBusy(true); setMessage(''); setError('');
    try {
      await post(`/api/quotes/${quoteId}/financial-scenarios`, inputs);
      await query.invalidateQueries({ queryKey: ['financial-scenarios', quoteId] });
      setMessage('Saved to this quotation. You can return to these assumptions later.');
    } catch (caught) { setError((caught as Error).message); }
    finally { setBusy(false); }
  }

  const maximum = Math.max(1, ...(preview?.rows.map(row => row.annual_planning_total_fils) || []));
  return <section className="surface financial-planner" aria-labelledby="financial-title">
    <div className="section-heading"><div><span className="eyebrow">FINANCIAL PLANNING AGENT</span><h2 id="financial-title">Explore what each plan could mean for your budget.</h2><p>Answer three questions. Drag a slider to see the recommendation recalculate from the fictional plan terms.</p></div><SlidersHorizontal size={26} aria-hidden="true"/></div>
    <div className="financial-questions">
      <label className="financial-question"><span><strong>1. What monthly amount feels comfortable for the premium?</strong><output>{aed(inputs.monthly_budget_aed * 100)} per month</output></span><input type="range" min="0" max="5000" step="50" value={inputs.monthly_budget_aed} onChange={event => setInputs(current => ({ ...current, monthly_budget_aed: Number(event.target.value) }))}/><small>This is your budgeting limit, not an instalment offer.</small></label>
      <label className="financial-question"><span><strong>2. What annual eligible outpatient spending would you like to explore?</strong><output>{aed(inputs.outpatient_spend_aed * 100)} per year</output></span><input type="range" min="0" max="30000" step="500" value={inputs.outpatient_spend_aed} onChange={event => setInputs(current => ({ ...current, outpatient_spend_aed: Number(event.target.value) }))}/><small>A hypothetical single-year illustration; it does not predict your care.</small></label>
      <label className="financial-question"><span><strong>Will an employer or sponsor contribute?</strong><output>{aed(inputs.contribution_aed * 100)} per year</output></span><input type="range" min="0" max="20000" step="500" value={inputs.contribution_aed} onChange={event => setInputs(current => ({ ...current, contribution_aed: Number(event.target.value) }))}/><small>Contribution changes your share, not the fictional insurer premium.</small></label>
      <fieldset className="financial-priority"><legend>3. Which trade-off matters most?</legend>{([
        ['lower_premium', 'Lower premium'], ['balanced', 'Balanced annual cost'], ['lower_member_cost', 'Lower cost when care happens'],
      ] as const).map(([value, label]) => <button type="button" className="secondary" aria-pressed={inputs.priority === value} key={value} onClick={() => setInputs(current => ({ ...current, priority: value }))}>{label}</button>)}</fieldset>
    </div>
    {stale && <p className="notice">This quote is stale. Update your profile and make a new quote to explore current options.</p>}
    {error && <p className="error" role="alert">{error}</p>}
    {!stale && !preview && !error && <p className="muted" role="status">Calculating your illustrative choices…</p>}
    {preview && !stale && <div className="financial-results" aria-live="polite">
      <div className="financial-answer"><span className="eyebrow">HELM'S ANSWER</span><p>{preview.reply}</p><button className="secondary" type="button" disabled={busy} onClick={() => void save()}><Check size={16}/> Save this scenario</button>{message && <small role="status">{message}</small>}</div>
      <div className="financial-bars" aria-label="Illustrative annual member cost comparison">{preview.rows.map(row => <div className="financial-row" key={row.plan_id}><div className="financial-row-heading"><strong>{row.name}{row.plan_id === preview.recommended_plan_id ? ' · best fit for this scenario' : ''}</strong><span>{aed(row.annual_planning_total_fils)} illustrative year</span></div><div className="financial-bar" role="img" aria-label={`${row.name}: ${aed(row.member_premium_fils)} member-funded premium plus ${aed(row.illustrative_member_care_fils)} illustrative outpatient share`}><span className="premium-segment" style={{ width: `${100 * row.member_premium_fils / maximum}%` }}/><span className="care-segment" style={{ width: `${100 * row.illustrative_member_care_fils / maximum}%` }}/></div><p><span className="premium-key"/> Premium share {aed(row.member_premium_fils)} <span className="care-key"/> Illustrative care share {aed(row.illustrative_member_care_fils)} · Budget equivalent {aed(row.monthly_budget_equivalent_fils)}/month</p>{row.fit_status !== 'supported' && <small className="financial-gap"><CircleAlert size={14}/>{[...row.gaps, ...row.unknowns][0] || 'Coverage needs more review.'}</small>}{row.fit_status === 'supported' && !row.within_budget && <small className="financial-gap"><CircleAlert size={14}/>Premium share is {aed(row.budget_gap_fils)} above your annual budget.</small>}{row.plan_id === preview.recommended_plan_id && <button type="button" onClick={() => onChoose(row.plan_id)}>Review Easy Fill for this plan <ArrowRight size={16}/></button>}</div>)}</div>
      <details><summary>How these numbers were calculated</summary><ul>{preview.assumptions.map(item => <li key={item}>{item}</li>)}</ul></details>
    </div>}
    {!!saved.data?.items?.length && <p className="muted financial-saved">{saved.data.items.length} saved scenario{saved.data.items.length === 1 ? '' : 's'} for this quote. The latest choices are restored when you return.</p>}
  </section>;
}
