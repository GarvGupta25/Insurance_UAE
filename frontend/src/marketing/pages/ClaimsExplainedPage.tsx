import { PageShell, Section, SurfaceCard } from '../components';
import { FileText, ClipboardList, RefreshCcw, HandHeart } from 'lucide-react';
import './ClaimsExplainedPage.css';

export function ClaimsExplainedPage() {
  return (
    <PageShell>
      <Section id="claims-hero">
        <div className="claims-hero">
          <h1>Claims & Support</h1>
          <p>
            Understanding how insurance operations work before you need them. 
            Here is a plain-language guide to our four core servicing flows.
          </p>
        </div>
      </Section>

      <Section id="claims-operations" tinted>
        <div className="claims-grid">
          
          <SurfaceCard className="claims-card">
            <div className="claims-card-icon"><ClipboardList size={32} /></div>
            <h2>Pre-authorization</h2>
            <p>
              Before undergoing a scheduled or major medical procedure, your hospital submits a 
              request to the insurer. This is a <strong>forecast</strong> to confirm if the treatment 
              is medically necessary and covered under your policy limits. It acts as an approval in advance, 
              giving you peace of mind, but it does not deduct from your balance until the actual treatment occurs.
            </p>
          </SurfaceCard>

          <SurfaceCard className="claims-card">
            <div className="claims-card-icon"><FileText size={32} /></div>
            <h2>Filing a Claim</h2>
            <p>
              A claim is the official request submitted <strong>after</strong> treatment is received. If you 
              visit a hospital within your direct-billing network, the hospital files the claim directly 
              to the insurer. You simply pay your required co-pay or deductible at the reception desk, and 
              the insurer handles the rest behind the scenes.
            </p>
          </SurfaceCard>

          <SurfaceCard className="claims-card">
            <div className="claims-card-icon"><RefreshCcw size={32} /></div>
            <h2>Reimbursement</h2>
            <p>
              Reimbursement is a specific type of claim that happens when you visit a clinic outside 
              your direct-billing network. In this scenario, you pay the full hospital bill upfront. 
              You then submit the invoice and medical report through the app. The insurer processes the 
              documents and pays you back directly to your bank account, minus any deductibles.
            </p>
          </SurfaceCard>

          <SurfaceCard className="claims-card">
            <div className="claims-card-icon"><HandHeart size={32} /></div>
            <h2>Disputing a Denial (Appeal)</h2>
            <p>
              If a claim or pre-authorization is denied, you have the right to challenge the decision. 
              You can initiate an <strong>Appeal</strong> directly in the platform by submitting new medical 
              evidence or a justification letter from your doctor. A human reviewer will evaluate the new 
              evidence and make a final decision to either uphold or overturn the denial.
            </p>
          </SurfaceCard>

        </div>
      </Section>
    </PageShell>
  );
}
