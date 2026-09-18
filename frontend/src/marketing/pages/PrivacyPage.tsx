import { PageShell, Section, SurfaceCard } from '../components';
import './LegalPages.css';

export function PrivacyPage() {
  return (
    <PageShell>
      <Section id="privacy-hero">
        <div className="legal-hero">
          <h1>Privacy Policy</h1>
          <p>Last updated: September 2026</p>
        </div>
      </Section>

      <Section id="privacy-content">
        <SurfaceCard className="legal-card">
          <h2>1. Data Collection in a Demo Environment</h2>
          <p>
            Helm AI is a demonstration application. Any information you input during the intake, 
            shopping, or servicing flows is treated as synthetic data used strictly for showcasing 
            the platform's capabilities. Do not submit genuine sensitive health or financial information.
          </p>

          <h2>2. How Information is Used</h2>
          <p>
            Data provided is used momentarily to simulate a deterministic comparison engine and to 
            generate a fictional policy recommendation. We do not sell, rent, or share this data 
            with real-world insurance providers, as no real insurance relationships exist.
          </p>

          <h2>3. Cookies and Analytics</h2>
          <p>
            This site uses strictly necessary session cookies to maintain your login state during 
            the demonstration. We do not use third-party tracking or advertising cookies.
          </p>

          <h2>4. Data Retention</h2>
          <p>
            Because this is a demonstration environment, accounts and associated synthetic data may 
            be periodically wiped without notice to maintain system performance.
          </p>
        </SurfaceCard>
      </Section>
    </PageShell>
  );
}
