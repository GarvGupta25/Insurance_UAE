import { Bell, CheckCircle2, Wallet } from 'lucide-react';
import { aed } from './api';

type Installment = { id: string; position: number; amount: number; due_date: string; status: string };
type ServicingEvent = { id: string; record_type: string; event_id: string; reviewer_action?: string | null; recorded_at: string };

export function PolicyNotifications({ instalments, servicing }: { instalments: Installment[]; servicing: ServicingEvent[] }) {
  const due = instalments.find(item => item.status !== 'paid');
  const appealReview = [...servicing].reverse().find(item => item.record_type === 'appeal_review');
  if (!due && !appealReview) return null;

  return <section className="surface simulated-notifications" aria-labelledby="simulated-notifications-heading" aria-live="polite">
    <div className="section-heading">
      <div>
        <span className="eyebrow">SIMULATED IN-APP NOTIFICATIONS</span>
        <h2 id="simulated-notifications-heading">Updates for this demo policy</h2>
      </div>
      <Bell aria-hidden="true" size={21}/>
    </div>
    {due && <div className="notification-stub">
      <Wallet aria-hidden="true" size={19}/>
      <div><strong>Test payment due · instalment {due.position}</strong><p>{aed(due.amount)} is scheduled for {due.due_date}. Open Payments to use the sandbox payment flow.</p></div>
      <span className="badge neutral">Simulated</span>
    </div>}
    {appealReview && <div className="notification-stub">
      <CheckCircle2 aria-hidden="true" size={19}/>
      <div><strong>Appeal decision recorded · {appealReview.event_id}</strong><p>Your broker marked this appeal as {appealReview.reviewer_action || 'reviewed'}. Open Servicing to view the preserved decision history.</p></div>
      <span className="badge neutral">Simulated</span>
    </div>}
    <small className="source-label">These are in-app demonstration notices only. Helm does not send email, SMS, or push messages.</small>
  </section>;
}
