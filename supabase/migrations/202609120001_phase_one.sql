-- Helm Phase 1. Backend owns mutations; browser access is read-only and owner-scoped.


CREATE TABLE audit_events (
	action VARCHAR(60) NOT NULL, 
	subject_id VARCHAR(36) NOT NULL, 
	details JSON NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	owner_id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_audit_events_owner_id ON audit_events (owner_id);

ALTER TABLE public.audit_events ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.audit_events FROM anon, authenticated;


CREATE TABLE command_receipts (
	key VARCHAR(100) NOT NULL, 
	payload_hash VARCHAR(64) NOT NULL, 
	response JSON NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	owner_id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (owner_id, key)
)

;

CREATE INDEX ix_command_receipts_owner_id ON command_receipts (owner_id);

ALTER TABLE public.command_receipts ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.command_receipts FROM anon, authenticated;


CREATE TABLE documents (
	kind VARCHAR(24) NOT NULL, 
	sha256 VARCHAR(64) NOT NULL, 
	extraction JSON NOT NULL, 
	accepted BOOLEAN NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	owner_id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_documents_owner_id ON documents (owner_id);

ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.documents FROM anon, authenticated;

GRANT SELECT ON public.documents TO authenticated;

CREATE POLICY own_read ON public.documents FOR SELECT TO authenticated USING (owner_id = (select auth.uid())::text);


CREATE TABLE profiles (
	version INTEGER NOT NULL, 
	facts JSON NOT NULL, 
	provenance JSON NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	owner_id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (owner_id)
)

;

CREATE INDEX ix_profiles_owner_id ON profiles (owner_id);

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.profiles FROM anon, authenticated;

GRANT SELECT ON public.profiles TO authenticated;

CREATE POLICY own_read ON public.profiles FOR SELECT TO authenticated USING (owner_id = (select auth.uid())::text);


CREATE TABLE shopping_cases (
	version INTEGER NOT NULL, 
	status VARCHAR(40) NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	owner_id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_shopping_cases_owner_id ON shopping_cases (owner_id);

ALTER TABLE public.shopping_cases ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.shopping_cases FROM anon, authenticated;

GRANT SELECT ON public.shopping_cases TO authenticated;

CREATE POLICY own_read ON public.shopping_cases FOR SELECT TO authenticated USING (owner_id = (select auth.uid())::text);


CREATE TABLE messages (
	case_id VARCHAR(36) NOT NULL, 
	role VARCHAR(16) NOT NULL, 
	text VARCHAR(12000) NOT NULL, 
	modality VARCHAR(16) NOT NULL, 
	details JSON NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	owner_id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(case_id) REFERENCES shopping_cases (id)
)

;

CREATE INDEX ix_messages_owner_id ON messages (owner_id);

CREATE INDEX ix_messages_case_id ON messages (case_id);

ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.messages FROM anon, authenticated;

GRANT SELECT ON public.messages TO authenticated;

CREATE POLICY own_read ON public.messages FOR SELECT TO authenticated USING (owner_id = (select auth.uid())::text);


CREATE TABLE profile_versions (
	profile_id VARCHAR(36) NOT NULL, 
	version INTEGER NOT NULL, 
	facts JSON NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	owner_id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (profile_id, version), 
	FOREIGN KEY(profile_id) REFERENCES profiles (id)
)

;

CREATE INDEX ix_profile_versions_owner_id ON profile_versions (owner_id);

ALTER TABLE public.profile_versions ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.profile_versions FROM anon, authenticated;


CREATE TABLE quotes (
	case_id VARCHAR(36) NOT NULL, 
	profile_version INTEGER NOT NULL, 
	snapshot JSON NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	owner_id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(case_id) REFERENCES shopping_cases (id)
)

;

CREATE INDEX ix_quotes_owner_id ON quotes (owner_id);

ALTER TABLE public.quotes ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.quotes FROM anon, authenticated;

GRANT SELECT ON public.quotes TO authenticated;

CREATE POLICY own_read ON public.quotes FOR SELECT TO authenticated USING (owner_id = (select auth.uid())::text);


CREATE TABLE agent_runs (
	case_id VARCHAR(36) NOT NULL, 
	message_id VARCHAR(36) NOT NULL, 
	status VARCHAR(24) NOT NULL, 
	attempts INTEGER NOT NULL, 
	leased_until TIMESTAMP WITH TIME ZONE, 
	result JSON NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	owner_id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(case_id) REFERENCES shopping_cases (id), 
	FOREIGN KEY(message_id) REFERENCES messages (id)
)

;

CREATE INDEX ix_agent_runs_status ON agent_runs (status);

CREATE INDEX ix_agent_runs_owner_id ON agent_runs (owner_id);

ALTER TABLE public.agent_runs ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.agent_runs FROM anon, authenticated;


CREATE TABLE applications (
	quote_id VARCHAR(36) NOT NULL, 
	status VARCHAR(40) NOT NULL, 
	snapshot JSON NOT NULL, 
	payload_hash VARCHAR(64) NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	owner_id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(quote_id) REFERENCES quotes (id)
)

;

CREATE INDEX ix_applications_owner_id ON applications (owner_id);

ALTER TABLE public.applications ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.applications FROM anon, authenticated;

GRANT SELECT ON public.applications TO authenticated;

CREATE POLICY own_read ON public.applications FOR SELECT TO authenticated USING (owner_id = (select auth.uid())::text);


CREATE TABLE policies (
	application_id VARCHAR(36), 
	status VARCHAR(40) NOT NULL, 
	snapshot JSON NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	owner_id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (application_id), 
	FOREIGN KEY(application_id) REFERENCES applications (id)
)

;

CREATE INDEX ix_policies_owner_id ON policies (owner_id);

ALTER TABLE public.policies ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.policies FROM anon, authenticated;

GRANT SELECT ON public.policies TO authenticated;

CREATE POLICY own_read ON public.policies FOR SELECT TO authenticated USING (owner_id = (select auth.uid())::text);


CREATE TABLE instalments (
	policy_id VARCHAR(36) NOT NULL, 
	position INTEGER NOT NULL, 
	due_date VARCHAR(10) NOT NULL, 
	amount INTEGER NOT NULL, 
	currency VARCHAR(3) NOT NULL, 
	status VARCHAR(24) NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	owner_id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (policy_id, position), 
	FOREIGN KEY(policy_id) REFERENCES policies (id)
)

;

CREATE INDEX ix_instalments_owner_id ON instalments (owner_id);

ALTER TABLE public.instalments ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.instalments FROM anon, authenticated;

GRANT SELECT ON public.instalments TO authenticated;

CREATE POLICY own_read ON public.instalments FOR SELECT TO authenticated USING (owner_id = (select auth.uid())::text);


CREATE TABLE payment_orders (
	installment_id VARCHAR(36) NOT NULL, 
	provider VARCHAR(24) NOT NULL, 
	provider_order_id VARCHAR(100), 
	status VARCHAR(24) NOT NULL, 
	amount INTEGER NOT NULL, 
	currency VARCHAR(3) NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	owner_id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(installment_id) REFERENCES instalments (id), 
	UNIQUE (provider_order_id)
)

;

CREATE INDEX ix_payment_orders_owner_id ON payment_orders (owner_id);

ALTER TABLE public.payment_orders ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.payment_orders FROM anon, authenticated;

GRANT SELECT ON public.payment_orders TO authenticated;

CREATE POLICY own_read ON public.payment_orders FOR SELECT TO authenticated USING (owner_id = (select auth.uid())::text);


CREATE TABLE receipts (
	order_id VARCHAR(36) NOT NULL, 
	installment_id VARCHAR(36) NOT NULL, 
	provider_payment_id VARCHAR(100) NOT NULL, 
	amount INTEGER NOT NULL, 
	currency VARCHAR(3) NOT NULL, 
	provider VARCHAR(24) NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	owner_id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (order_id), 
	FOREIGN KEY(order_id) REFERENCES payment_orders (id), 
	UNIQUE (installment_id), 
	FOREIGN KEY(installment_id) REFERENCES instalments (id), 
	UNIQUE (provider_payment_id)
)

;

CREATE INDEX ix_receipts_owner_id ON receipts (owner_id);

ALTER TABLE public.receipts ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.receipts FROM anon, authenticated;

GRANT SELECT ON public.receipts TO authenticated;

CREATE POLICY own_read ON public.receipts FOR SELECT TO authenticated USING (owner_id = (select auth.uid())::text);


CREATE FUNCTION public.reject_history_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Historical records are append-only'; END;
$$;


CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON public.profile_versions FOR EACH ROW EXECUTE FUNCTION public.reject_history_mutation();

CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON public.quotes FOR EACH ROW EXECUTE FUNCTION public.reject_history_mutation();

CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON public.receipts FOR EACH ROW EXECUTE FUNCTION public.reject_history_mutation();

CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON public.audit_events FOR EACH ROW EXECUTE FUNCTION public.reject_history_mutation();

CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON public.command_receipts FOR EACH ROW EXECUTE FUNCTION public.reject_history_mutation();