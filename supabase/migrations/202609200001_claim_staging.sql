-- Claim Management / Phase 1: pre-adjudication staging only.
-- Existing policy IDs are VARCHAR(36), so staging IDs follow the same compatible project convention.
CREATE TABLE public.claim_intakes (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    policy_id VARCHAR(36) NOT NULL REFERENCES public.policies(id),
    kind TEXT NOT NULL CHECK (kind IN ('pre_auth', 'claim', 'reimbursement', 'appeal', 'emergency')),
    raw_message TEXT,
    structured_fields JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_emergency BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

CREATE TABLE public.claim_documents (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    claim_intake_id VARCHAR(36) NOT NULL REFERENCES public.claim_intakes(id) ON DELETE CASCADE,
    doc_type TEXT NOT NULL,
    extracted_fields JSONB DEFAULT '{}'::jsonb,
    completeness_ok BOOLEAN,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

CREATE TABLE public.claim_flags (
    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    claim_intake_id VARCHAR(36) NOT NULL REFERENCES public.claim_intakes(id) ON DELETE CASCADE,
    flag_type TEXT NOT NULL CHECK (
        flag_type IN ('emergency', 'missing_docs', 'exclusion_risk', 'anomaly', 'high_value')
    ),
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'reviewed', 'closed')),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

ALTER TABLE public.claim_intakes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.claim_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.claim_flags ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.claim_intakes, public.claim_documents, public.claim_flags
    FROM anon, authenticated;
GRANT SELECT ON public.claim_intakes, public.claim_documents, public.claim_flags
    TO authenticated;

CREATE POLICY claim_intakes_scoped_read ON public.claim_intakes
    FOR SELECT TO authenticated
    USING (
        public.marketplace_is_broker_or_support()
        OR EXISTS (
            SELECT 1 FROM public.policies policy
            WHERE policy.id = claim_intakes.policy_id
              AND policy.owner_id = auth.uid()::text
        )
    );

CREATE POLICY claim_documents_scoped_read ON public.claim_documents
    FOR SELECT TO authenticated
    USING (
        public.marketplace_is_broker_or_support()
        OR EXISTS (
            SELECT 1
            FROM public.claim_intakes intake
            JOIN public.policies policy ON policy.id = intake.policy_id
            WHERE intake.id = claim_documents.claim_intake_id
              AND policy.owner_id = auth.uid()::text
        )
    );

CREATE POLICY claim_flags_scoped_read ON public.claim_flags
    FOR SELECT TO authenticated
    USING (
        public.marketplace_is_broker_or_support()
        OR EXISTS (
            SELECT 1
            FROM public.claim_intakes intake
            JOIN public.policies policy ON policy.id = intake.policy_id
            WHERE intake.id = claim_flags.claim_intake_id
              AND policy.owner_id = auth.uid()::text
        )
    );

-- Mutations remain backend-owned; no direct browser write grants are created.
