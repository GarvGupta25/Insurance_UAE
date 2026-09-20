import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Navigate } from 'react-router-dom';
import { api } from '../api';
import { ProviderApplications } from './ProviderApplications';
import { ProviderQuoteForm } from './ProviderQuoteForm';
import { ProviderPolicies } from './ProviderPolicies';
import { ProviderFinancialAccounts } from './ProviderFinancialAccounts';
import { ProviderFlagForm } from './ProviderFlagForm';

export function ProviderWorkspace() {
  const access = useQuery<{ role: 'member' | 'broker' | 'provider' }>({ queryKey: ['access'], queryFn: () => api('/api/me/access') });
  const [applicationId, setApplicationId] = useState(''); const [policyId, setPolicyId] = useState('');
  if (access.isLoading) return <div className="loading">Checking provider access…</div>;
  if (access.data?.role !== 'provider') return <Navigate to="/app" replace/>;
  return <div><div className="page-heading compact"><div><span className="eyebrow">PROVIDER WORKSPACE</span><h1>Applications and policies</h1><p>Only applications and records assigned to your provider organisation are available here.</p></div><span className="badge success">Tenant isolated</span></div><div className="provider-grid"><section className="surface"><span className="eyebrow">RECEIVED APPLICATIONS</span><h2>Awaiting quotation</h2><ProviderApplications selected={applicationId} onSelect={setApplicationId}/></section>{applicationId ? <ProviderQuoteForm applicationId={applicationId}/> : <div className="empty-state"><h3>Select an application</h3><p>Review its consented snapshot and prepare terms.</p></div>}<ProviderPolicies selectedPolicy={policyId} onSelectPolicy={setPolicyId}/><div><ProviderFinancialAccounts policyId={policyId}/><ProviderFlagForm policyId={policyId}/></div></div></div>;
}
