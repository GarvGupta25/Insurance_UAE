import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { ArrowRight, Building2, HeartPulse, ShieldCheck } from 'lucide-react';
import { PageShell, Section } from '../components';
import { api, aed } from '../../api';
import './PlansPage.css';

function coverageLabel(plan: any) {
  if (plan.maternity?.covered) return plan.maternity.waiting_period_months ? `Maternity after ${plan.maternity.waiting_period_months} months` : 'Maternity from day one';
  return 'General health cover';
}

export function PlansPage() {
  const { data: catalogue, error, isLoading } = useQuery({ queryKey: ['marketplace-plans'], queryFn: () => api('/api/public/marketplace-plans') });
  const plans = catalogue?.plans || [];
  return <PageShell>
    <Section id="plans-hero" tinted><div className="plans-hero scroll-reveal"><span className="plans-kicker"><ShieldCheck size={16}/> Fictional UAE marketplace</span><h1>Find the cover that fits your next step.</h1><p>Explore 50 fictional Helm schemes. Every card gives you the essentials; open it for the full benefit details.</p><div className="plans-hero-stats"><span><strong>10</strong> demo partners</span><span><strong>50</strong> schemes</span><span><strong>5</strong> cover styles</span></div></div></Section>
    <Section id="plans-catalogue">{isLoading && <p className="plans-loading">Loading schemes...</p>}{error && <p className="plans-error">Failed to load the scheme catalogue.</p>}{!isLoading && !error && <div className="scheme-grid" aria-label="Popular schemes">{plans.map((plan: any, index: number) => <Link to={`/plans/${plan.id}`} className="scheme-card scroll-reveal" key={plan.id}><div className="scheme-card__top"><span className={`scheme-network scheme-network--${plan.network}`}>{plan.network} network</span><span className="scheme-card__number">{String(index + 1).padStart(2, '0')}</span></div><div><p className="scheme-provider"><Building2 size={14}/>{plan.provider_name}</p><h2>{plan.name.replace(`${plan.provider_name} `, '')}</h2></div><div className="scheme-price"><strong>{aed(plan.annual_premium * 100)}</strong><span>per year</span></div><div className="scheme-highlights"><span><HeartPulse size={15}/>{coverageLabel(plan)}</span><span>{aed(plan.annual_limit * 100)} annual limit</span></div><div className="scheme-card__action">View full details <ArrowRight size={17}/></div></Link>)}</div>}</Section>
  </PageShell>;
}
