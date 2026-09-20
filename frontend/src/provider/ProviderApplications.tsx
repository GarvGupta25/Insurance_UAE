import { useQuery } from '@tanstack/react-query';
import { api } from '../api';
import type { ProviderApplication } from './types';

export function ProviderApplications({ selected, onSelect }: { selected: string; onSelect: (id: string) => void }) {
  const applications = useQuery<ProviderApplication[]>({ queryKey: ['provider-applications'], queryFn: () => api('/api/provider/applications'), refetchInterval: 5000 });
  if (applications.isLoading) return <p>Loading received applications…</p>;
  if (applications.error) return <p className="error">{applications.error.message}</p>;
  if (!applications.data?.length) return <div className="empty-state"><h3>No applications awaiting a quote</h3><p>Broker-approved, consented applications assigned to your organisation will appear here.</p></div>;
  const selectedApplication = applications.data.find(application => application.id === selected);
  return <><div className="provider-list">{applications.data.map(application => <button type="button" className={`provider-row ${selected === application.id ? 'selected' : ''}`} key={application.id} onClick={() => onSelect(application.id)}><span><strong>Application {application.id.slice(0, 8)}</strong><small>Received {new Date(application.created_at).toLocaleDateString('en-AE')}</small></span><span className="badge">Quote</span></button>)}</div>{selectedApplication && <dl className="application-fields provider-snapshot">{Object.entries(selectedApplication.consent_snapshot).map(([key, value]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{typeof value === 'object' ? JSON.stringify(value) : String(value || 'Not provided')}</dd></div>)}</dl>}</>;
}
