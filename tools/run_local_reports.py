"""Run the actual job CLI against disposable databases, without delivery."""

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from datetime import timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy import text


def main():
    root = Path(__file__).resolve().parents[1]
    writer = create_engine(
        "postgresql+psycopg2://postgres:local-test-only@"
        "127.0.0.1:25435/postgres"
    )
    reader = create_engine(
        "postgresql+psycopg2://postgres:local-test-only@"
        "127.0.0.1:25436/postgres"
    )
    with writer.begin() as con:
        assert not con.execute(text("SELECT pg_is_in_recovery()")).scalar_one()
        with con.connection.cursor() as cursor:
            cursor.execute((root / "tests/fixtures/postgres.sql").read_text())
        lsn = con.execute(
            text("SELECT pg_current_wal_insert_lsn()::text")
        ).scalar_one()
    deadline = time.monotonic() + 15
    while True:
        with reader.connect() as con:
            assert con.execute(text("SELECT pg_is_in_recovery()")).scalar_one()
            replayed = con.execute(
                text(
                    "SELECT pg_last_wal_replay_lsn() >= CAST(:lsn AS pg_lsn)"
                ),
                {"lsn": lsn},
            ).scalar_one()
        if replayed:
            break
        if time.monotonic() >= deadline:
            raise RuntimeError("Standby failed to replay local fixture")
        time.sleep(0.05)
    output = root / ".cache/real-run"
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    environment = {
        "PATH": os.environ["PATH"],
        "TMPDIR": str(output),
        "DATABASE_HOST": "127.0.0.1",
        "DATABASE_PORT": "25435",
        "DATABASE_RO_HOST": "127.0.0.1",
        "DATABASE_RO_PORT": "25436",
        "DATABASE_USER": "postgres",
        "DATABASE_PASSWORD": "local-test-only",
        "DATABASE_NAME": "postgres",
        "CLOWDER_ENABLED": "false",
        "EMAIL_GROUPS": "{}",
        "NAMESPACE": "hccm-prod",
        "RUN_DAILY_REPORTS": "true",
        "WEEKLY_REPORT_SCHEDULED_DAY": str(
            datetime.now(timezone.utc).weekday()
        ),
    }
    completed = subprocess.run(
        [sys.executable, "job.py"],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=180,
    )
    (output / "job.log").write_text(completed.stdout + completed.stderr)
    completed.check_returncode()
    csv_files = list((output / "reports").glob("*.csv"))
    if len(csv_files) != 40:
        raise RuntimeError(f"Expected 40 CLI reports, got {len(csv_files)}")
    if not (output / "koku_metrics.zip").is_file():
        raise RuntimeError("CLI did not create its report archive")
    with writer.connect() as con:
        rows = con.execute(
            text("SELECT count(*) FROM public.__customer_total_data")
        ).scalar_one()
    if rows <= 1:
        raise RuntimeError("CLI failed to persist daily totals")
    print(
        json.dumps(
            {
                "cli_reports": len(csv_files),
                "persisted_dates": rows,
                "external_delivery": "disabled by isolated environment",
            }
        )
    )
    writer.dispose()
    reader.dispose()


if __name__ == "__main__":
    main()
