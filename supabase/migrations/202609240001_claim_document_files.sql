-- Original medical documents are API-only: no anon/authenticated table grants.
CREATE TABLE public.claim_document_files (
    document_id VARCHAR(36) PRIMARY KEY REFERENCES public.claim_documents(id) ON DELETE CASCADE,
    filename VARCHAR(120) NOT NULL,
    media_type VARCHAR(40) NOT NULL,
    content BYTEA NOT NULL
);

ALTER TABLE public.claim_document_files ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.claim_document_files FROM PUBLIC, anon, authenticated;
