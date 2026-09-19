-- Marketplace Pivot v2 / Phase 2.
-- The existing Helm Direct catalogue remains the immutable JSON fixture used by domain.py.
-- This relational catalogue stores provider-owned marketplace plans, including exact reference copies
-- of the three Helm Direct fixture plans, without changing the fixture or the existing quote flow.

CREATE TABLE public.providers (
    id VARCHAR(36) PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    is_seed_demo BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

CREATE TABLE public.provider_users (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id),
    provider_id VARCHAR(36) NOT NULL REFERENCES public.providers(id),
    display_name TEXT NOT NULL
);
CREATE INDEX ix_provider_users_provider_id ON public.provider_users(provider_id);

CREATE TABLE public.marketplace_plans (
    id VARCHAR(36) PRIMARY KEY,
    provider_id VARCHAR(36) NOT NULL REFERENCES public.providers(id),
    plan_code VARCHAR(80) NOT NULL,
    name TEXT NOT NULL,
    terms JSONB NOT NULL,
    is_helm_direct_reference BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    UNIQUE(provider_id, plan_code)
);
CREATE INDEX ix_marketplace_plans_provider_id ON public.marketplace_plans(provider_id);

CREATE TABLE public.marketplace_applications (
    id VARCHAR(36) PRIMARY KEY,
    owner_id VARCHAR(36) NOT NULL,
    case_id VARCHAR(36) NOT NULL REFERENCES public.shopping_cases(id),
    provider_id VARCHAR(36) NOT NULL REFERENCES public.providers(id),
    status TEXT NOT NULL DEFAULT 'awaiting_broker_review' CHECK (status IN (
        'awaiting_broker_review', 'broker_approved', 'sent_to_providers',
        'quotes_collected', 'customer_selected', 'provider_accepted',
        'broker_final_review', 'bound', 'declined'
    )),
    consent_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    UNIQUE(case_id, provider_id)
);
CREATE INDEX ix_marketplace_applications_owner_status
    ON public.marketplace_applications(owner_id, status);
CREATE INDEX ix_marketplace_applications_provider_status
    ON public.marketplace_applications(provider_id, status);

CREATE TABLE public.provider_quotations (
    id VARCHAR(36) PRIMARY KEY,
    application_id VARCHAR(36) NOT NULL REFERENCES public.marketplace_applications(id),
    provider_id VARCHAR(36) NOT NULL REFERENCES public.providers(id),
    marketplace_plan_id VARCHAR(36) REFERENCES public.marketplace_plans(id),
    plan_terms JSONB NOT NULL,
    premium NUMERIC(12, 2) NOT NULL CHECK (premium >= 0),
    status TEXT NOT NULL DEFAULT 'submitted' CHECK (status IN (
        'submitted', 'shortlisted', 'selected', 'accepted', 'declined', 'withdrawn'
    )),
    submitted_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    UNIQUE(application_id, provider_id)
);
CREATE INDEX ix_provider_quotations_provider_status
    ON public.provider_quotations(provider_id, status);

CREATE TABLE public.policies_marketplace (
    id VARCHAR(36) PRIMARY KEY,
    owner_id VARCHAR(36) NOT NULL,
    application_id VARCHAR(36) NOT NULL UNIQUE REFERENCES public.marketplace_applications(id),
    quotation_id VARCHAR(36) NOT NULL UNIQUE REFERENCES public.provider_quotations(id),
    provider_id VARCHAR(36) NOT NULL REFERENCES public.providers(id),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'discontinued')),
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    discontinued_reason TEXT
);
CREATE INDEX ix_policies_marketplace_owner_id ON public.policies_marketplace(owner_id);
CREATE INDEX ix_policies_marketplace_provider_id ON public.policies_marketplace(provider_id);

CREATE TABLE public.provider_payments (
    id VARCHAR(36) PRIMARY KEY,
    owner_id VARCHAR(36) NOT NULL,
    policy_id VARCHAR(36) NOT NULL REFERENCES public.policies_marketplace(id),
    amount NUMERIC(12, 2) NOT NULL CHECK (amount >= 0),
    paid_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    status TEXT NOT NULL DEFAULT 'paid' CHECK (status IN ('paid', 'due', 'overdue'))
);
CREATE INDEX ix_provider_payments_policy_id ON public.provider_payments(policy_id);

