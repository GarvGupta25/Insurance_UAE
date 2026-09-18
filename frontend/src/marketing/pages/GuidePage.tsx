import { Link } from 'react-router-dom';
import { ArrowRight, Info, ShieldAlert } from 'lucide-react';
import { PageShell, Section, SurfaceCard } from '../components';
import './GuidePage.css';

export function GuidePage() {
  return (
    <PageShell>
      <Section id="guide-hero">
        <div className="guide-hero">
          <h1>New to the UAE?</h1>
          <p>
            Understanding health insurance here doesn’t have to be complicated. 
            Here is everything you need to know about regulatory requirements, market costs, 
            and essential terminology.
          </p>
        </div>
      </Section>

      <Section id="guide-why">
        <div className="guide-content">
          <h2>Why you need individual cover</h2>
          <p>
            Health insurance is a strict legal condition of UAE residency. Your residency visa 
            cannot be issued or renewed without proof of active cover, and failure to maintain it 
            results in monthly fines.
          </p>
          <p>
            While many companies provide group cover for their employees, you <strong>must arrange your own individual policy</strong> if you are:
          </p>
          <ul className="guide-list">
            <li>A self-sponsored resident or freelancer</li>
            <li>An investor or Golden Visa holder</li>
            <li>Someone whose employer-sponsored cover has just ended</li>
          </ul>
        </div>
      </Section>

      <Section id="guide-regulators" tinted>
        <div className="guide-content">
          <h2>Who regulates what?</h2>
          <p>The UAE's healthcare regulation is split by emirate:</p>
          <div className="guide-table-wrapper">
            <table className="guide-table">
              <thead>
                <tr>
                  <th>Emirate</th>
                  <th>Regulator & Scheme</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Dubai</td>
                  <td>Dubai Health Authority (DHA)</td>
                </tr>
                <tr>
                  <td>Abu Dhabi</td>
                  <td>Department of Health (DoH)</td>
                </tr>
                <tr>
                  <td>Sharjah & Northern Emirates</td>
                  <td>Ministry of Health and Prevention (MOHAP) — Basic Health Insurance Scheme</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </Section>

      <Section id="guide-portability">
        <div className="guide-content">
          <h2>Employer vs. Individual Cover</h2>
          <p>
            Employer-sponsored group cover is convenient, but it typically ends within ~30 days of 
            your visa cancellation if you leave your job. An <strong>individual policy</strong>, on the other hand, 
            is fully portable because it isn’t tied to any employer.
          </p>
        </div>
      </Section>

      <Section id="guide-glossary" tinted>
        <div className="guide-content">
          <h2>Essential Glossary</h2>
          <dl className="guide-glossary">
            <div className="glossary-item">
              <dt>Deductible (or Excess)</dt>
              <dd>The fixed out-of-pocket amount you must pay on each visit or claim before your insurance kicks in.</dd>
            </div>
            <div className="glossary-item">
              <dt>Co-payment vs. Co-insurance</dt>
              <dd>A co-payment is a flat fee per visit, while co-insurance is a percentage of the total bill you share with the insurer.</dd>
            </div>
            <div className="glossary-item">
              <dt>Network Tier</dt>
              <dd>The specific list of hospitals and clinics where you can use your insurance card without paying the full bill upfront.</dd>
            </div>
            <div className="glossary-item">
              <dt>Direct Billing vs. Reimbursement</dt>
              <dd>Direct billing means the hospital charges the insurer directly; reimbursement means you pay upfront and claim it back later.</dd>
            </div>
            <div className="glossary-item">
              <dt>Annual Limit</dt>
              <dd>The absolute maximum financial ceiling the insurer will pay for your healthcare in a given policy year.</dd>
            </div>
            <div className="glossary-item">
              <dt>Sub-limit</dt>
              <dd>A smaller, specific limit within your annual limit applied to certain treatments (like maternity or dental).</dd>
            </div>
            <div className="glossary-item">
              <dt>Waiting Period</dt>
              <dd>The time you must hold the policy before coverage for specific conditions (like maternity) begins.</dd>
            </div>
            <div className="glossary-item">
              <dt>Pre-existing Condition</dt>
              <dd>A medical condition you were diagnosed with, or showed symptoms of, before buying the policy.</dd>
            </div>
            <div className="glossary-item">
              <dt>Geographic Scope</dt>
              <dd>Where in the world your policy covers you (e.g., UAE only, GCC, Worldwide excluding USA/Canada).</dd>
            </div>
          </dl>
        </div>
      </Section>

      <Section id="guide-costs">
        <div className="guide-content">
          <h2>What a policy actually costs</h2>
          <p>
            Health insurance costs sit on a wide spectrum depending on age, network, and pre-existing conditions.
          </p>
          <div className="guide-cost-chart">
            <SurfaceCard className="cost-tier">
              <div className="cost-tier-header">Basic Mandatory Cover</div>
              <div className="cost-tier-range">A few hundred AED / year</div>
              <div className="cost-tier-desc">Restricted networks, basic benefits.</div>
            </SurfaceCard>
            <SurfaceCard className="cost-tier">
              <div className="cost-tier-header">Comprehensive Individual Cover</div>
              <div className="cost-tier-range">Tens of thousands of AED / year</div>
              <div className="cost-tier-desc">Wide networks, high limits, global coverage.</div>
            </SurfaceCard>
          </div>
          <small className="guide-caption">* Illustrative ranges indicating general 2026 UAE market context. Not a Helm AI quote.</small>
        </div>
      </Section>

      <Section id="guide-good-to-know" tinted>
        <div className="guide-content">
          <h2>Good to know</h2>
          <div className="guide-callouts-grid">
            <SurfaceCard className="guide-callout-card">
              <div className="guide-callout-icon"><Info size={24} /></div>
              <h3>30-Day Cooling-Off Period</h3>
              <p>Under UAE Central Bank regulations, you are entitled to a full premium refund if you cancel a new individual policy within 30 days of purchase, provided no claims have been made.</p>
            </SurfaceCard>
            <SurfaceCard className="guide-callout-card">
              <div className="guide-callout-icon"><ShieldAlert size={24} /></div>
              <h3>Emirates ID Linkage</h3>
              <p>Your Emirates ID number is the exact identifier the insurer submits to the government (DHA/DoH). Any mismatch between your application and your EID will result in visa-processing failures.</p>
            </SurfaceCard>
          </div>
        </div>
      </Section>

      <Section id="guide-cta">
        <div className="guide-cta">
          <h2>Ready to find your cover?</h2>
          <p>See exactly how Helm AI can match you with the right scheme.</p>
          <Link to="/login" className="m-button-primary">
            Get started <ArrowRight size={18} />
          </Link>
        </div>
      </Section>
    </PageShell>
  );
}
