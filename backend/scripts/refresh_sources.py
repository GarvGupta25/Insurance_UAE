"""Refresh fixed public sources without sending any applicant data."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import engine
from app.models import SourceSnapshot
from app.sources import registry, retrieve


def main():
    with Session(engine()) as db:
        for entry in registry():
            try:
                evidence = retrieve(entry)
            except Exception as error:
                print(f"{entry['id']}: unavailable ({type(error).__name__}); previous evidence retained")
                continue
            latest = db.scalar(
                select(SourceSnapshot)
                .where(SourceSnapshot.source_id == entry["id"])
                .order_by(SourceSnapshot.fetched_at.desc())
                .limit(1)
            )
            if latest and latest.sha256 == evidence["sha256"]:
                print(f"{entry['id']}: unchanged; previous version retained")
                continue
            db.add(SourceSnapshot(**evidence))
            db.commit()
            print(f"{entry['id']}: new unreviewed evidence stored")


if __name__ == "__main__":
    main()
