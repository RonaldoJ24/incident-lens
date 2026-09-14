"""Apply the checked-in PostgreSQL migrations in deterministic order."""

import argparse
import os
from pathlib import Path
from typing import Iterable, Optional, Union


ROOT = Path(__file__).resolve().parents[1]


def migration_files(migration_dir: Optional[Union[str, Path]] = None) -> Iterable[Path]:
    root = Path(migration_dir) if migration_dir else ROOT / "migrations"
    return sorted(root.glob("[0-9][0-9][0-9]_*.sql"))


def apply_migrations(connection, migration_dir: Optional[Union[str, Path]] = None) -> None:
    """Apply each migration once, rolling back the whole migration on failure."""

    files = list(migration_files(migration_dir))
    if not files:
        raise RuntimeError("No PostgreSQL migrations found")
    with connection.transaction():
        connection.execute(
            """CREATE TABLE IF NOT EXISTS incident_lens_schema_migrations (
              version INTEGER PRIMARY KEY,
              name TEXT NOT NULL,
              applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )"""
        )
        applied = {}
        for row in connection.execute("SELECT version, name FROM incident_lens_schema_migrations").fetchall():
            version = row["version"] if isinstance(row, dict) else row[0]
            name = row["name"] if isinstance(row, dict) else row[1]
            applied[version] = name
        for path in files:
            version = int(path.name[:3])
            if version in applied:
                if applied[version] != path.name:
                    raise RuntimeError("Migration version %d is recorded as %s, not %s" % (version, applied[version], path.name))
                continue
            # The checked-in migrations are declarative statements; execute
            # them individually so this works with psycopg's parameterized
            # protocol as well as its simple-query path.
            for statement in path.read_text(encoding="utf-8").split(";"):
                if statement.strip():
                    connection.execute(statement)
            connection.execute(
                "INSERT INTO incident_lens_schema_migrations(version,name) VALUES (%s,%s)",
                (version, path.name),
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=None, help="PostgreSQL URL; defaults to INCIDENT_LENS_DATABASE_URL")
    parser.add_argument("--migration-dir", default=None)
    args = parser.parse_args()
    database_url = args.database_url or os.getenv("INCIDENT_LENS_DATABASE_URL")
    if not database_url:
        parser.error("--database-url or INCIDENT_LENS_DATABASE_URL is required")
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - setup failure path
        raise SystemExit("PostgreSQL migrations require the psycopg package") from exc
    with psycopg.connect(database_url) as connection:
        apply_migrations(connection, migration_dir=args.migration_dir)


if __name__ == "__main__":
    main()
