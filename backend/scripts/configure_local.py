"""Read local Supabase CLI status from stdin. Write ignored local config without printing keys."""

import json
import sys
from pathlib import Path

from cryptography.fernet import Fernet

root = Path(__file__).resolve().parents[2]
raw = sys.stdin.read()
data = json.loads(raw[raw.index("{") :])
backend = root / "backend" / ".env"
frontend = root / "frontend" / ".env"
values = {
    "DATABASE_URL": data["DB_URL"].replace("postgresql://", "postgresql+psycopg://"),
    "SUPABASE_URL": data["API_URL"],
    "SUPABASE_ANON_KEY": data["ANON_KEY"],
    "DOCUMENT_ENCRYPTION_KEY": Fernet.generate_key().decode(),
    "PAYMENT_PROVIDER": "simulator",
}
if backend.exists() or frontend.exists():
    raise SystemExit("Configuration already exists. It was not overwritten.")
backend.write_text("\n".join(f"{key}={value}" for key, value in values.items()) + "\n", encoding="utf-8")
frontend.write_text(
    f"VITE_SUPABASE_URL={values['SUPABASE_URL']}\nVITE_SUPABASE_ANON_KEY={values['SUPABASE_ANON_KEY']}\n",
    encoding="utf-8",
)
print("Local configuration written to ignored .env files. No keys printed.")
