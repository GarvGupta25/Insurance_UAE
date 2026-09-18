import { useQuery } from '@tanstack/react-query';
import { PageShell, Section, SurfaceCard } from '../components';
import { api } from '../../api';
import './PartnersPage.css';

interface Provider {
  id: string;
  name: string;
  tier: string;
  emirate: string;
}

const TIER_LABELS: Record<string, string> = {
  in_network_clinic: 'Community / Restricted',
  private_hospital: 'Standard',
  premium_private_hospital: 'Premium / Wide',
};

export function PartnersPage() {
  const { data: providersData, error } = useQuery({
    queryKey: ['public-providers'],
    queryFn: () => api('/api/public/providers'),
  });

  // Group providers by tier
  const providersByTier = (providersData?.items || []).reduce((acc: Record<string, Provider[]>, provider: Provider) => {
    const label = TIER_LABELS[provider.tier] || provider.tier;
    if (!acc[label]) acc[label] = [];
    acc[label].push(provider);
    return acc;
  }, {});

  return (
    <PageShell>
      {/* 1. Impossible to miss demo label */}
      <div className="partners-demo-alert" role="alert">
        <strong>Sample partner network — for demonstration purposes.</strong> 
        {' '}These are illustrative provider names, not real insurer or hospital partnerships.
      </div>

      <Section id="partners-hero">
        <div className="partners-hero">
          <h1>Our Partners</h1>
          <p>
            Helm AI is designed to integrate seamlessly with top-tier providers across the UAE.
            Explore our fictional network tiers below.
          </p>
        </div>
      </Section>

      <Section id="partners-list" tinted>
        {error ? (
          <div className="partners-error">
            <p>Provider directory temporarily unavailable.</p>
          </div>
        ) : (
          <div className="partners-tiers-container">
            {Object.keys(TIER_LABELS).map((tierKey) => {
              const label = TIER_LABELS[tierKey];
              const tierProviders = providersByTier[label];
              
              if (!tierProviders || tierProviders.length === 0) return null;

              return (
                <div key={label} className="partners-tier-group">
                  <h2 className="partners-tier-heading">{label}</h2>
                  <div className="partners-grid">
                    {tierProviders.map((provider: Provider) => (
                      <SurfaceCard key={provider.id} className="partners-card">
                        <h3>{provider.name}</h3>
                        <p>{provider.emirate}</p>
                      </SurfaceCard>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Section>
    </PageShell>
  );
}
