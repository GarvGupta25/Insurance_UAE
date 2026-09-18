import { PageShell, Section, SurfaceCard } from '../components';
import { AlertTriangle } from 'lucide-react';
import './LegalPages.css';

export function DisclaimerPage() {
  return (
    <PageShell>
      <Section id="disclaimer-hero">
        <div className="legal-hero">
          <h1>Demonstration Disclaimer</h1>
          <p>Please read this notice carefully before interacting with the platform.</p>
        </div>
      </Section>

      <Section id="disclaimer-content">
        <SurfaceCard className="legal-card disclaimer-card">
          <div className="disclaimer-icon-wrapper">
            <AlertTriangle size={48} className="disclaimer-icon" />
          </div>
          
          <h2>This is a Demonstration Product</h2>
          
          <p>
            <strong>Helm AI is a software prototype and simulator.</strong> It is not a licensed 
            insurance broker, underwriter, or healthcare provider.
          </p>

          <p>
            <strong>Fictional Entities:</strong> All plan names (e.g., Harbour Basic, Crescent Choice), 
            network tiers, and partner hospital names displayed on this website are entirely fictional 
            and illustrative.
          </p>

          <p>
            <strong>Synthetic Financials:</strong> The premiums, deductibles, and claim payouts 
            shown are synthetic data. <strong>No real insurance policy is ever issued</strong> through 
            this platform.
          </p>

          <p>
            <strong>Simulated Payments:</strong> Even where a payment flow or checkout screen is 
            presented within the application, it operates strictly in a sandbox/simulator mode. 
            <strong>No real payment is processed, and no real funds are transferred.</strong>
          </p>

          <p>
            By proceeding to sign up or use the application, you acknowledge that all data, limits, 
            and interactions are simulated for the purpose of evaluating the software architecture.
          </p>
        </SurfaceCard>
      </Section>
    </PageShell>
  );
}
