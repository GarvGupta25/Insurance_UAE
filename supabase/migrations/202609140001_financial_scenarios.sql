CREATE TABLE public.financial_scenarios (
    id VARCHAR(36) PRIMARY KEY,
    owner_id VARCHAR(36) NOT NULL,
    quote_id VARCHAR(36) NOT NULL REFERENCES public.quotes(id),
    inputs JSONB NOT NULL,
    result JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);
CREATE INDEX ix_financial_scenarios_owner_id ON public.financial_scenarios(owner_id);
CREATE INDEX ix_financial_scenarios_quote_id ON public.financial_scenarios(quote_id);
ALTER TABLE public.financial_scenarios ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.financial_scenarios FROM anon, authenticated;
