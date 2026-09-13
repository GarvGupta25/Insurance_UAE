ALTER TABLE public.policy_reassessments
    ADD COLUMN status VARCHAR(32) NOT NULL DEFAULT 'pending_review',
    ADD COLUMN recommended_plan_id VARCHAR(80);
CREATE INDEX ix_policy_reassessments_owner_status ON public.policy_reassessments(owner_id, status);

ALTER TABLE public.review_decisions
    ADD COLUMN reassessment_id VARCHAR(36) REFERENCES public.policy_reassessments(id);
