"""Generate initial PostgreSQL DDL from the first implementation's declarative schema."""

from pathlib import Path

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.models import Base

target = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "202609120001_phase_one.sql"
target.parent.mkdir(parents=True, exist_ok=True)
parts = ["-- Helm Phase 1. Backend owns mutations; browser access is read-only and owner-scoped."]
for table in Base.metadata.sorted_tables:
    parts.append(str(CreateTable(table).compile(dialect=postgresql.dialect())) + ";")
    for index in table.indexes:
        parts.append(str(CreateIndex(index).compile(dialect=postgresql.dialect())) + ";")
    parts.extend(
        [
            f"ALTER TABLE public.{table.name} ENABLE ROW LEVEL SECURITY;",
            f"REVOKE ALL ON public.{table.name} FROM anon, authenticated;",
        ]
    )
    if table.name not in {"audit_events", "command_receipts", "agent_runs", "profile_versions"}:
        parts.extend(
            [
                f"GRANT SELECT ON public.{table.name} TO authenticated;",
                f"CREATE POLICY own_read ON public.{table.name} FOR SELECT TO authenticated USING (owner_id = (select auth.uid())::text);",
            ]
        )
parts += [
    """
CREATE FUNCTION public.reject_history_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Historical records are append-only'; END;
$$;
"""
]
for name in ["profile_versions", "quotes", "receipts", "audit_events", "command_receipts"]:
    parts.append(
        f"CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON public.{name} FOR EACH ROW EXECUTE FUNCTION public.reject_history_mutation();"
    )
target.write_text("\n\n".join(parts), encoding="utf-8")
print("Generated Phase 1 schema and owner read policies.")
