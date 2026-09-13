ALTER TABLE public.policies ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;

CREATE TABLE public.servicing_events (
    id VARCHAR(36) PRIMARY KEY,
    owner_id VARCHAR(36) NOT NULL,
    policy_id VARCHAR(36) NOT NULL REFERENCES public.policies(id),
    root_id VARCHAR(80) NOT NULL,
    record_type VARCHAR(24) NOT NULL,
    kind VARCHAR(24) NOT NULL,
    effective_month INTEGER,
    sequence INTEGER NOT NULL,
    payload JSONB NOT NULL,
    outcome VARCHAR(32),
    reason_code VARCHAR(40),
    plan_pays_fils INTEGER,
    member_pays_fils INTEGER,
    calculation JSONB NOT NULL DEFAULT '[]'::jsonb,
    ledger_before JSONB,
    ledger_after JSONB,
    supersedes_id VARCHAR(36) REFERENCES public.servicing_events(id),
    reviewer_action VARCHAR(32),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL
);
CREATE INDEX ix_servicing_events_policy_sequence ON public.servicing_events(policy_id, sequence);
CREATE UNIQUE INDEX uq_servicing_decision_root ON public.servicing_events(policy_id, root_id) WHERE record_type = 'decision';
ALTER TABLE public.servicing_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.servicing_events FROM anon, authenticated;

CREATE TABLE public.benefit_ledger_projections (
    id VARCHAR(36) PRIMARY KEY,
    owner_id VARCHAR(36) NOT NULL,
    policy_id VARCHAR(36) NOT NULL UNIQUE REFERENCES public.policies(id),
    through_sequence INTEGER NOT NULL DEFAULT 0,
    ledger JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL
);
ALTER TABLE public.benefit_ledger_projections ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.benefit_ledger_projections FROM anon, authenticated;

CREATE FUNCTION public.reject_servicing_history_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Servicing history is append-only'; END;
$$;
CREATE TRIGGER immutable_servicing_history BEFORE UPDATE OR DELETE ON public.servicing_events
FOR EACH ROW EXECUTE FUNCTION public.reject_servicing_history_mutation();
