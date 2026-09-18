import { PageShell, Section, SurfaceCard } from '../components';
import { ArrowRight, FileText, Activity, ShieldCheck, UserCheck } from 'lucide-react';
import { Link } from 'react-router-dom';
import './HowItWorksPage.css';

export function HowItWorksPage() {
  return (
    <PageShell>
      <Section id="hiw-hero">
        <div className="hiw-hero">
          <h1>How It Works</h1>
          <p>
            A transparent look at exactly how Helm AI generates recommendations, 
            and why a human reviewer always has the final say.
          </p>
        </div>
      </Section>

      <Section id="hiw-steps">
        <div className="hiw-steps-container">
          
          <SurfaceCard className="hiw-step-card">
            <div className="hiw-step-header">
              <div className="hiw-icon"><UserCheck size={28} /></div>
              <h2>1. Tell us about you</h2>
            </div>
            <p>
              The journey starts with a simple intake form or chat session. We collect only the 
              necessary baseline facts: your age, visa status, dependents, and any high-level 
              healthcare priorities. We do not ask for detailed medical history upfront unless 
              relevant to selecting the right coverage tier.
            </p>
          </SurfaceCard>

          <SurfaceCard className="hiw-step-card">
            <div className="hiw-step-header">
              <div className="hiw-icon"><Activity size={28} /></div>
              <h2>2. We compare 3 plan structures</h2>
            </div>
            <p>
              Our deterministic comparison engine takes your profile and evaluates it against our 
              three standardized plan catalogs. Instead of confusing you with dozens of slightly 
              different policies, the engine strictly maps your needs to the best fit among our 
              Essential, Standard, or Comprehensive tiers.
            </p>
          </SurfaceCard>

          <SurfaceCard className="hiw-step-card">
            <div className="hiw-step-header">
              <div className="hiw-icon"><FileText size={28} /></div>
              <h2>3. Get a clear recommendation</h2>
            </div>
            <p>
              The system generates a specific plan recommendation accompanied by a transparent reasoning 
              trace. You will see exactly why a particular network tier or annual limit was selected 
              for you, rather than just being shown a price.
            </p>
          </SurfaceCard>

          <SurfaceCard className="hiw-step-card">
            <div className="hiw-step-header">
              <div className="hiw-icon"><ShieldCheck size={28} /></div>
              <h2>4. A reviewer signs off</h2>
            </div>
            <p>
              Crucially, AI never issues a policy autonomously. An expert human broker reviews the 
              recommendation and your profile. They can either approve the AI's suggestion or edit it 
              if human context dictates a better approach. Only after this sign-off can your policy be generated.
            </p>
          </SurfaceCard>

        </div>
      </Section>

      <Section id="hiw-cta" tinted>
        <div className="hiw-cta-container">
          <h2>Ready to get started?</h2>
          <Link to="/login" className="m-button-primary">
            Start your intake <ArrowRight size={18} />
          </Link>
        </div>
      </Section>
    </PageShell>
  );
}
