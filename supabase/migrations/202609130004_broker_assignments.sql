-- Assignments are provisioned by an administrator, never by a member or broker route.
CREATE TABLE public.broker_assignments (
    member_id VARCHAR(36) PRIMARY KEY,
    broker_id VARCHAR(36) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);
CREATE INDEX ix_broker_assignments_broker_id ON public.broker_assignments(broker_id);
ALTER TABLE public.broker_assignments ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.broker_assignments FROM anon, authenticated;
