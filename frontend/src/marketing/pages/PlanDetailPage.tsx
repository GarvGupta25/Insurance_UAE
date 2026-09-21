import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowRight, ArrowLeft, CheckCircle2 } from 'lucide-react';
import { PageShell, Section, SurfaceCard } from '../components';
import { api, aed } from '../../api';
import './PlanDetailPage.css';

function getPlanPersona(planId: string): string {
  switch (planId) {
    case 'plan_a':
      return "This essential package is often chosen by healthy individuals seeking basic regulatory compliance, or those managing a tight budget who don't anticipate frequent specialist visits.";
    case 'plan_b':
      return "A balanced choice often chosen by mid-career professionals who want access to a broader network of private hospitals and better coverage for occasional treatments.";
    case 'plan_c':
      return "Comprehensive protection often chosen by applicants planning a family within the year, managing an ongoing condition, or those who prefer unrestricted access to premium facilities.";
    default:
      return "A flexible option suited to UAE residents seeking reliable health cover.";
  }
}

export function PlanDetailPage() {
  const { planId } = useParams();
  
  const { data: catalogue, error, isLoading } = useQuery({
    queryKey: ['marketplace-plans'],
    queryFn: () => api('/api/public/marketplace-plans'),
  });

  const plan = catalogue?.plans?.find((p: any) => p.id === planId);

  if (isLoading) {
    return (
      <PageShell>
        <Section><p className="plan-detail-loading">Loading plan details...</p></Section>
      </PageShell>
    );
  }

  if (error || (!isLoading && !plan)) {
    return (
      <PageShell>
        <Section id="plan-not-found">
          <div className="plan-detail-error">
            <h1>Plan not found</h1>
            <p>We couldn't find the scheme you were looking for.</p>
            <Link to="/plans" className="m-button-secondary">
              <ArrowLeft size={18} /> View all plans
            </Link>
          </div>
        </Section>
      </PageShell>
    );
  }

  return (
    <PageShell>
      <Section id="plan-detail-hero" tinted>
        <div className="plan-detail-hero">
          <Link to="/plans" className="plan-detail-back">
            <ArrowLeft size={16} /> Back to popular schemes
          </Link>
          <h1>{plan.name}</h1>
          <p className="plan-detail-persona">{getPlanPersona(plan.id)}</p>
          <div className="plan-detail-premium">{aed(plan.annual_premium * 100)} <span>/ year</span></div>
          <Link to="/login" className="m-button-primary">
            Get my personal comparison <ArrowRight size={18} />
          </Link>
        </div>
      </Section>

      <Section id="plan-detail-terms">
        <div className="plan-terms-grid">
          <SurfaceCard className="plan-term-card">
            <h3>Network Tier</h3>
            <p className="plan-term-value">{plan.network.replace(/_/g, ' ')}</p>
            <p className="plan-term-explainer">Determines which clinics and hospitals you can visit without paying entirely out of pocket.</p>
          </SurfaceCard>
          
          <SurfaceCard className="plan-term-card">
            <h3>Annual Limit</h3>
            <p className="plan-term-value">{aed(plan.annual_limit * 100)}</p>
            <p className="plan-term-explainer">The maximum amount the insurer will pay for your treatment in a single policy year.</p>
          </SurfaceCard>
          
          <SurfaceCard className="plan-term-card">
            <h3>Deductible & Co-pay</h3>
            <p className="plan-term-value">{aed(plan.deductible * 100)} + {plan.outpatient_copay_pct}%</p>
            <p className="plan-term-explainer">You pay the deductible first, then the co-pay percentage for remaining costs on each visit.</p>
          </SurfaceCard>

          <SurfaceCard className="plan-term-card">
            <h3>Maternity Cover</h3>
            <div className="plan-term-value">
              {!plan.maternity.covered ? 'Not included' : plan.maternity.waiting_period_months > 0
                ? `Starts after ${plan.maternity.waiting_period_months} months`
                : 'Covered immediately'}
            </div>
            <p className="plan-term-explainer">The waiting period before you can claim for pregnancy and maternity-related care.</p>
          </SurfaceCard>

          <SurfaceCard className="plan-term-card">
            <h3>Pre-existing Conditions</h3>
            <div className="plan-term-value">
              {!plan.chronic_preexisting.covered ? 'Not included' : plan.chronic_preexisting.waiting_period_months > 0
                ? `Starts after ${plan.chronic_preexisting.waiting_period_months} months`
                : 'Covered immediately'}
            </div>
            <p className="plan-term-explainer">The waiting period before treatment for conditions you already had prior to joining is covered.</p>
          </SurfaceCard>

          <SurfaceCard className="plan-term-card">
            <h3>Dental & Optical</h3>
            <div className="plan-term-value flex-align">
              {plan.dental_optical !== 'none' ? <><CheckCircle2 size={18} className="icon-success" /> {plan.dental_optical}</> : 'Not included'}
            </div>
            <p className="plan-term-explainer">Coverage for routine dental checkups, procedures, and eye care.</p>
          </SurfaceCard>
        </div>
      </Section>
    </PageShell>
  );
}
