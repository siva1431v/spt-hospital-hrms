"""
One-off migration: copy all data from the SQLite database into PostgreSQL.

Usage (from the backend/ folder):
    python -m scripts.migrate_sqlite_to_postgres \
        --sqlite spt_hrms.db \
        --postgres "postgresql://USER:PASS@HOST:PORT/DBNAME"

- Creates any missing tables in Postgres from the SQLAlchemy models.
- Refuses to run if the Postgres tables already hold data (use --wipe to clear them first).
- Copies every table in foreign-key order, converting SQLite 0/1 to real booleans.
- Resets Postgres id sequences so new rows don't collide.
- Prints a row-count comparison at the end.
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, MetaData, select, text, Boolean, func


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sqlite", default="spt_hrms.db")
    ap.add_argument("--postgres", required=True, help="postgresql://user:pass@host:port/db")
    ap.add_argument("--wipe", action="store_true", help="Delete existing Postgres rows first")
    ap.add_argument("--drop-orphans", action="store_true",
                    help="After loading, delete rows whose required parent is missing (nullable links are set to NULL)")
    args = ap.parse_args()

    pg_url = args.postgres.replace("postgresql+asyncpg://", "postgresql://").replace("postgres://", "postgresql://", 1)
    if not os.path.exists(args.sqlite):
        sys.exit(f"SQLite file not found: {args.sqlite}")

    # Register all models on Base.metadata
    from app.core.database import Base
    import app.models  # noqa: F401
    from app.models import employee, department, shift, attendance, payroll, user, audit, leave  # noqa: F401

    src = create_engine(f"sqlite:///{args.sqlite}")
    dst = create_engine(pg_url)

    Base.metadata.create_all(dst)

    src_meta = MetaData()
    src_meta.reflect(src)
    tables = [t for t in Base.metadata.sorted_tables if t.name in src_meta.tables]
    skipped = sorted(set(src_meta.tables) - {t.name for t in tables} - {"sqlite_sequence", "alembic_version"})
    if skipped:
        print(f"Note: SQLite tables with no model (not copied): {skipped}")

    with dst.begin() as dconn:
        existing = {t.name: dconn.execute(select(func.count()).select_from(t)).scalar() for t in tables}
        if any(existing.values()):
            if not args.wipe:
                busy = {k: v for k, v in existing.items() if v}
                sys.exit(f"Postgres already has data {busy}. Re-run with --wipe to replace it.")
            for t in reversed(tables):
                dconn.execute(t.delete())

    with src.connect() as sconn, dst.begin() as dconn:
        # departments <-> employees reference each other, so pause FK triggers during the bulk load
        # (needs the default Railway 'postgres' superuser). Integrity is checked afterwards.
        dconn.execute(text("SET session_replication_role = replica"))
        for t in tables:
            src_cols = {c.name for c in src_meta.tables[t.name].columns}
            cols = [c for c in t.columns if c.name in src_cols]
            bool_cols = {c.name for c in cols if isinstance(c.type, Boolean)}
            rows = sconn.execute(text(f'SELECT {", ".join(chr(34)+c.name+chr(34) for c in cols)} FROM "{t.name}"')).mappings().all()
            batch = []
            for r in rows:
                d = dict(r)
                for b in bool_cols:
                    if d.get(b) is not None:
                        d[b] = bool(d[b])
                batch.append(d)
            if batch:
                dconn.execute(t.insert(), batch)
            print(f"  {t.name:35s} {len(batch):6d} rows")

        dconn.execute(text("SET session_replication_role = DEFAULT"))

        # Reset sequences for integer primary keys
        for t in tables:
            pk = list(t.primary_key.columns)
            if len(pk) == 1 and pk[0].autoincrement is not False and str(pk[0].type).upper().startswith("INT"):
                dconn.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('\"{t.name}\"', '{pk[0].name}'), "
                    f"COALESCE((SELECT MAX(\"{pk[0].name}\") FROM \"{t.name}\"), 0) + 1, false)"
                ))

    dropped = {}
    if args.drop_orphans:
        print("\nRemoving orphan references:")
        with dst.connect() as d:
            before = {t.name: d.execute(select(func.count()).select_from(t)).scalar() for t in tables}
        with dst.begin() as d:
            changed = True
            while changed:
                changed = False
                for t in tables:
                    for fk in t.foreign_keys:
                        col, tgt = fk.parent, fk.column
                        cond = (f'"{col.name}" IS NOT NULL AND NOT EXISTS (SELECT 1 FROM "{tgt.table.name}" p '
                                f'WHERE p."{tgt.name}" = "{t.name}"."{col.name}")')
                        if col.nullable:
                            n = d.execute(text(f'UPDATE "{t.name}" SET "{col.name}" = NULL WHERE {cond}')).rowcount
                            action = "set to NULL"
                        else:
                            n = d.execute(text(f'DELETE FROM "{t.name}" WHERE {cond}')).rowcount
                            action = "rows deleted (plus any cascaded children)"
                        if n:
                            changed = True
                            print(f"  {t.name}.{col.name} -> {tgt.table.name}: {n} {action}")

        with dst.connect() as d:
            for t in tables:
                gone = before[t.name] - d.execute(select(func.count()).select_from(t)).scalar()
                if gone:
                    dropped[t.name] = gone

    print("\nForeign-key integrity check:")
    orphans = 0
    with dst.connect() as d:
        for t in tables:
            for fk in t.foreign_keys:
                col, tgt = fk.parent.name, fk.column
                n = d.execute(text(
                    f'SELECT COUNT(*) FROM "{t.name}" c WHERE c."{col}" IS NOT NULL AND NOT EXISTS '
                    f'(SELECT 1 FROM "{tgt.table.name}" p WHERE p."{tgt.name}" = c."{col}")'
                )).scalar()
                if n:
                    orphans += n
                    print(f"  ORPHAN {t.name}.{col} -> {tgt.table.name}.{tgt.name}: {n} rows")
    print("  all references valid" if not orphans else f"  {orphans} orphan references found (see above; re-run with --wipe --drop-orphans)")
    ok_fk = orphans == 0

    print("\nVerification (SQLite vs Postgres):")
    ok = ok_fk
    with src.connect() as s, dst.connect() as d:
        for t in tables:
            a = s.execute(text(f'SELECT COUNT(*) FROM "{t.name}"')).scalar()
            b = d.execute(select(func.count()).select_from(t)).scalar()
            gone = dropped.get(t.name, 0)
            flag = "OK " if a - gone == b else "MISMATCH"
            ok &= a - gone == b
            note = f"  ({gone} orphans dropped)" if gone else ""
            print(f"  {flag} {t.name:35s} {a:6d} -> {b:6d}{note}")
    print("\nMigration complete." if ok else "\nMigration finished WITH MISMATCHES — check above.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
