-- Provisional and final decisions are separate immutable records.
ALTER TABLE public.claim_decisions DROP CONSTRAINT IF EXISTS claim_decisions_claim_intake_id_key;
ALTER TABLE public.claim_decisions ADD COLUMN provisional_applied_fils integer NOT NULL DEFAULT 0;
ALTER TABLE public.claim_decisions ADD COLUMN net_due_fils integer;
CREATE UNIQUE INDEX claim_one_provisional ON public.claim_decisions(claim_intake_id) WHERE decision_type = 'provisional';
CREATE UNIQUE INDEX claim_one_final ON public.claim_decisions(claim_intake_id) WHERE decision_type <> 'provisional';

CREATE TABLE public.provisional_auth_rules (
  id varchar(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
  policy_type varchar(80) NOT NULL,
  claim_category varchar(80) NOT NULL,
  max_amount_fils integer NOT NULL CHECK (max_amount_fils > 0),
  requires_conditions jsonb NOT NULL DEFAULT '[]'::jsonb,
  active boolean NOT NULL DEFAULT true,
  updated_by varchar(36) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(policy_type, claim_category)
);
CREATE TABLE public.claim_auto_rules (
  id varchar(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
  policy_type varchar(80) NOT NULL,
  claim_category varchar(80) NOT NULL,
  max_amount_fils integer NOT NULL CHECK (max_amount_fils > 0),
  min_confidence double precision NOT NULL CHECK (min_confidence BETWEEN 0 AND 1),
  active boolean NOT NULL DEFAULT true,
  updated_by varchar(36) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(policy_type, claim_category)
);
CREATE TABLE public.claim_quality_audits (
  id varchar(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
  claim_intake_id varchar(36) NOT NULL UNIQUE REFERENCES public.claim_intakes(id) ON DELETE CASCADE,
  status varchar(24) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'correct', 'incorrect')),
  reviewer_id varchar(36),
  note text,
  created_at timestamptz NOT NULL DEFAULT now(),
  reviewed_at timestamptz
);
ALTER TABLE public.provisional_auth_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.claim_auto_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.claim_quality_audits ENABLE ROW LEVEL SECURITY;
GRANT SELECT ON public.provisional_auth_rules, public.claim_auto_rules TO helm_claim_servicing;
GRANT SELECT ON public.claim_quality_audits TO helm_claim_servicing;
CREATE POLICY claim_servicing_read_provisional_rules ON public.provisional_auth_rules FOR SELECT TO helm_claim_servicing USING (true);
CREATE POLICY claim_servicing_read_auto_rules ON public.claim_auto_rules FOR SELECT TO helm_claim_servicing USING (true);
CREATE POLICY claim_servicing_read_quality_audits ON public.claim_quality_audits FOR SELECT TO helm_claim_servicing USING (true);
REVOKE ALL ON public.provisional_auth_rules, public.claim_auto_rules, public.claim_quality_audits FROM anon, authenticated, helm_claim_intake_agent, helm_claim_risk_agent;
INSERT INTO public.provisional_auth_rules(policy_type, claim_category, max_amount_fils, requires_conditions, updated_by)
VALUES ('plan_a', 'emergency_room_admission', 200000, '["emergency_flag", "active_policy", "covered_category"]', 'system_seed');
INSERT INTO public.claim_auto_rules(policy_type, claim_category, max_amount_fils, min_confidence, updated_by)
VALUES ('plan_a', 'general', 100000, 0.8, 'system_seed');