CREATE TABLE public.provider_flags (
    id VARCHAR(36) PRIMARY KEY,
    owner_id VARCHAR(36) NOT NULL,
    policy_id VARCHAR(36) NOT NULL REFERENCES public.policies_marketplace(id),
    provider_id VARCHAR(36) NOT NULL REFERENCES public.providers(id),
    reason TEXT NOT NULL,
    note TEXT,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'reviewed', 'closed')),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);
CREATE INDEX ix_provider_flags_provider_status ON public.provider_flags(provider_id, status);

-- Provider identity is always derived from the authenticated account, never from a browser-supplied ID.
CREATE FUNCTION public.current_provider_id() RETURNS VARCHAR(36)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
    SELECT provider_id
    FROM public.provider_users
    WHERE user_id = auth.uid()
    LIMIT 1;
$$;
REVOKE ALL ON FUNCTION public.current_provider_id() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.current_provider_id() TO authenticated;

CREATE FUNCTION public.marketplace_is_broker_or_support() RETURNS BOOLEAN
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
    SELECT COALESCE((auth.jwt() -> 'app_metadata' ->> 'helm_role') IN ('broker', 'support_agent'), false);
$$;
REVOKE ALL ON FUNCTION public.marketplace_is_broker_or_support() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.marketplace_is_broker_or_support() TO authenticated;

ALTER TABLE public.providers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.provider_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.marketplace_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.marketplace_applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.provider_quotations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.policies_marketplace ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.provider_payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.provider_flags ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.providers, public.provider_users, public.marketplace_plans,
    public.marketplace_applications, public.provider_quotations, public.policies_marketplace,
    public.provider_payments, public.provider_flags FROM anon, authenticated;
GRANT SELECT ON public.providers, public.provider_users, public.marketplace_plans,
    public.marketplace_applications, public.provider_quotations, public.policies_marketplace,
    public.provider_payments, public.provider_flags TO authenticated;

CREATE POLICY providers_authenticated_read ON public.providers FOR SELECT TO authenticated USING (true);
CREATE POLICY marketplace_plans_authenticated_read ON public.marketplace_plans
    FOR SELECT TO authenticated USING (true);
CREATE POLICY provider_users_own_or_privileged_read ON public.provider_users
    FOR SELECT TO authenticated
    USING (user_id = auth.uid() OR public.marketplace_is_broker_or_support());

CREATE POLICY marketplace_applications_scoped_read ON public.marketplace_applications
    FOR SELECT TO authenticated
    USING (
        owner_id = auth.uid()::text
        OR provider_id = public.current_provider_id()
        OR public.marketplace_is_broker_or_support()
    );

CREATE POLICY provider_quotations_scoped_read ON public.provider_quotations
    FOR SELECT TO authenticated
    USING (
        provider_id = public.current_provider_id()
        OR public.marketplace_is_broker_or_support()
        OR EXISTS (
            SELECT 1
            FROM public.marketplace_applications application
            WHERE application.id = provider_quotations.application_id
              AND application.owner_id = auth.uid()::text
        )
    );

CREATE POLICY policies_marketplace_scoped_read ON public.policies_marketplace
    FOR SELECT TO authenticated
    USING (
        owner_id = auth.uid()::text
        OR provider_id = public.current_provider_id()
        OR public.marketplace_is_broker_or_support()
    );

CREATE POLICY provider_payments_scoped_read ON public.provider_payments
    FOR SELECT TO authenticated
    USING (
        owner_id = auth.uid()::text
        OR public.marketplace_is_broker_or_support()
        OR EXISTS (
            SELECT 1
            FROM public.policies_marketplace policy
            WHERE policy.id = provider_payments.policy_id
              AND policy.provider_id = public.current_provider_id()
        )
    );

CREATE POLICY provider_flags_scoped_read ON public.provider_flags
    FOR SELECT TO authenticated
    USING (
        owner_id = auth.uid()::text
        OR provider_id = public.current_provider_id()
        OR public.marketplace_is_broker_or_support()
    );

-- The FastAPI backend owns every marketplace mutation. Phase 5 adds provider endpoints with
-- server-side provider scoping; no direct browser INSERT/UPDATE/DELETE grants are created here.
