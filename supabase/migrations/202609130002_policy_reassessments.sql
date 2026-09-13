CREATE TABLE public.policy_reassessments (
    id VARCHAR(36) PRIMARY KEY,
    owner_id VARCHAR(36) NOT NULL,
    policy_id VARCHAR(36) NOT NULL REFERENCES public.policies(id),
    profile_version INTEGER NOT NULL,
    report JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL
);
CREATE INDEX ix_policy_reassessments_policy_created ON public.policy_reassessments(policy_id, created_at DESC);
ALTER TABLE public.policy_reassessments ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.policy_reassessments FROM anon, authenticated;
