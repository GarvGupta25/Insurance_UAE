export type ProviderApplication = {
  id: string;
  status: string;
  created_at: string;
  consent_snapshot: Record<string, unknown>;
};

export type ProviderQuotation = {
  id: string;
  application_id: string;
  plan_terms: Record<string, unknown>;
  premium: number;
  status: string;
  submitted_at: string;
};

export type ProviderPolicy = {
  id: string;
  application_id: string;
  quotation_id: string;
  status: string;
  started_at: string;
  discontinued_reason?: string | null;
};
