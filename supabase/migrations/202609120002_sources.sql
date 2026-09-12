-- Public source snapshots are administrator refreshed and not exposed via PostgREST.
CREATE TABLE public.source_snapshots (
    id VARCHAR(36) PRIMARY KEY,
    source_id VARCHAR(80) NOT NULL,
    url VARCHAR(1000) NOT NULL,
    mime VARCHAR(40) NOT NULL,
    sha256 VARCHAR(64) NOT NULL,
    fetched_at TIMESTAMP WITH TIME ZONE NOT NULL,
    excerpt VARCHAR(12000) NOT NULL,
    verification VARCHAR(30) NOT NULL
);
CREATE INDEX ix_source_snapshots_source_id ON public.source_snapshots (source_id);
ALTER TABLE public.source_snapshots ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.source_snapshots FROM anon, authenticated;
