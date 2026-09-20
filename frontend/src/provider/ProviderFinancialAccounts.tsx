import { useQuery } from '@tanstack/react-query';
import { api, aed } from '../api';

export function ProviderFinancialAccounts({ policyId }: { policyId: string }) {
  const payments = useQuery<any[]>({ queryKey: ['provider-payments', policyId], queryFn: () => api(`/api/provider/policies/${policyId}/payments`), enabled: !!policyId });
  return <section className="surface"><span className="eyebrow">FINANCIAL ACCOUNT</span><h2>Payment ledger</h2>{!policyId ? <p>Select a policy to view its provider-scoped account.</p> : payments.isLoading ? <p>Loading payments…</p> : payments.error ? <p className="error">{payments.error.message}</p> : !payments.data?.length ? <p>No payment records have been posted.</p> : <div className="table-scroll"><table><thead><tr><th>Date</th><th>Status</th><th>Amount</th></tr></thead><tbody>{payments.data.map(payment => <tr key={payment.id}><td>{new Date(payment.paid_at).toLocaleDateString('en-AE')}</td><td>{payment.status}</td><td>{aed(payment.amount * 100)}</td></tr>)}</tbody></table></div>}</section>;
}
