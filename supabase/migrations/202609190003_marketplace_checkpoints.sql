-- Marketplace Pivot v2 / Phase 3: two distinct broker checkpoints.

ALTER TABLE public.review_decisions
    ADD COLUMN marketplace_application_id VARCHAR(36)
        REFERENCES public.marketplace_applications(id),
    ADD COLUMN checkpoint VARCHAR(24)
        CHECK (checkpoint IS NULL OR checkpoint = 'checkpoint_2');

CREATE UNIQUE INDEX uq_review_decisions_marketplace_checkpoint
    ON public.review_decisions(marketplace_application_id, checkpoint)
    WHERE marketplace_application_id IS NOT NULL;

CREATE FUNCTION public.enforce_marketplace_application_checkpoint() RETURNS trigger
LANGUAGE plpgsql SET search_path = public AS $$
BEGIN
    IF NEW.status = 'sent_to_providers' AND OLD.status <> 'sent_to_providers' THEN
        IF OLD.status <> 'broker_approved' THEN
            RAISE EXCEPTION 'application must be broker_approved before provider submission';
        END IF;
        IF NOT EXISTS (
            SELECT 1
            FROM public.review_decisions review
            JOIN public.recommendations recommendation
              ON recommendation.id = review.recommendation_id
            WHERE recommendation.case_id = NEW.case_id
              AND recommendation.status = 'approved'
              AND review.action IN ('approve', 'edit')
        ) THEN
            RAISE EXCEPTION 'checkpoint 1 approval is required before provider submission';
        END IF;
    END IF;

    IF NEW.status = 'bound' AND OLD.status <> 'bound' THEN
        IF NOT EXISTS (
            SELECT 1 FROM public.provider_quotations quotation
            WHERE quotation.application_id = NEW.id AND quotation.status = 'accepted'
        ) OR NOT EXISTS (
            SELECT 1 FROM public.review_decisions review
            WHERE review.marketplace_application_id = NEW.id
              AND review.checkpoint = 'checkpoint_2'
              AND review.action = 'approve'
        ) THEN
            RAISE EXCEPTION 'accepted quotation and checkpoint 2 approval are required before binding';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER marketplace_application_checkpoint_guard
BEFORE UPDATE OF status ON public.marketplace_applications
FOR EACH ROW EXECUTE FUNCTION public.enforce_marketplace_application_checkpoint();

CREATE FUNCTION public.enforce_marketplace_policy_checkpoint() RETURNS trigger
LANGUAGE plpgsql SET search_path = public AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM public.marketplace_applications application
        JOIN public.provider_quotations quotation
          ON quotation.id = NEW.quotation_id
         AND quotation.application_id = application.id
        WHERE application.id = NEW.application_id
          AND application.status = 'broker_final_review'
          AND quotation.status = 'accepted'
    ) OR NOT EXISTS (
        SELECT 1 FROM public.review_decisions review
        WHERE review.marketplace_application_id = NEW.application_id
          AND review.checkpoint = 'checkpoint_2'
          AND review.action = 'approve'
    ) THEN
        RAISE EXCEPTION 'checkpoint 2 approval is required before policy creation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER marketplace_policy_checkpoint_guard
BEFORE INSERT ON public.policies_marketplace
FOR EACH ROW EXECUTE FUNCTION public.enforce_marketplace_policy_checkpoint();
