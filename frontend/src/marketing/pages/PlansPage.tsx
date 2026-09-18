import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { PageShell, Section, SurfaceCard } from '../components';
import { api, aed } from '../../api';
import './PlansPage.css';

export function PlansPage() {
  const { data: catalogue, error, isLoading } = useQuery({
    queryKey: ['catalogue'],
    queryFn: () => api('/api/catalogue'),
  });

  const plans = catalogue?.items || [];

  return (
    <PageShell>
      <Section id="plans-hero">
        <div className="plans-hero">
          <h1>Best Schemes</h1>
          <p>
            Compare our available UAE health plans side by side. From essential 
            regulatory coverage to premium wide-network care.
          </p>
        </div>
      </Section>

      <Section id="plans-comparison" tinted>
        {isLoading && <p className="plans-loading">Loading schemes...</p>}
        {error && <p className="plans-error">Failed to load plan catalogue.</p>}

        {!isLoading && !error && plans.length > 0 && (
          <div className="plans-container">
            {/* Desktop Table View (>=1024px) */}
            <div className="plans-table-wrapper">
              <table className="plans-table">
                <thead>
                  <tr>
                    <th>Features</th>
                    {plans.map((plan: any) => (
                      <th key={plan.id}>
                        <h3>{plan.name}</h3>
                        <div className="plans-table-premium">{aed(plan.base_premium)} / year</div>
                        <Link to={`/plans/${plan.id}`} className="plans-details-link">View Details</Link>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Annual limit</td>
                    {plans.map((plan: any) => (
                      <td key={plan.id}>
                        {aed(plan.annual_limit)}
                        {plan.annual_limit === 150000 && (
                          <div className="plans-regulatory-callout">
                            * AED 150,000 matches the UAE's regulatory minimum annual benefit level
                          </div>
                        )}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td>Network tier</td>
                    {plans.map((plan: any) => (
                      <td key={plan.id}>{plan.network_tier.replace(/_/g, ' ')}</td>
                    ))}
                  </tr>
                  <tr>
                    <td>Deductible</td>
                    {plans.map((plan: any) => (
                      <td key={plan.id}>{aed(plan.deductible)}</td>
                    ))}
                  </tr>
                  <tr>
                    <td>Co-pay</td>
                    {plans.map((plan: any) => (
                      <td key={plan.id}>{plan.copay_percent}%</td>
                    ))}
                  </tr>
                  <tr>
                    <td>Maternity</td>
                    {plans.map((plan: any) => (
                      <td key={plan.id}>
                        {plan.maternity_waiting_months > 0
                          ? `Covered after ${plan.maternity_waiting_months} months`
                          : 'Covered immediately'}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td>Chronic / Pre-existing</td>
                    {plans.map((plan: any) => (
                      <td key={plan.id}>
                        {plan.chronic_waiting_months > 0
                          ? `Covered after ${plan.chronic_waiting_months} months`
                          : 'Covered immediately'}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td>Dental & Optical</td>
                    {plans.map((plan: any) => (
                      <td key={plan.id}>{plan.dental_optical ? 'Included' : 'Not included'}</td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Mobile Cards View (<1024px) */}
            <div className="plans-cards-wrapper">
              {plans.map((plan: any) => (
                <SurfaceCard key={plan.id} className="plan-mobile-card">
                  <div className="plan-mobile-header">
                    <h2>{plan.name}</h2>
                    <div className="plan-mobile-premium">{aed(plan.base_premium)} / year</div>
                  </div>
                  <dl className="plan-mobile-details">
                    <div className="plan-dl-row">
                      <dt>Annual limit</dt>
                      <dd>
                        {aed(plan.annual_limit)}
                        {plan.annual_limit === 150000 && (
                          <div className="plans-regulatory-callout">
                            * AED 150,000 matches the UAE's regulatory minimum annual benefit level
                          </div>
                        )}
                      </dd>
                    </div>
                    <div className="plan-dl-row">
                      <dt>Network tier</dt>
                      <dd>{plan.network_tier.replace(/_/g, ' ')}</dd>
                    </div>
                    <div className="plan-dl-row">
                      <dt>Deductible</dt>
                      <dd>{aed(plan.deductible)}</dd>
                    </div>
                    <div className="plan-dl-row">
                      <dt>Co-pay</dt>
                      <dd>{plan.copay_percent}%</dd>
                    </div>
                    <div className="plan-dl-row">
                      <dt>Maternity</dt>
                      <dd>
                        {plan.maternity_waiting_months > 0
                          ? `Covered after ${plan.maternity_waiting_months} months`
                          : 'Covered immediately'}
                      </dd>
                    </div>
                    <div className="plan-dl-row">
                      <dt>Chronic</dt>
                      <dd>
                        {plan.chronic_waiting_months > 0
                          ? `Covered after ${plan.chronic_waiting_months} months`
                          : 'Covered immediately'}
                      </dd>
                    </div>
                    <div className="plan-dl-row">
                      <dt>Dental / Optical</dt>
                      <dd>{plan.dental_optical ? 'Included' : 'Not included'}</dd>
                    </div>
                  </dl>
                  <Link to={`/plans/${plan.id}`} className="m-button-primary plan-mobile-cta">
                    View Details
                  </Link>
                </SurfaceCard>
              ))}
            </div>
          </div>
        )}
      </Section>
    </PageShell>
  );
}
