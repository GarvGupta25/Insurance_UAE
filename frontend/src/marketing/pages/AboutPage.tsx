import { PageShell, Section, SurfaceCard } from '../components';
import './AboutPage.css';

export function AboutPage() {
  return (
    <PageShell>
      {/* 1. Hero */}
      <Section id="about-hero">
        <div className="about-hero">
          <h1>About Helm AI</h1>
          <p>
            Helm AI compares individual UAE health plans, recommends one with a clear
            reasoning trace, and always requires a human reviewer to confirm the 
            recommendation before a policy is created. 
          </p>
        </div>
      </Section>

      {/* 2. How a recommendation actually happens */}
      <Section id="about-process" tinted>
        <div className="about-section-header">
          <h2>How a recommendation actually happens</h2>
          <p>We believe in transparent tradeoffs and accountable advice.</p>
        </div>
        
        <div className="about-process-grid">
          <SurfaceCard className="about-step-card">
            <span className="about-step-number">1. Intake</span>
            <p>You answer simple questions about your health, visa type, and priorities through our chat or forms.</p>
          </SurfaceCard>
          
          <SurfaceCard className="about-step-card">
            <span className="about-step-number">2. Deterministic Comparison</span>
            <p>Our engine maps your needs directly against strict plan rules (networks, waiting periods, deductibles).</p>
          </SurfaceCard>
          
          <SurfaceCard className="about-step-card">
            <span className="about-step-number">3. Human Reviewer</span>
            <p>An expert broker reviews the AI’s recommendation. They can approve it, or edit it if the context requires a different approach.</p>
          </SurfaceCard>
          
          <SurfaceCard className="about-step-card">
            <span className="about-step-number">4. Policy Creation</span>
            <p>Only after the human reviewer signs off can a policy be generated and issued to you.</p>
          </SurfaceCard>
        </div>
      </Section>

      {/* 3. Demonstration disclaimer */}
      <Section id="about-demo">
        <SurfaceCard className="about-demo-card">
          <h2>This is a demonstration product</h2>
          <p>
            The plans, premiums, and partner names shown on this website are 
            entirely fictional and synthetic. Helm AI is built exclusively for 
            demonstrating an insurance brokerage workflow and architecture.
          </p>
          <p>
            Using this platform does not create any real policy, payment obligation, 
            or relationship with a licensed insurer.
          </p>
        </SurfaceCard>
      </Section>

      {/* 
        TODO: Add real leadership headshots, media logos, and founding details here 
        once genuine content exists outside this repository. Do not invent facts.
      */}
    </PageShell>
  );
}
