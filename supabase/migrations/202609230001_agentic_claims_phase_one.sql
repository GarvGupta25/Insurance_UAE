-- Phase 0 keeps the current claim tables and financial servicing records intact.
ALTER TABLE public.claim_intakes DROP CONSTRAINT IF EXISTS claim_intakes_kind_check;
ALTER TABLE public.claim_intakes ADD CONSTRAINT claim_intakes_kind_check
  CHECK (kind IN ('pre_auth', 'claim', 'reimbursement', 'appeal', 'emergency', 'pending'));
CREATE TABLE public.claim_findings (
  id varchar(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
  claim_intake_id varchar(36) NOT NULL REFERENCES public.claim_intakes(id) ON DELETE CASCADE,
  agent_name varchar(40) NOT NULL,
  finding_type varchar(40) NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  confidence double precision NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX claim_findings_claim_idx ON public.claim_findings(claim_intake_id);

CREATE TABLE public.claim_audit_log (
  id varchar(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
  claim_intake_id varchar(36) NOT NULL REFERENCES public.claim_intakes(id) ON DELETE CASCADE,
  actor_type varchar(16) NOT NULL CHECK (actor_type IN ('agent', 'broker', 'system')),
  actor_id varchar(80) NOT NULL,
  action varchar(80) NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX claim_audit_log_claim_idx ON public.claim_audit_log(claim_intake_id);
CREATE FUNCTION public.claim_audit_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Claim audit records are immutable'; END;
$$;
CREATE TRIGGER claim_audit_no_update BEFORE UPDATE OR DELETE ON public.claim_audit_log
FOR EACH ROW EXECUTE FUNCTION public.claim_audit_immutable();

CREATE TABLE public.oncall_roster (
  id varchar(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
  broker_id varchar(36) NOT NULL,
  shift_start timestamptz NOT NULL,
  shift_end timestamptz NOT NULL,
  is_active boolean NOT NULL DEFAULT true,
  CHECK (shift_end > shift_start)
);
CREATE INDEX oncall_active_shift_idx ON public.oncall_roster(shift_start, shift_end) WHERE is_active;

-- A read-only index of decisions already made by the deterministic servicing engine.
CREATE TABLE public.claim_decisions (
  id varchar(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
  claim_intake_id varchar(36) NOT NULL UNIQUE REFERENCES public.claim_intakes(id) ON DELETE CASCADE,
  servicing_event_id varchar(36) UNIQUE REFERENCES public.servicing_events(id),
  decision_type varchar(40) NOT NULL,
  amount_fils integer,
  decided_by varchar(80) NOT NULL,
  rationale text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER claim_decisions_no_update BEFORE UPDATE OR DELETE ON public.claim_decisions
FOR EACH ROW EXECUTE FUNCTION public.claim_audit_immutable();

CREATE ROLE helm_claim_intake_agent NOLOGIN;
CREATE ROLE helm_claim_risk_agent NOLOGIN;
CREATE ROLE helm_claim_servicing NOLOGIN;
CREATE ROLE helm_claim_broker NOLOGIN;
GRANT USAGE ON SCHEMA public TO helm_claim_intake_agent, helm_claim_risk_agent, helm_claim_servicing, helm_claim_broker;
GRANT SELECT, INSERT ON public.claim_intakes, public.claim_findings, public.claim_audit_log TO helm_claim_intake_agent;
GRANT SELECT ON public.claim_intakes TO helm_claim_risk_agent;
GRANT SELECT, INSERT ON public.claim_findings, public.claim_audit_log TO helm_claim_risk_agent;
GRANT SELECT ON public.claim_documents, public.policies TO helm_claim_intake_agent, helm_claim_risk_agent;
GRANT SELECT ON public.claim_intakes, public.claim_findings, public.claim_audit_log TO helm_claim_servicing;
GRANT SELECT, INSERT ON public.claim_decisions TO helm_claim_servicing;
GRANT SELECT, INSERT ON public.claim_decisions TO helm_claim_broker;
REVOKE ALL ON public.claim_decisions FROM anon, authenticated, helm_claim_intake_agent, helm_claim_risk_agent;

ALTER TABLE public.claim_findings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.claim_audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.oncall_roster ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.claim_decisions ENABLE ROW LEVEL SECURITY;
CREATE POLICY claim_intake_agent_write ON public.claim_intakes FOR INSERT TO helm_claim_intake_agent WITH CHECK (true);
CREATE POLICY claim_intake_agent_read ON public.claim_intakes FOR SELECT TO helm_claim_intake_agent USING (true);
CREATE POLICY claim_risk_agent_read ON public.claim_intakes FOR SELECT TO helm_claim_risk_agent USING (true);
CREATE POLICY claim_documents_agent_read ON public.claim_documents FOR SELECT TO helm_claim_intake_agent, helm_claim_risk_agent USING (true);
CREATE POLICY policies_claim_agent_read ON public.policies FOR SELECT TO helm_claim_intake_agent, helm_claim_risk_agent USING (true);
CREATE POLICY claim_findings_agent_write ON public.claim_findings FOR INSERT TO helm_claim_intake_agent, helm_claim_risk_agent WITH CHECK (true);
CREATE POLICY claim_findings_agent_read ON public.claim_findings FOR SELECT TO helm_claim_intake_agent, helm_claim_risk_agent, helm_claim_servicing USING (true);
CREATE POLICY claim_audit_agent_write ON public.claim_audit_log FOR INSERT TO helm_claim_intake_agent, helm_claim_risk_agent WITH CHECK (true);
CREATE POLICY claim_audit_servicing_read ON public.claim_audit_log FOR SELECT TO helm_claim_servicing USING (true);
CREATE POLICY claim_decisions_servicing_write ON public.claim_decisions FOR INSERT TO helm_claim_servicing WITH CHECK (true);
CREATE POLICY claim_decisions_servicing_read ON public.claim_decisions FOR SELECT TO helm_claim_servicing USING (true);
CREATE POLICY claim_decisions_broker_write ON public.claim_decisions FOR INSERT TO helm_claim_broker WITH CHECK (true);
CREATE POLICY claim_decisions_broker_read ON public.claim_decisions FOR SELECT TO helm_claim_broker USING (true);
GRANT SELECT ON public.claim_findings TO authenticated;
CREATE POLICY claim_findings_scoped_read ON public.claim_findings FOR SELECT TO authenticated
USING (EXISTS (
  SELECT 1 FROM public.claim_intakes intake JOIN public.policies policy ON policy.id = intake.policy_id
  WHERE intake.id = claim_findings.claim_intake_id
    AND (policy.owner_id = auth.uid()::text OR public.marketplace_is_broker_or_support())
));
-- All mutations, roster reads and audit reads stay server-side.
