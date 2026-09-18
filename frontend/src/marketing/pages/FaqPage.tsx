import { PageShell, Section } from '../components';
import './FaqPage.css';

export function FaqPage() {
  return (
    <PageShell>
      <Section id="faq-hero">
        <div className="faq-hero">
          <h1>Frequently Asked Questions</h1>
          <p>Clear, direct answers about health insurance and using Helm AI.</p>
        </div>
      </Section>

      <Section id="faq-content">
        <div className="faq-container">
          
          <div className="faq-group">
            <h2>About Cover</h2>
            <div className="faq-accordion">
              <details className="faq-details">
                <summary>What is a deductible?</summary>
                <div className="faq-answer">
                  A deductible (or excess) is the fixed out-of-pocket amount you must pay on each visit or claim before your insurance coverage kicks in.
                </div>
              </details>
              
              <details className="faq-details">
                <summary>What is the difference between direct billing and reimbursement?</summary>
                <div className="faq-answer">
                  Direct billing means the hospital charges the insurer directly using your Emirates ID or insurance card. Reimbursement means you pay the hospital upfront and submit the invoice to the insurer to be paid back later.
                </div>
              </details>
              
              <details className="faq-details">
                <summary>How are pre-existing conditions handled?</summary>
                <div className="faq-answer">
                  A pre-existing condition is a medical issue you were diagnosed with before buying the policy. Depending on the plan, coverage for these conditions may begin immediately, or there may be a waiting period (e.g., 6 months) before treatments for that specific condition are covered.
                </div>
              </details>
            </div>
          </div>

          <div className="faq-group">
            <h2>Using Helm AI</h2>
            <div className="faq-accordion">
              <details className="faq-details">
                <summary>Does the AI automatically issue my policy?</summary>
                <div className="faq-answer">
                  No. Helm AI generates a recommendation based on strict deterministic rules, but an expert human broker must review and sign off on that recommendation before any actual policy can be issued.
                </div>
              </details>
              
              <details className="faq-details">
                <summary>Do I have to enter my medical history to get a quote?</summary>
                <div className="faq-answer">
                  Our initial intake only asks for high-level facts (age, visa status, dependents) to recommend a tier. Detailed medical history is generally only collected when proceeding to formal application and underwriting.
                </div>
              </details>
              
              <details className="faq-details">
                <summary>Why do you only show three plans?</summary>
                <div className="faq-answer">
                  Instead of overwhelming you with dozens of slightly altered policies, our engine categorizes the UAE market into three clear tiers (Essential, Standard, Comprehensive). We recommend the structure that best fits your regulatory needs and budget.
                </div>
              </details>
            </div>
          </div>

          <div className="faq-group">
            <h2>Claims & Appeals</h2>
            <div className="faq-accordion">
              <details className="faq-details">
                <summary>How does pre-authorization work?</summary>
                <div className="faq-answer">
                  Pre-authorization is a forecast before treatment. Your hospital submits a request for a planned procedure, and the insurer confirms whether it's covered. It doesn't affect your balance until the actual claim is filed.
                </div>
              </details>
              
              <details className="faq-details">
                <summary>How do I submit a reimbursement claim?</summary>
                <div className="faq-answer">
                  If you visited a clinic outside your direct-billing network, you pay upfront and submit a claim through the app with a copy of your invoice and medical report. Once processed, the funds are reimbursed to your account.
                </div>
              </details>
              
              <details className="faq-details">
                <summary>Can I dispute a denied claim?</summary>
                <div className="faq-answer">
                  Yes. If a claim is denied, you can file an appeal directly in the platform by submitting new medical evidence or a doctor's justification. A reviewer will evaluate the new evidence and either uphold or overturn the denial.
                </div>
              </details>
            </div>
          </div>

        </div>
      </Section>
    </PageShell>
  );
}
