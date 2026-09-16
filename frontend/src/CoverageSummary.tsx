import { aed } from './api';
import { ReadAloud } from './Voice';

type Plan = {
  name: string;
  annual_limit: number;
  deductible: number;
  outpatient_copay_pct: number;
  network_note?: string;
  maternity: { covered: boolean; waiting_period_months?: number; limit?: number };
  chronic_preexisting: { covered: boolean; waiting_period_months?: number };
  dental_optical?: string;
};

export function coverageSummaryText(plan: Plan) {
  const maternity = plan.maternity.covered
    ? `Maternity is available after ${plan.maternity.waiting_period_months} months, with plan payments up to ${aed((plan.maternity.limit || 0) * 100)}.`
    : 'Maternity is not included in this plan.';
  const existingConditions = plan.chronic_preexisting.covered
    ? `Declared existing conditions are covered after ${plan.chronic_preexisting.waiting_period_months} months.`
    : 'Declared existing conditions are not included in this plan.';
  const deductible = plan.deductible === 0 ? 'There is no deductible.' : `You pay the first ${aed(plan.deductible * 100)} before the outpatient copay applies.`;
  return `${plan.name} provides up to ${aed(plan.annual_limit * 100)} of plan payments in each policy year. ${deductible} Your outpatient copay is ${plan.outpatient_copay_pct}%. ${maternity} ${existingConditions} Dental and optical cover is ${plan.dental_optical || 'not stated'}.`;
}

export function CoverageSummary({ plan }: { plan: Plan }) {
  const summary = coverageSummaryText(plan);
  return <section className="surface coverage-summary" aria-labelledby="coverage-summary-heading">
    <div className="section-heading">
      <div>
        <span className="eyebrow">PLAIN-LANGUAGE SUMMARY</span>
        <h2 id="coverage-summary-heading">What your cover means day to day</h2>
      </div>
      <ReadAloud text={summary}/>
    </div>
    <p>{summary}</p>
    {plan.network_note && <p className="muted"><strong>Network:</strong> {plan.network_note}</p>}
    <small className="source-label">This summary is assembled from your frozen fictional plan terms. It does not change or interpret policy terms.</small>
  </section>;
}
