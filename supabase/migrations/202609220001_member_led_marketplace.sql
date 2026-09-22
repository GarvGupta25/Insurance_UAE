-- The member-led demo journey sends only explicitly selected plans to providers.
-- Broker tooling remains available for support, but does not block the member path.
CREATE OR REPLACE FUNCTION public.enforce_marketplace_application_checkpoint()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.enforce_marketplace_policy_checkpoint()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN NEW;
END;
$$;
